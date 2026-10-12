import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import classify  # noqa: E402
import log_traffic as lt  # noqa: E402
from merge_events import merge  # noqa: E402

TODAY = date(2026, 10, 12)
ALL_OK = {"csv", "dhl_stadium", "sportsdb"}


def rec(source, source_id, name, start, confirmed=True, **kw):
    return {"source": source, "source_id": source_id, "name": name, "start": start, "end": None,
            "end_date": None, "time_confirmed": confirmed,
            "time_source": {"csv": "csv", "dhl_stadium": "json", "sportsdb": "sportsdb"}[source],
            "venue_text": "DHL Stadium", "category_hint": "sport", "crowd_hint": None, **kw}


def test_three_sources_merge_into_one_event_with_csv_priority():
    events, review = merge([], [
        rec("csv", "2026-10-17-stormers-vs-bristol-bears", "Stormers vs Bristol Bears", "2026-10-17T16:15:00+02:00",
            size="medium"),
        rec("dhl_stadium", "event-470", "DHL Stormers vs Bristol Bears", "2026-10-17T16:15:00+02:00"),
        rec("sportsdb", "2550793", "Stormers vs Bristol Bears", "2026-10-17T16:15:00+02:00"),
    ], [], ALL_OK, TODAY)
    assert len(events) == 1 and review == []
    e = events[0]
    assert e["id"] == "2026-10-17-stormers-vs-bristol-bears"  # same id the logger already uses
    assert e["sources"] == ["csv", "dhl_stadium", "sportsdb"]
    assert e["end_estimate"] == "2026-10-17T18:15:00+02:00"
    assert e["override"] and e["size"] == "medium"


def test_sportsdb_time_beats_dhl():
    events, _ = merge([], [
        rec("dhl_stadium", "event-472", "DHL Stormers vs Ulster", "2026-10-31T13:45:00+02:00"),
        rec("sportsdb", "1", "Stormers vs Ulster", "2026-10-31T14:45:00+02:00"),
    ], [], ALL_OK, TODAY)
    assert events[0]["start"] == "2026-10-31T14:45:00+02:00"
    assert events[0]["time_source"] == "sportsdb"
    assert events[0]["name"] == "DHL Stormers vs Ulster"


def test_csv_time_conflict_is_flagged_but_csv_wins():
    events, review = merge([], [
        rec("csv", "c", "Stormers vs Bulls", "2027-01-03T15:00:00+02:00"),
        rec("sportsdb", "1", "Stormers vs Bulls", "2027-01-03T16:00:00+02:00"),
    ], [], ALL_OK, TODAY)
    assert events[0]["start"].startswith("2027-01-03T15:00")
    assert [(r["type"], r["detail"]) for r in review] == [("time_conflict", "CSV 15:00, sportsdb 16:00")]


def test_reschedule_keeps_id_by_source_id():
    prev, _ = merge([], [rec("dhl_stadium", "event-9", "Big Concert", "2026-11-20T18:00:00+02:00",
                             category_hint="concert")], [], ALL_OK, TODAY)
    events, review = merge(prev, [rec("dhl_stadium", "event-9", "Big Concert", "2026-11-27T18:00:00+02:00",
                                      category_hint="concert")], [], ALL_OK, TODAY)
    assert len(events) == 1
    assert events[0]["id"] == "2026-11-20-big-concert"
    assert events[0]["start"].startswith("2026-11-27")
    assert events[0]["rescheduled_from"] == "2026-11-20"
    assert review[0]["type"] == "rescheduled"


def test_vanished_events():
    prev, _ = merge([], [
        rec("dhl_stadium", "a", "Future Gig", "2026-11-20T18:00:00+02:00", category_hint="concert"),
        rec("dhl_stadium", "b", "Past Gig", "2026-09-20T18:00:00+02:00", category_hint="concert"),
    ], [], ALL_OK, TODAY)
    events, _ = merge(prev, [], [], ALL_OK, TODAY)
    assert {e["name"]: e["status"] for e in events} == {"Future Gig": "unconfirmed", "Past Gig": "confirmed"}
    events, _ = merge(prev, [], [], {"csv", "sportsdb"}, TODAY)  # DHL failed today
    assert all(e["status"] == "confirmed" for e in events)


def test_multi_day_row_does_not_absorb_other_event_in_range():
    events, _ = merge([], [
        rec("csv", "c", "Cape Town Cycle Tour Expo", "2027-03-11T10:00:00+02:00", end_date="2027-03-13",
            category_hint="other"),
        rec("dhl_stadium", "d", "Tattoo Convention", "2027-03-12T10:00:00+02:00", category_hint="other"),
    ], [], ALL_OK, TODAY)
    assert len(events) == 2


def test_closures_attach_and_set_race_end():
    closures = [{"event_date": "2027-03-14", "event_name": "Cape Town Cycle Tour", "road": "Beach Rd",
                 "from": "2027-03-14T05:00:00+02:00", "to": "2027-03-14T18:30:00+02:00", "source_url": None}]
    events, _ = merge([], [rec("csv", "c", "Cape Town Cycle Tour", "2027-03-14T06:00:00+02:00",
                               category_hint="race")], closures, ALL_OK, TODAY)
    assert events[0]["closures"][0]["road"] == "Beach Rd"
    assert events[0]["end_estimate"] == "2027-03-14T18:30:00+02:00"
    assert events[0]["size"] == "big"


def test_classify_keyword_order_and_size():
    assert classify.category("Cape Town Cycle Tour") == "race"
    assert classify.category("Cape Town Pride Mardi Gras") == "parade"
    assert classify.category("Stormers vs Bulls") == "sport"
    assert classify.category("Coldplay World Tour") == "concert"
    assert classify.category("Wine Show") == "unknown"
    assert classify.size("sport", "DHL Stormers vs Vodacom Bulls") == "big"
    assert classify.size("sport", "Stormers vs Scarlets") == "medium"
    assert classify.size("race", "Anything", crowd=44500) == "big"


def test_logger_reads_multi_day_events_json():
    events, _ = merge([], [rec("csv", "c", "HSBC SVNS Cape Town", "2026-12-05T10:00:00+02:00",
                               end="2026-12-05T20:00:00+02:00", end_date="2026-12-06")], [], ALL_OK, TODAY)
    windows = lt.event_windows(lt.json_rows(events))
    sast = lambda *a: datetime(*a, tzinfo=lt.SAST)  # noqa: E731
    assert [(w["from"], w["to"]) for w in windows] == [
        (sast(2026, 12, 5, 5), sast(2026, 12, 5, 23)), (sast(2026, 12, 6, 5), sast(2026, 12, 6, 23))]
    assert windows[0]["event_id"] == "2026-12-05-hsbc-svns-cape-town"


def test_merge_is_stable_when_nothing_changes():
    records = [rec("csv", "c", "Stormers vs Lions", "2026-12-19T16:00:00+02:00"),
               rec("dhl_stadium", "event-473", "DHL Stormers vs Lions", "2026-12-19T15:00:00+02:00"),
               rec("sportsdb", "1", "Stormers vs Lions", "2026-12-19T16:00:00+02:00")]
    first, _ = merge([], records, [], ALL_OK, TODAY)
    second, review = merge(first, records, [], ALL_OK, TODAY)
    assert first == second and review == []
