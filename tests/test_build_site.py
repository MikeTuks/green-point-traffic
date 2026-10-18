import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_site import SAST, build  # noqa: E402

NOW = datetime(2026, 10, 18, 6, 17, tzinfo=SAST)


def event(id_, start, end, confirmed=True, **kw):
    return {"id": id_, "name": id_, "start": start, "end_estimate": end, "end_date": None,
            "time_confirmed": confirmed, "category": "sport", "size": "medium", "status": "confirmed",
            "closures": [], **kw}


def cell(m):
    return {"median": m, "low": m, "high": m, "n": 1}


CURVES = {"sport/medium/outbound": {
    "events": 1,
    "arrival": {"-120": cell(2.3), "-105": cell(2.9), "-90": cell(3.3), "-75": cell(0.0)},
    "during": {"0": cell(0.9), "60": cell(-1.1)},
    "departure": {"0": cell(-0.8), "30": cell(7.2), "45": cell(4.2), "60": cell(9.7), "75": cell(4.1),
                  "90": cell(-0.2)},
}}


def test_bad_stretches_follow_start_and_end():
    data = build([event("g", "2026-10-24T16:00:00+02:00", "2026-10-24T18:00:00+02:00")], CURVES, {}, NOW)
    out = data["events"][0]["outlook"]["outbound"]
    assert out["games"] == 1 and out["from"] == "11:00"
    assert out["bad"] == [["14:00", "14:45"], ["18:30", "19:30"]]
    assert len(out["median"]) == 40  # 11:00 to 21:00 in 15-minute slots
    assert out["median"][20] == 0.9 and out["median"][24] == -1.1  # 16:00 and 17:00, during the game
    assert data["events"][0]["outlook"]["return"] == {"games": 0}


def test_past_events_dropped_and_tbc_has_no_outlook():
    data = build([event("old", "2026-10-17T16:15:00+02:00", "2026-10-17T18:15:00+02:00"),
                  event("tbc", "2026-11-10T00:00:00+02:00", "2026-11-10T02:00:00+02:00", confirmed=False)],
                 CURVES, {"sportsdb": {"error": "HTTPError 429", "failing_since": "2026-10-16"}}, NOW)
    assert [e["id"] for e in data["events"]] == ["tbc"]
    assert data["events"][0]["outlook"] is None and data["events"][0]["start"] is None
    assert data["sources"] == [{"name": "TheSportsDB", "ok": False, "failing_since": "2026-10-16"}]


def test_multi_day_event_uses_first_day_hours():
    data = build([event("svns", "2026-12-05T10:00:00+02:00", "2026-12-06T20:00:00+02:00",
                        end_date="2026-12-06")], {}, {}, NOW)
    e = data["events"][0]
    assert (e["days"], e["start"], e["end"]) == (2, "10:00", "20:00")
