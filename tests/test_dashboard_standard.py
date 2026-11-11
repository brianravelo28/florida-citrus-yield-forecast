"""The dashboard checklist items: About sections, counts, and the host endpoints."""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from dash import dcc, html

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app_module():
    old = os.getcwd()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    try:
        from src import app
        yield app
    finally:
        os.chdir(old)
        sys.path.remove(str(ROOT))


def walk(component):
    """Every component in a Dash tree, parents before children."""
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            yield from walk(c)
    elif children is not None and not isinstance(children, str):
        yield from walk(children)


def text_of(component):
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return " ".join(text_of(c) for c in component)
    return text_of(getattr(component, "children", None))


def assert_footer(footer):
    """A chart footer is exactly: a collapsed 'About this chart' section of italic bullets, then the count."""
    kids = footer.children
    assert len(kids) == 2 and isinstance(kids[0], html.Details) and isinstance(kids[1], html.P)
    summary, bullets = kids[0].children
    assert text_of(summary) == "About this chart" and not getattr(kids[0], "open", False)         # collapsed
    items = bullets.children
    assert items and all(isinstance(li.children, html.I) and text_of(li).strip() for li in items)  # italic, non-empty
    assert text_of(kids[1]).startswith("n = ") and "NASS values behind this chart" in text_of(kids[1])
    return text_of(kids[1])


def test_every_chart_in_the_layout_is_followed_by_an_about_section_and_a_count(app_module):
    graphs = 0
    for node in walk(app_module.app.layout):
        kids = getattr(node, "children", None)
        if isinstance(kids, (list, tuple)) and any(isinstance(k, dcc.Graph) for k in kids):
            graphs += 1
            g = next(k for k in kids if isinstance(k, dcc.Graph))
            after = kids[kids.index(g) + 1:]
            assert len(after) == 1                                  # nothing between or after but the footer
            footer = after[0]
            if getattr(footer, "id", None) is None:                 # a static chart builds its footer at import
                assert_footer(footer)
    assert graphs == 6                                              # 3 on the Overview, 1 By Fruit, 2 By State


def test_dynamic_charts_return_the_same_footer(app_module):
    _, f = app_module.update_value_by_fruit("real")
    assert_footer(f)
    _, f = app_module.update_fruit("Oranges", "value_of_production_usd", "nominal")
    assert_footer(f)
    for footer in app_module.update_state("CA", "real")[1::2]:
        assert_footer(footer)


def test_about_sections_define_the_terms_and_carry_the_caveats_of_their_chart(app_module):
    about = lambda footer: text_of(footer.children[0])
    assert "old enough to bear fruit" in about(app_module.acres_footer())
    value = about(app_module.update_value_by_fruit("real")[1])
    assert "packinghouse-door price" in value and "consumer price index" in value and "preliminary" in value
    assert "Utilized production is the part of the crop" in about(app_module.update_fruit("Lemons", "production_boxes", "real")[1])
    assert "bearing" in about(app_module.update_fruit("Lemons", "yield_boxes_per_acre", "real")[1]).lower()
    # a caveat the data need shows on every chart it affects: the California 2022 yield gap
    assert "58 boxes per acre" in about(app_module.update_fruit("Oranges", "yield_boxes_per_acre", "real")[1])
    assert "preliminary" in about(app_module.share_footer()) and "withheld" in about(app_module.update_fruit("Oranges", "bearing_acres", "real")[1])


def test_counts_match_an_independent_recount_from_the_data_files(app_module):
    df = pd.read_csv(ROOT / "data/citrus_by_state.csv")
    totals = pd.read_csv(ROOT / "data/citrus_totals_by_state.csv")
    nb = df[df.value.notna()]
    # acreage by state: fruit rows before NASS's totals begin, then NASS's 76 state totals (no gap year)
    expected = len(nb[(nb.measure == "bearing_acres") & (nb.year < 2008)]) + len(totals[totals.measure == "bearing_acres"])
    assert text_of(app_module.acres_footer().children[1]) == f"n = {expected:,} NASS values behind this chart"
    # a By Fruit chart: every plotted point, one per non-blank value
    n = len(nb[(nb.measure == "bearing_acres") & (nb.fruit == "Oranges")])
    assert assert_footer(app_module.update_fruit("Oranges", "bearing_acres", "real")[1]) == f"n = {n:,} NASS values behind this chart"
    # the flagged California 2022 yield is drawn as a gap, so it is not counted
    y = len(nb[(nb.measure == "yield_boxes_per_acre") & (nb.fruit == "Oranges")]) - 1
    assert assert_footer(app_module.update_fruit("Oranges", "yield_boxes_per_acre", "real")[1]) == f"n = {y:,} NASS values behind this chart"
    # the dollar toggle changes the dollars, not the number of values
    assert text_of(app_module.update_value_by_fruit("real")[1].children[1]) == text_of(app_module.update_value_by_fruit("nominal")[1].children[1])


def test_a_chart_resting_on_fewer_than_30_values_carries_an_asterisk_with_a_tooltip(app_module):
    small = app_module.update_fruit("Tangelos", "bearing_acres", "real")[1].children[1]       # Florida tangelos: 27 values
    assert "n = 27 " in text_of(small)
    abbr = [c for c in walk(small) if isinstance(c, html.Abbr)]
    assert len(abbr) == 1 and abbr[0].children == "*" and "Fewer than 30 values" in abbr[0].title
    large = app_module.update_fruit("Oranges", "bearing_acres", "real")[1].children[1]
    assert not [c for c in walk(large) if isinstance(c, html.Abbr)]


def test_healthz_is_a_real_endpoint_not_the_dash_front_page(app_module):
    client = app_module.server.test_client()
    r = client.get("/healthz")
    assert r.status_code == 200 and r.is_json and r.get_json() == {"status": "ok"}
    assert client.head("/healthz").status_code == 200
    front = client.get("/")
    assert front.status_code == 200 and not front.is_json and b"_dash-config" in front.data      # the Dash page is still served


def test_debugz_reports_the_process_and_the_loaded_data(app_module):
    r = app_module.server.test_client().get("/debugz")
    d = r.get_json()
    assert r.status_code == 200 and d["status"] == "ok" and d["uptime_seconds"] >= 0 and d["pid"] == os.getpid()
    assert d["python"] == sys.version.split()[0] and d["packages"]["dash"] and d["packages"]["pandas"]
    assert d["data"]["citrus_rows"] == 2483 and d["data"]["totals_rows"] == 152 and d["data"]["latest_season"] == 2026
    assert d["memory_kind"] and (d["memory_mb"] is None or d["memory_mb"] > 0)
    assert "no-store" in r.headers["Cache-Control"]
    assert "NASS_KEY" not in r.get_data(as_text=True)                                            # nothing secret is reported


def test_the_browser_tab_has_a_title(app_module):
    assert app_module.app.title == "US Citrus Industry Dashboard"
