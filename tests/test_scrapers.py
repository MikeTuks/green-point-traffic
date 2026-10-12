import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scrapers import capetown_gov, dhl_stadium, sportsdb  # noqa: E402
from scrapers.base import ScrapeError  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def by_id(records):
    return {r["source_id"]: r for r in records}


def test_dhl_times_are_utc_converted_to_sast():
    r = by_id(dhl_stadium.parse(load("dhl_events.json"), "now"))
    assert r["event-470"]["start"] == "2026-10-17T16:15:00+02:00"  # known kick-off
    assert r["event-470"]["name"] == "DHL Stormers vs Bristol Bears"
    assert r["event-470"]["time_confirmed"] and r["event-470"]["category_hint"] == "sport"


def test_dhl_multi_day_event_has_end_date():
    svns = by_id(dhl_stadium.parse(load("dhl_events.json"), "now"))["event-457"]
    assert svns["start"] == "2026-12-05T10:00:00+02:00"
    assert svns["end_date"] == "2026-12-06"


def test_dhl_category_mapping():
    r = by_id(dhl_stadium.parse(load("dhl_events.json"), "now"))
    assert r["event-396"]["category_hint"] == "concert"


def test_dhl_midnight_sast_is_time_tbc():
    data = {"data": [{"id": 1, "attributes": {"title": "Gig", "category": "Concerts", "slug": "gig", "event": [
        {"daterange": [{"start": "2026-11-20T22:00:00.000Z", "end": None}]}]}}]}
    r = dhl_stadium.parse(data, "now")[0]
    assert not r["time_confirmed"]
    assert r["start"] == "2026-11-21T18:00:00+02:00"


@pytest.mark.parametrize("data", [{}, {"data": None}, {"data": [{"id": 1}]}])
def test_dhl_structural_change_raises(data):
    with pytest.raises(ScrapeError):
        dhl_stadium.parse(data, "now")


def test_sportsdb_keeps_stormers_home_games_with_known_kickoff():
    r = sportsdb.parse_events(load("sportsdb_day.json"), "events", "now")
    assert [(x["name"], x["start"]) for x in r] == [("Stormers vs Ulster", "2026-10-31T14:45:00+02:00")]


def test_sportsdb_no_events_is_not_a_failure():
    assert sportsdb.parse_events({"event": None}, "event", "now") == []
    with pytest.raises(ScrapeError):
        sportsdb.parse_events({"error": "x"}, "events", "now")


def test_sportsdb_helpers():
    assert sportsdb.season("2027-01-16") == "2026-2027"
    assert sportsdb.season("2026-10-17") == "2026-2027"
    assert sportsdb.opponent_words("DHL Stormers vs Vodacom Bulls") == ["Vodacom", "Bulls"]


def test_city_listing_parses_cards():
    releases = capetown_gov.parse_listing((FIXTURES / "city_listing.html").read_text(encoding="utf-8"))
    assert len(releases) == 3
    first = releases[0]
    assert first["url"].startswith("https://web1.capetown.gov.za/web1/newsandnotices/Home/Release/")
    assert "?" not in first["url"]
    assert len(first["date"]) == 10 and first["title"]


def test_city_release_text_and_keywords():
    text = capetown_gov.release_text((FIXTURES / "city_release.html").read_text(encoding="utf-8"))
    assert "Fish Hoek" in text
    assert capetown_gov.matches("Road closures on Fritz Sonnenberg Road and Beach Road, Green Point") == [
        "beach road", "fritz sonnenberg", "green point"]
    assert capetown_gov.matches(text) == []


def test_city_structural_change_raises():
    with pytest.raises(ScrapeError):
        capetown_gov.parse_listing("<html><body>nothing</body></html>")
    with pytest.raises(ScrapeError):
        capetown_gov.release_text("<html></html>")
