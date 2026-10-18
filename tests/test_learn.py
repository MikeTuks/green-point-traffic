import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from learn import learn  # noqa: E402

EVENTS = [{"id": "a", "category": "sport", "size": "medium"},
          {"id": "b", "category": "sport", "size": "medium"}]


def reading(ts, live, hist, event_id=None, control=False, start=None, end=None, route="outbound"):
    return {"ts": ts, "route": route, "event_id": event_id, "control_day": control,
            "window": "control" if control else "event", "min_from_start": start, "min_from_end": end,
            "status": "ok", "live_s": live, "historic_s": hist}


def test_median_across_events_with_low_high_and_count():
    curves = learn([
        reading("2026-10-17T18:45:00+02:00", 1600, 1000, "a", start=150, end=30),
        reading("2026-10-24T18:45:00+02:00", 1240, 1000, "b", start=150, end=30),
    ], EVENTS)
    c = curves["sport/medium/outbound"]
    assert c["events"] == 2
    assert c["departure"]["30"] == {"median": 7.0, "low": 4.0, "high": 10.0, "n": 2}


def test_control_day_median_is_subtracted_per_hour():
    curves = learn([
        reading("2026-11-07T14:10:00+02:00", 1060, 1000, control=True),
        reading("2026-11-07T14:40:00+02:00", 1180, 1000, control=True),
        reading("2026-10-17T14:20:00+02:00", 1300, 1000, "a", start=-115, end=-235),
    ], EVENTS)
    assert curves["sport/medium/outbound"]["arrival"]["-120"]["median"] == 3.0
    assert "control" not in str(curves)


def test_readings_outside_spans_and_unknown_events_are_ignored():
    curves = learn([
        reading("2026-10-17T17:00:00+02:00", 1600, 1000, "a", start=45, end=-75),
        reading("2026-10-17T18:45:00+02:00", 1600, 1000, "zzz", start=150, end=30),
    ], EVENTS)
    assert curves == {}
