"""Merge the CSV and scraped records into data/events.json.

Matching (PLAN.md, Merging):
1. a record whose (source, source_id) is already linked to an event
   belongs to it, even if its date changed (reschedule);
2. otherwise same or overlapping dates AND token-set ratio >= 80.
Field priority: name/date CSV > DHL > TheSportsDB; time CSV > TheSportsDB
> DHL; category CSV > source label > keywords. Conflicts, ambiguous
matches, reschedules and unknown categories of upcoming events go to
needs_review.json. Events that no source lists any more become
"unconfirmed" if still upcoming (only when all their sources ran OK).
Exits 1 only when a source has failed 3 days running (scrape_health.json).

    python scripts/merge_events.py
"""
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from rapidfuzz import fuzz, utils

import classify
import load_manual
from scrape_events import FAIL_DAYS, add_review, read_json, report, scrape, update_health, write_json
from scrapers.base import DEFAULT_TIME, SAST

PRIORITY = ("csv", "dhl_stadium", "sportsdb")
TIME_PRIORITY = ("csv", "sportsdb", "dhl_stadium")
TIME_SOURCE = {"csv": "csv", "json": "dhl_stadium", "sportsdb": "sportsdb"}
DURATION = {"sport": timedelta(hours=2), "concert": timedelta(hours=4),
            "race": timedelta(hours=6), "parade": timedelta(hours=6)}
STADIUM = ("dhl", "cape town stadium")


def similar(a, b):
    return fuzz.token_set_ratio(a, b, processor=utils.default_process)


def days(rec):
    first = date.fromisoformat(rec["start"][:10])
    return first, date.fromisoformat(rec["end_date"]) if rec.get("end_date") else first


def overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


class Group:
    """One event: its previous version (if any) and today's records by source."""

    def __init__(self, prev=None):
        self.prev, self.records = prev, {}

    def ids(self):
        ids = dict(self.prev["source_ids"]) if self.prev else {}
        ids.update({s: r["source_id"] for s, r in self.records.items()})
        return ids

    def main(self):
        """Highest-priority record, or the previous event."""
        return next((self.records[s] for s in PRIORITY if s in self.records), self.prev)


def group_records(prev_events, records, review, today):
    groups = [Group(e) for e in prev_events]
    for rec in records:
        group = next((g for g in groups if g.ids().get(rec["source"]) == rec["source_id"]), None)
        if group is None:
            scored = sorted(((similar(g.main()["name"], rec["name"]), i) for i, g in enumerate(groups)
                             if rec["source"] not in g.ids() and overlaps(days(g.main()), days(rec))),
                            reverse=True)
            scored = [(score, i) for score, i in scored if score >= 80]
            if len(scored) > 1 and rec["start"][:10] >= today.isoformat():
                review.append({"type": "ambiguous_match", "event_id": None,
                               "detail": f"{rec['source']} '{rec['name']}' on {rec['start'][:10]} matches "
                                         f"{len(scored)} events"})
            group = groups[scored[0][1]] if scored else None
        if group is None:
            group = Group()
            groups.append(group)
        group.records[rec["source"]] = rec
    return groups


