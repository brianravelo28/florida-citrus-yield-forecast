"""
Record where each data file came from: `data/manifest.json` holds, per file, its source, the date it was
pulled, its row count and its SHA-256. The fetch scripts write it; the dashboard reads the pull dates for
its source notices (NASS and BLS both ask that users of their APIs credit them and, for BLS, give the date
the data were retrieved); a test fails if a data file changes without its entry.
"""

import datetime
import hashlib
import json
from pathlib import Path

MANIFEST = "data/manifest.json"


def sha256(path):
    """SHA-256 of a data file with line endings normalized to LF, so a Windows working copy (CRLF) and the
    checkout git stores and Linux hosts use (LF) give the same value."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load(path=MANIFEST):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def record(data_path, source, rows, pulled=None, manifest=MANIFEST):
    """Add or replace the entry for one data file, keeping the others. `pulled` defaults to today's date."""
    entries = load(manifest)
    entries[Path(data_path).as_posix()] = {
        "source": source,
        "pulled": pulled or datetime.date.today().isoformat(),
        "rows": int(rows),
        "sha256": sha256(data_path),
    }
    Path(manifest).write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entries
