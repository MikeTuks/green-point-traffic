"""Build the web page into _site/ for GitHub Pages.

    python scripts/build_site.py

Copies site/ and writes _site/data.json: upcoming events with, per
direction, the learned extra delay in 15-minute slots across the logging
window (start - 5 h to end + 3 h) and the stretches where the median is
BAD_MIN minutes or more. Only aggregated curves are published.
"""
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "_site"
SAST = timezone(timedelta(hours=2))
STEP = timedelta(minutes=15)
BEFORE, AFTER = timedelta(hours=5), timedelta(hours=3)
BAD_MIN = 2.0
ROUTES = ("outbound", "return")
SOURCE_NAMES = {"dhl_stadium": "DHL Stadium", "sportsdb": "TheSportsDB", "capetown_gov": "City of Cape Town"}


def hhmm(dt):
    return f"{dt:%H:%M}"


def first_day_times(event):
    """(start, end) on the first day; multi-day events repeat the same hours."""
    start = datetime.fromisoformat(event["start"])
    end_clock = datetime.fromisoformat(event["end_estimate"]).timetz()
    end = datetime.combine(start.date(), end_clock)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def lookup(curve, anchor, minutes):
    step = int(STEP.total_seconds() // 60)
    return curve[anchor].get(str(minutes // step * step))


def route_outlook(curve, start, end):
    if not curve:
        return {"games": 0}
    times, median, low, high = [], [], [], []
    t = start - BEFORE
    while t < end + AFTER:
        cells = [c for c in (lookup(curve, "arrival", int((t - start).total_seconds() // 60)) if t < start else None,
                             lookup(curve, "departure", int((t - end).total_seconds() // 60)) if t >= end else None)
                 if c]
        cell = max(cells, key=lambda c: c["median"], default=None)
        times.append(t)
        median.append(cell and cell["median"])
        low.append(cell and cell["low"])
        high.append(cell and cell["high"])
        t += STEP
    return {"games": curve["events"], "from": hhmm(times[0]), "median": median, "low": low, "high": high,
            "bad": bad_stretches(times, median)}


def bad_stretches(times, values):
    """[["18:45", "19:45"], ...] for runs of slots at or above BAD_MIN."""
    stretches, begin = [], None
    for t, v in zip(times + [None], values + [None]):
        if v is not None and v >= BAD_MIN:
            begin = begin or t
        elif begin:
            stretches.append([hhmm(begin), hhmm(prev + STEP)])
            begin = None
        prev = t
    return stretches


def page_event(event, curves):
    start, end = first_day_times(event)
    last = datetime.fromisoformat(event["end_date"]) if event.get("end_date") else start
    days = (last.date() - start.date()).days + 1
    outlook = None
    if event["time_confirmed"]:
        outlook = {r: route_outlook(curves.get(f"{event['category']}/{event['size']}/{r}"), start, end)
                   for r in ROUTES}
    return {
        "id": event["id"], "name": event["name"], "date": start.date().isoformat(), "days": days,
        "start": hhmm(start) if event["time_confirmed"] else None, "end": hhmm(end),
        "category": event["category"], "size": event["size"], "status": event["status"],
        "rescheduled_from": event.get("rescheduled_from"),
        "closures": [{"road": c["road"], "from": c["from"], "to": c["to"]} for c in event.get("closures", [])],
        "outlook": outlook,
    }


def build(events, curves, health, now):
    today = now.date().isoformat()
    upcoming = sorted((e for e in events if (e.get("end_date") or e["start"][:10]) >= today),
                      key=lambda e: e["start"])
    return {
        "updated": now.isoformat(timespec="minutes"),
        "sources": [{"name": SOURCE_NAMES.get(s, s), "ok": h.get("error") is None,
                     "failing_since": h.get("failing_since")} for s, h in health.items()],
        "events": [page_event(e, curves) for e in upcoming],
    }


def read(name, default):
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main():
    data = build(read("events.json", []), read("curves.json", {}).get("curves", {}),
                 read("scrape_health.json", {}), datetime.now(SAST))
    shutil.copytree(ROOT / "site", OUT, dirs_exist_ok=True)
    (OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"_site: {len(data['events'])} upcoming events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