def build(group, closures, ok_sources, taken_ids, today, review):
    recs, prev = group.records, group.prev
    main = group.main()
    name = main["name"]
    first_day, last_day = days(main)
    upcoming = first_day >= today

    category = next((recs[s]["category_hint"] for s in PRIORITY if s in recs and recs[s]["category_hint"]), None) \
        or classify.category(name)
    timed = next((recs[s] for s in TIME_PRIORITY if s in recs and recs[s]["time_confirmed"]), None)
    if timed is None and prev and prev["time_confirmed"] and TIME_SOURCE.get(prev["time_source"]) not in ok_sources:
        timed = {"start": prev["start"], "time_source": prev["time_source"]}  # that source failed today
    start_time = datetime.fromisoformat(timed["start"]).timetz().replace(tzinfo=None) if timed \
        else DEFAULT_TIME.get(category, DEFAULT_TIME["sport"])
    start = datetime.combine(first_day, start_time, SAST)

    event_closures = [{k: c[k] for k in ("road", "from", "to", "source_url")} for c in closures
                      if first_day <= date.fromisoformat(c["event_date"]) <= last_day
                      and similar(c["event_name"], name) >= 80]
    end_rec = next((recs[s] for s in ("csv", "dhl_stadium") if s in recs and recs[s]["end"]), None)
    if end_rec:
        end_time = datetime.fromisoformat(end_rec["end"]).astimezone(SAST).time()
    elif category in ("race", "parade") and event_closures:
        end_time = max(datetime.fromisoformat(c["to"]) for c in event_closures).time()
    else:
        end_time = (start + DURATION.get(category, timedelta(hours=3))).time()
    end = datetime.combine(last_day, end_time, SAST)
    if end <= datetime.combine(last_day, start_time, SAST):
        end += timedelta(days=1)

    event_id = prev["id"] if prev else load_manual.slug(f"{first_day} {name}")
    if not prev:
        base, n = event_id, 2
        while event_id in taken_ids:
            event_id, n = f"{base}-{n}", n + 1
    taken_ids.add(event_id)

    rescheduled_from = prev.get("rescheduled_from") if prev else None
    if prev and prev["start"][:10] != start.date().isoformat():
        rescheduled_from = rescheduled_from or prev["start"][:10]
        review.append({"type": "rescheduled", "event_id": event_id,
                       "detail": f"{prev['start'][:10]} -> {start.date()}"})

    if upcoming and "csv" in recs:
        other = next((recs[s] for s in ("sportsdb", "dhl_stadium") if s in recs), None)
        if other and other["start"][:10] != recs["csv"]["start"][:10]:
            review.append({"type": "date_conflict", "event_id": event_id,
                           "detail": f"CSV {recs['csv']['start'][:10]}, {other['source']} {other['start'][:10]}"})
        other = next((recs[s] for s in ("sportsdb", "dhl_stadium") if s in recs and recs[s]["time_confirmed"]), None)
        if recs["csv"]["time_confirmed"] and other and other["start"][11:16] != recs["csv"]["start"][11:16]:
            review.append({"type": "time_conflict", "event_id": event_id,
                           "detail": f"CSV {recs['csv']['start'][11:16]}, {other['source']} {other['start'][11:16]}"})
    if upcoming and category == "unknown":
        review.append({"type": "unknown_category", "event_id": event_id, "detail": name})

    csv_rec = recs.get("csv", {})
    return {
        "id": event_id,
        "name": name,
        "start": start.isoformat(),
        "end_estimate": end.isoformat(),
        "end_date": last_day.isoformat() if last_day != first_day else None,
        "time_confirmed": timed is not None,
        "time_source": timed["time_source"] if timed else "default",
        "category": category,
        "size": csv_rec.get("size") or classify.size(category, name, csv_rec.get("crowd_hint")),
        "crowd_hint": csv_rec.get("crowd_hint"),
        "closures": event_closures,
        "sources": [s for s in PRIORITY if s in recs],
        "source_ids": dict(sorted(group.ids().items())),
        "status": "confirmed",
        "rescheduled_from": rescheduled_from,
        "override": "csv" in recs,
    }


def merge(prev_events, records, closures, ok_sources, today):
    """Return (events, review items). `records` must be in PRIORITY order of source."""
    review = []
    records = [r for r in records if r["source"] != "sportsdb"
               or any(v in (r["venue_text"] or "dhl").lower() for v in STADIUM)]
    groups = group_records(prev_events, records, review, today)
    taken = {g.prev["id"] for g in groups if g.prev}
    events = []
    for g in groups:
        if g.records:
            events.append(build(g, closures, ok_sources, taken, today, review))
            continue
        event = dict(g.prev)
        if (event["status"] != "cancelled" and event["start"][:10] >= today.isoformat()
                and all(s in ok_sources for s in event["sources"])):
            event["status"] = "unconfirmed"
        events.append(event)
    events.sort(key=lambda e: (e["start"], e["id"]))
    return events, review


def main():
    today = date.today()
    results, errors, new_releases = scrape(today)
    report(results, errors, new_releases, today)
    csv_records, closures = load_manual.load()
    records = csv_records + [r for s in PRIORITY[1:] for r in results.get(s, [])]
    ok_sources = {"csv", *results}
    events, review = merge(read_json("events.json", []), records, closures, ok_sources, today)
    write_json("events.json", events)
    new = add_review(review, today)
    upcoming = [e for e in events if e["start"][:10] >= today.isoformat()]
    print(f"== events.json: {len(events)} events, {len(upcoming)} upcoming, {len(new)} new review items")
    for e in upcoming:
        flags = "" if e["status"] == "confirmed" else f" [{e['status']}]"
        print(f"  {e['start'][:16]}-{e['end_estimate'][11:16]}  {e['category']:7} {e['size']:6} "
              f"{e['name']}  ({', '.join(e['sources'])}){flags}")
    for item in new:
        print(f"  review: {item['type']} {item.get('event_id') or ''} {item.get('detail') or item.get('title')}")
    if path := os.environ.get("NEW_REVIEW_FILE"):
        Path(path).write_text("".join(
            f"- {i['type']}: {i.get('event_id') or i.get('title')} {i.get('detail') or i.get('url') or ''}\n"
            for i in new_releases + new), encoding="utf-8")
    counts = {**{s: len(r) for s, r in results.items()}, "capetown_gov": len(new_releases)}
    failing = update_health(errors, counts, today)
    for source in failing:
        print(f"error: {source} has failed {FAIL_DAYS} days running (see data/scrape_health.json)")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
