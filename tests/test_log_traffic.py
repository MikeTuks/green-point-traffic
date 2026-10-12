import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import log_traffic as lt  # noqa: E402
from tomtom import route_points  # noqa: E402


def sast(*args):
    return datetime(*args, tzinfo=lt.SAST)


def find(windows, now):
    return next((w for w in windows if w["from"] <= now <= w["to"]), None)


def test_confirmed_sport_window_is_start_minus_5h_to_end_plus_3h():
    w = lt.event_windows([{"name": "Stormers vs Bristol Bears", "date": "2026-10-17", "time": "16:15",
                           "category": "sport"}])
    assert w[0]["from"] == sast(2026, 10, 17, 11, 15)
    assert w[0]["to"] == sast(2026, 10, 17, 21, 15)  # 16:15 + 2 h + 3 h
    assert w[0]["event_id"] == "2026-10-17-stormers-vs-bristol-bears"


def test_tbc_time_uses_wide_window():
    w = lt.event_windows([{"name": "Bafana friendly", "date": "2026-11-10", "time": "", "category": "sport"}])
    assert (w[0]["from"], w[0]["to"]) == (sast(2026, 11, 10, 10), sast(2026, 11, 10, 23))


def test_multi_day_event_gets_one_window_per_day():
    w = lt.event_windows([{"name": "HSBC SVNS Cape Town", "date": "2026-12-05", "end_date": "2026-12-06",
                           "time": "08:00", "category": "sport"}])
    assert len(w) == 2
    assert find(w, sast(2026, 12, 6, 9)) is not None
    assert find(w, sast(2026, 12, 5, 23, 30)) is None
    assert {x["event_id"] for x in w} == {"2026-12-05-hsbc-svns-cape-town"}


def test_end_time_overrides_default_duration():
    w = lt.event_windows([{"name": "HSBC SVNS Cape Town", "date": "2026-12-05", "end_date": "2026-12-06",
                           "time": "10:00", "end_time": "20:00", "category": "sport"}])
    assert w[1]["end"] == sast(2026, 12, 6, 20)
    assert (w[1]["from"], w[1]["to"]) == (sast(2026, 12, 6, 5), sast(2026, 12, 6, 23))


def test_closure_window_spans_multiple_days():
    w = lt.closure_windows([{"event_date": "2027-03-14", "event_name": "Cape Town Cycle Tour",
                             "road": "Fritz Sonnenberg Rd", "from": "2027-03-11T06:00", "to": "2027-03-14T21:00"}])
    assert find(w, sast(2027, 3, 12, 3)) is not None
    assert find(w, sast(2027, 3, 14, 21, 1)) is None


def test_control_day_skipped_when_event_same_day():
    rows = [{"date": "2026-10-17", "start": "", "end": ""}, {"date": "2026-11-07", "start": "", "end": ""}]
    w = lt.control_windows(rows, event_days={date(2026, 10, 17)})
    assert [x["from"].date() for x in w] == [date(2026, 11, 7)]
    assert (w[0]["from"].hour, w[0]["to"].hour) == (10, 23)


def test_route_points_reverse_for_return():
    out = route_points("H", "D", "A:B", "outbound")
    ret = route_points("H", "D", "B:A", "return")
    assert out == ["H", "A", "B", "D"]
    assert ret == ["D", "B", "A", "H"]
