"""The README, Methodology and schema doc must quote the figures the committed data give."""

import doc_figures
import pytest


def test_every_figure_quoted_in_the_docs_matches_the_data():
    drift = doc_figures.missing()
    assert not drift, "documents have drifted from the data:\n" + "\n".join(f"  {d}: {p}" for d, p in drift)


def test_the_checker_notices_a_figure_that_is_not_in_the_text(tmp_path):
    """A checker that cannot fail proves nothing: change one number in a copy of the README and it must report it."""
    for rel in ("README.md", "docs/METHODOLOGY.md", "docs/SCHEMA.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text((doc_figures.ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "data").mkdir()
    for name in ("citrus_by_state.csv", "citrus_totals_by_state.csv", "cpi_u_monthly.csv", "manifest.json"):
        (tmp_path / "data" / name).write_bytes((doc_figures.ROOT / "data" / name).read_bytes())
    assert doc_figures.missing(tmp_path) == []
    readme = tmp_path / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("from 1,143,300 acres", "from 1,143,000 acres"), encoding="utf-8")
    assert [p for d, p in doc_figures.missing(tmp_path) if d == "README"] and all(d == "README" for d, _ in doc_figures.missing(tmp_path))


def test_the_sample_questions_each_rest_on_at_least_30_values_and_are_in_the_readme():
    f = doc_figures.figures()
    readme = (doc_figures.ROOT / "README.md").read_text(encoding="utf-8")
    assert min(f["q1_n"], f["q2_n"], f["q3_n"]) >= 30
    for q in ("How many bearing acres of oranges did Florida have in 1997 compared with 2026?",
              "What was California's value of production in 2018 and in 2026, in constant 2025 dollars?",
              "In 2014, which state had the larger share of the US value of production, Florida or California?"):
        assert q in readme


def test_the_sample_questions_have_the_answers_the_dashboard_shows():
    """Each question is answered on the chart the README names; check the numbers a reader would read off it."""
    import os
    import sys
    old = os.getcwd()
    os.chdir(doc_figures.ROOT)
    sys.path.insert(0, str(doc_figures.ROOT))
    try:
        from src import app
        fig, _ = app.update_fruit("Oranges", "bearing_acres", "real")
        fl = dict(zip(*[list(next(t for t in fig.data if t.name == "Florida")[k]) for k in ("x", "y")]))
        assert (fl[1997], fl[2026]) == (624900.0, 126800.0)                                       # Q1
        line = next(t for t in app.update_state("CA", "real")[2].data if t.type == "scatter")
        ca = dict(zip(line.x, line.y))
        assert (round(ca[2018]), round(ca[2026])) == (3069, 2645)                                  # Q2, $ million in 2025 dollars
        assert round(app.value_share.loc[2014, "CA"]) == 56 and round(app.value_share.loc[2014, "FL"]) == 41   # Q3
    finally:
        os.chdir(old)
        sys.path.remove(str(doc_figures.ROOT))


def test_the_test_count_in_the_readme_is_the_number_of_tests_pytest_collects():
    import re
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=doc_figures.ROOT, capture_output=True, text=True).stdout
    n = int(re.search(r"(\d+) tests? collected", out).group(1))
    assert f"{n} tests run in about" in (doc_figures.ROOT / "README.md").read_text(encoding="utf-8")


def test_the_figures_the_headline_uses_are_the_ones_the_app_computes():
    """The app headline and the README quote the same numbers from two code paths; they must agree."""
    import os
    import sys
    f = doc_figures.figures()
    old = os.getcwd()
    os.chdir(doc_figures.ROOT)
    sys.path.insert(0, str(doc_figures.ROOT))
    try:
        from src import app
        assert (app.ACRES_FALL, app.FL_LOSS_SHARE, app.FL_ACRES_FALL, app.CA_BELOW_PEAK) == (
            f["acres_fall"], f["fl_loss_share"], f["fl_acres_fall"], f["ca_below_peak"])
        assert f"{f['share_fl_first']:.0f}%" in app.HEADLINE and f"{f['share_ca_last']:.0f}%" in app.HEADLINE
    finally:
        os.chdir(old)
        sys.path.remove(str(doc_figures.ROOT))
