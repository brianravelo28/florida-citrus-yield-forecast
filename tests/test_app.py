"""Callback and layout tests for the dashboard: every control combination returns, in both dollar modes."""

import os
import sys
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app_module():
    """The app reads its data files relative to the repo root, so import it from there."""
    old = os.getcwd()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    try:
        from src import app
        yield app
    finally:
        os.chdir(old)
        sys.path.remove(str(ROOT))


def text_of(component):
    """All the text inside a Dash component tree."""
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return " ".join(text_of(c) for c in component)
    return text_of(getattr(component, "children", None))


def line(fig):
    return next(t for t in fig.data if t.type == "scatter" and t.mode == "lines")


def test_layout_has_a_dollar_toggle_that_defaults_to_constant_dollars(app_module):
    toggle = app_module.app.layout["dollars"] if hasattr(app_module.app.layout, "__getitem__") else None
    assert toggle is not None and toggle.value == "real"
    assert {o["value"] for o in toggle.options} == {"real", "nominal"}


@pytest.mark.parametrize("dollars", ["real", "nominal"])
def test_every_fruit_and_measure_combination_returns_a_figure_and_notes(app_module, dollars):
    for fruit in app_module.FRUITS:
        for metric in app_module.METRICS:
            fig, notes = app_module.update_fruit(fruit, metric, dollars)
            assert isinstance(fig, go.Figure) and len(fig.data) >= 1
            assert text_of(notes)                                           # a preliminary-season note at least


@pytest.mark.parametrize("dollars", ["real", "nominal"])
def test_every_state_returns_both_charts(app_module, dollars):
    for state in app_module.STATES:
        a_fig, a_note, v_fig, v_note = app_module.update_state(state, dollars)
        assert len(a_fig.data) >= 1 and len(v_fig.data) >= 2                # fruit stacks plus the state's total line
        assert "dollar values" in text_of(v_note).lower()                   # the note says which dollars


def test_real_values_equal_nominal_in_the_base_season_and_differ_by_the_factor_elsewhere(app_module):
    nominal, _ = app_module.update_value_by_fruit("nominal")
    real, _ = app_module.update_value_by_fruit("real")
    n, r = line(nominal), line(real)
    year = lambda t, y: float(np.asarray(t.y)[list(t.x).index(y)])
    assert year(r, app_module.BASE_YEAR) == pytest.approx(year(n, app_module.BASE_YEAR))
    assert year(r, 1990) == pytest.approx(year(n, 1990) * app_module.FACTORS.loc[1990])
    assert year(r, 1990) > 2 * year(n, 1990) and year(r, 2026) < year(n, 2026)


def test_dollar_axis_and_notes_say_which_dollars(app_module):
    nominal_fig, nominal_note = app_module.update_value_by_fruit("nominal")
    real_fig, real_note = app_module.update_value_by_fruit("real")
    assert "as reported" in nominal_fig.layout.yaxis.title.text and "2025 dollars" in real_fig.layout.yaxis.title.text
    assert "consumer price index" in text_of(real_note) and "not adjusted for inflation" in text_of(nominal_note)
    assert "October 2025" in text_of(real_note) and "11 months" in text_of(real_note)    # the month BLS did not publish
    # the share and acreage charts are not dollar charts and do not change with the toggle
    assert app_module.build_value_share_by_state().layout.yaxis.title.text == "Share of US value (%)"


def test_price_and_value_charts_follow_the_toggle_and_the_other_measures_do_not(app_module):
    for metric in ("value_of_production_usd", "price_usd_per_box"):
        n, _ = app_module.update_fruit("Oranges", metric, "nominal")
        r, _ = app_module.update_fruit("Oranges", metric, "real")
        assert n.layout.yaxis.title.text != r.layout.yaxis.title.text
        assert not np.allclose(np.asarray(n.data[0].y, dtype=float), np.asarray(r.data[0].y, dtype=float), equal_nan=True)
    n, _ = app_module.update_fruit("Oranges", "bearing_acres", "nominal")
    r, _ = app_module.update_fruit("Oranges", "bearing_acres", "real")
    assert np.allclose(np.asarray(n.data[0].y, dtype=float), np.asarray(r.data[0].y, dtype=float), equal_nan=True)
