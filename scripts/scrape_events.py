"""Run the event scrapers.

DHL Stadium lists every event; TheSportsDB is then asked for the
kick-off of each upcoming Stormers game on those dates. City media
releases mentioning Green Point are added to data/needs_review.json.
Each source runs independently: one failure never stops the others.
merge_events.py records each source's outcome in data/scrape_health.json.
merge_events.py calls scrape(); run this file on its own to just print
what the sources return.

    python scripts/scrape_events.py
"""
import json
import sys
from datetime import date
from pathlib import Path

from scrapers import capetown_gov, dhl_stadium, sportsdb
from scrapers.base import ScrapeError

DATA = Path(__file__).resolve().parent.parent / "data"
SOURCES = ("dhl_stadium", "sportsdb", "capetown_gov")
FAIL_DAYS = 3  # a source failing this many days running fails the daily workflow


def stormers_games(records, today):
    """(date, title) of each upcoming Stormers game listed by DHL Stadium."""
    return sorted((r["start"][:10], r["name"]) for r in records
                  if "stormers" in r["name"].lower() and r["start"][:10] >= today.isoformat())


def read_json(name, default):
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(name, value):
    (DATA / name).write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def add_review(items, today):
    """Append items to needs_review.json, skipping ones already there; return the new ones."""
    review = read_json("needs_review.json", [])
    key = lambda item: (item["type"], item.get("url"), item.get("event_id"), item.get("detail"))  # noqa: E731
    known = {key(item) for item in review}
    new = [{**item, "added": today.isoformat()} for item in items if key(item) not in known]
    write_json("needs_review.json", review + new)
    return new


def check_city_releases(today):
    """Add new matching City releases to needs_review.json; return them."""
    flagged, seen = capetown_gov.fetch(set(read_json("seen_releases.json", [])))
    new = add_review([{"type": "city_release", **r} for r in flagged], today)
    write_json("seen_releases.json", sorted(seen))
    return new


def scrape(today):
    """Return ({source: records}, {source: error}, new City releases)."""
    results, errors = {}, {}
    try:
        results["dhl_stadium"] = dhl_stadium.fetch()
    except ScrapeError as e:
        errors["dhl_stadium"] = str(e)
    try:
        results["sportsdb"] = sportsdb.fetch(stormers_games(results.get("dhl_stadium", []), today))
    except ScrapeError as e:
        errors["sportsdb"] = str(e)
    try:
        new_releases = check_city_releases(today)
    except ScrapeError as e:
        errors["capetown_gov"], new_releases = str(e), []
    return results, errors, new_releases


def update_health(errors, counts, today):
    """Record each source's outcome in scrape_health.json.

    `counts` is {source: records returned} for the sources that ran OK.
    Returns the sources that have failed FAIL_DAYS days running (counted
    from the first failure, so several runs on one day count once).
    """
    health = read_json("scrape_health.json", {})
    failing = []
    for source in SOURCES:
        h = health.get(source, {"last_success": None, "events": None})
        if source in errors:
            since = h.get("failing_since") or today.isoformat()
            h = {**h, "error": errors[source], "failing_since": since}
            if (today - date.fromisoformat(since)).days >= FAIL_DAYS - 1:
                failing.append(source)
        else:
            h = {"last_success": today.isoformat(), "events": counts[source], "error": None, "failing_since": None}
        health[source] = h
    write_json("scrape_health.json", health)
    return failing


def report(results, errors, new_releases, today):
    for source, records in results.items():
        upcoming = [r for r in records if r["start"][:10] >= today.isoformat()]
        print(f"== {source}: {len(records)} events, {len(upcoming)} upcoming")
        for r in sorted(upcoming, key=lambda r: r["start"]):
            tbc = "" if r["time_confirmed"] else " (time TBC)"
            print(f"  {r['start'][:16]}{tbc}  {r['category_hint'] or '-':8} {r['name']}")
    print(f"== capetown_gov: {len(new_releases)} new releases to review")
    for r in new_releases:
        print(f"  {r['date']}  {r['title']}  [{', '.join(r['keywords'])}]")
    for source, error in errors.items():
        print(f"error: {error}")


def main():
    today = date.today()
    results, errors, new_releases = scrape(today)
    report(results, errors, new_releases, today)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
