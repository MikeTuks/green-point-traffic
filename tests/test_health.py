import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import scrape_events  # noqa: E402

OK = {"dhl_stadium": 76, "sportsdb": 5, "capetown_gov": 0}


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape_events, "DATA", tmp_path)
    return tmp_path


def run(day, errors=None):
    counts = {s: n for s, n in OK.items() if s not in (errors or {})}
    return scrape_events.update_health(errors or {}, counts, date(2026, 10, day))


def test_success_is_recorded(data_dir):
    assert run(16) == []
    health = json.loads((data_dir / "scrape_health.json").read_text(encoding="utf-8"))
    assert health["dhl_stadium"] == {"last_success": "2026-10-16", "events": 76, "error": None,
                                     "failing_since": None}


def test_failure_fails_workflow_only_on_third_day(data_dir):
    run(15)
    err = {"sportsdb": "eventsnext.php: HTTPError"}
    assert run(16, err) == []
    assert run(16, err) == []  # a second run on the same day does not count twice
    assert run(17, err) == []
    assert run(18, err) == ["sportsdb"]
    health = json.loads((data_dir / "scrape_health.json").read_text(encoding="utf-8"))
    assert health["sportsdb"] == {"last_success": "2026-10-15", "events": 5,
                                  "error": "eventsnext.php: HTTPError", "failing_since": "2026-10-16"}


def test_success_resets_the_streak():
    err = {"capetown_gov": "listing: HTTPError"}
    run(16, err)
    run(17, err)
    assert run(18) == []
    assert run(19, err) == []


def test_first_ever_run_failing():
    assert run(16, {"dhl_stadium": "x"}) == []
