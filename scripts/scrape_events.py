"""Run the event scrapers and print what they found.

DHL Stadium lists every event; TheSportsDB is then asked for the
kick-off of each upcoming Stormers game on those dates. Each source runs
independently: one failure never stops the other. Merging and writing
events.json come in Phase 8.

    python scripts/scrape_events.py
"""
import sys
from datetime import date

from scrapers import dhl_stadium, sportsdb
from scrapers.base import ScrapeError


def stormers_games(records, today):
    """(date, title) of each upcoming Stormers game listed by DHL Stadium."""
    return sorted((r["start"][:10], r["name"]) for r in records
                  if "stormers" in r["name"].lower() and r["start"][:10] >= today.isoformat())


def main():
    results, errors = {}, {}
    try:
        results["dhl_stadium"] = dhl_stadium.fetch()
    except ScrapeError as e:
        errors["dhl_stadium"] = str(e)
    try:
        results["sportsdb"] = sportsdb.fetch(stormers_games(results.get("dhl_stadium", []), date.today()))
    except ScrapeError as e:
        errors["sportsdb"] = str(e)

    for source, records in results.items():
        upcoming = [r for r in records if r["start"][:10] >= date.today().isoformat()]
        print(f"== {source}: {len(records)} events, {len(upcoming)} upcoming")
        for r in sorted(upcoming, key=lambda r: r["start"]):
            tbc = "" if r["time_confirmed"] else " (time TBC)"
            print(f"  {r['start'][:16]}{tbc}  {r['category_hint'] or '-':8} {r['name']}")
    for source, error in errors.items():
        print(f"error: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
