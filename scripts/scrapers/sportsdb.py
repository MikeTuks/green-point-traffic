"""Stormers home kick-off times from TheSportsDB (free API key).

The Stormers site's terms forbid automated access, so kick-offs come
from TheSportsDB instead. The free key caps every query (3 events per
day-and-league, 1 per search, 1 for "next home game"), so for each
upcoming Stormers date from DHL Stadium:
1. ask that day once per league;
2. if the game is still missing (busy Champions Cup days), search
   "Stormers vs <word>" for each word of the opponent's name and keep a
   hit only if its date matches.
The team's next home game is also asked for, which catches games DHL
does not list. Anything still missing keeps its DHL time.
"""
import time
from datetime import date

from .base import ScrapeError, get_json, now_utc, utc_to_sast

BASE = "https://www.thesportsdb.com/api/v1/json/123"
TEAM_ID = "136670"  # Stormers
LEAGUES = ("4446", "4550")  # URC, Champions Cup
PAUSE = 2.5  # free limit is 30 requests a minute


def parse_events(data, key, fetched_at):
    """Stormers home games in one response; `key` is 'events' or 'event'."""
    if not isinstance(data, dict) or key not in data:
        raise ScrapeError(f"sportsdb: no '{key}' key")
    records = []
    for e in data[key] or []:
        if e.get("idHomeTeam") != TEAM_ID or not e.get("strTimestamp"):
            continue
        try:
            start = utc_to_sast(e["strTimestamp"])
            event_id, name = e["idEvent"], e["strEvent"]
        except (KeyError, ValueError):
            raise ScrapeError(f"sportsdb: event {e.get('idEvent')}: bad fields") from None
        records.append({
            "source": "sportsdb",
            "source_id": event_id,
            "name": name,
            "start": start.isoformat(),
            "end": None,
            "end_date": None,
            "time_confirmed": True,
            "time_source": "sportsdb",
            "venue_text": e.get("strVenue"),
            "category_hint": "sport",
            "crowd_hint": None,
            "url": f"https://www.thesportsdb.com/event/{event_id}",
            "fetched_at": fetched_at,
        })
    return records


def season(day):
    """'2027-01-16' -> '2026-2027' (seasons run August to July)."""
    d = date.fromisoformat(day)
    first = d.year if d.month >= 8 else d.year - 1
    return f"{first}-{first + 1}"


def opponent_words(title):
    """'DHL Stormers vs Vodacom Bulls' -> ['Vodacom', 'Bulls']."""
    return title.split(" vs ", 1)[-1].split()[:3]


def fetch(games):
    """`games`: (date 'YYYY-MM-DD', DHL title) per upcoming Stormers home game."""
    fetched_at, found, calls = now_utc(), {}, 0

    def ask(endpoint, params, key):
        nonlocal calls
        if calls:
            time.sleep(PAUSE)
        calls += 1
        for r in parse_events(get_json(f"{BASE}/{endpoint}", params), key, fetched_at):
            found[r["source_id"]] = r

    ask("eventsnext.php", {"id": TEAM_ID}, "events")
    for day in sorted({d for d, _ in games}):
        for league in LEAGUES:
            ask("eventsday.php", {"d": day, "l": league}, "events")
    for day, title in games:
        for word in opponent_words(title):
            if any(r["start"][:10] == day for r in found.values()):
                break
            before = dict(found)
            ask("searchevents.php", {"e": f"Stormers_vs_{word}", "s": season(day)}, "event")
            found = {k: r for k, r in found.items() if k in before or r["start"][:10] == day}
    return list(found.values())
