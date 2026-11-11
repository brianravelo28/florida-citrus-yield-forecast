"""The data manifest: where each file came from, when, and its checksum."""

import json
import os
import sys
from pathlib import Path

import manifest
import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ["data/citrus_by_state.csv", "data/citrus_totals_by_state.csv", "data/cpi_u_monthly.csv"]


def test_the_manifest_matches_every_committed_data_file():
    """Fails if a data file changes without its manifest entry (the data version is its checksum)."""
    entries = manifest.load(ROOT / "data/manifest.json")
    assert sorted(entries) == sorted(FILES)
    import pandas as pd
    for f in FILES:
        e = entries[f]
        assert e["sha256"] == manifest.sha256(ROOT / f), f"{f} changed since it was recorded; rerun its fetch script"
        assert e["rows"] == len(pd.read_csv(ROOT / f))
        assert len(e["pulled"]) == 10 and e["pulled"][4] == "-" and e["source"]


def test_the_checksum_ignores_line_endings(tmp_path):
    lf, crlf = tmp_path / "a.csv", tmp_path / "b.csv"
    lf.write_bytes(b"x,y\n1,2\n")
    crlf.write_bytes(b"x,y\r\n1,2\r\n")
    assert manifest.sha256(lf) == manifest.sha256(crlf)                       # Windows and Linux checkouts agree
    crlf.write_bytes(b"x,y\r\n1,3\r\n")
    assert manifest.sha256(lf) != manifest.sha256(crlf)                       # a changed value is noticed


def test_record_adds_or_replaces_one_entry_and_keeps_the_others(tmp_path):
    data, other, m = tmp_path / "d.csv", tmp_path / "o.csv", tmp_path / "manifest.json"
    data.write_text("a\n1\n2\n")
    other.write_text("b\n9\n")
    manifest.record(other, "source O", 1, pulled="2026-01-02", manifest=m)
    manifest.record(data, "source D", 2, pulled="2026-03-04", manifest=m)
    entries = json.loads(m.read_text())
    assert entries[other.as_posix()]["pulled"] == "2026-01-02" and entries[data.as_posix()]["rows"] == 2
    data.write_text("a\n1\n2\n3\n")
    manifest.record(data, "source D", 3, pulled="2026-05-06", manifest=m)
    entries = json.loads(m.read_text())
    assert entries[data.as_posix()]["pulled"] == "2026-05-06" and entries[data.as_posix()]["rows"] == 3
    assert entries[other.as_posix()]["pulled"] == "2026-01-02"                 # the other file's entry is untouched
    assert manifest.load(tmp_path / "missing.json") == {}                      # no manifest yet is an empty one


def test_the_dashboard_credits_nass_and_bls_with_the_dates_from_the_manifest():
    old = os.getcwd()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    try:
        from src import app
        notice = app.SOURCE_NOTICE
        entries = manifest.load(ROOT / "data/manifest.json")
        assert "This product uses the NASS API but is not endorsed or certified by NASS." in notice
        assert "BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov." in notice
        assert entries["data/citrus_by_state.csv"]["pulled"] in notice and entries["data/cpi_u_monthly.csv"]["pulled"] in notice
        assert app.app.layout["source-notice"].children == notice            # shown in the header of every tab
    finally:
        os.chdir(old)
        sys.path.remove(str(ROOT))
