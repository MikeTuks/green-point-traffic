"""Load the hand-edited CSVs as common records (source "csv") and closures.

Blank CSV fields are left for the other sources and the classifier to
fill; filled fields override them in merge_events.py.
"""
import csv
import re
from datetime import date, datetime, time
from pathlib import Path

from scrapers.base import DEFAULT_TIME, SAST

DATA = Path(__file__).resolve().parent.parent / "data"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def read_csv(name):
    path = DATA / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def event_records(rows):
    records = []
    for row in rows:
        day = date.fromisoformat(row["date"])
        category = row.get("category") or None
        confirmed = bool(row.get("time"))
        t = time.fromisoformat(row["time"]) if confirmed else DEFAULT_TIME.get(category, DEFAULT_TIME["sport"])
        end = datetime.combine(day, time.fromisoformat(row["end_time"]), SAST) if row.get("end_time") else None
        records.append({
            "source": "csv",
            "source_id": f"{row['date']}-{slug(row['name'])}",
            "name": row["name"],
            "start": datetime.combine(day, t, SAST).isoformat(),
            "end": end.isoformat() if end else None,
            "end_date": row.get("end_date") or None,
            "time_confirmed": confirmed,
            "time_source": "csv" if confirmed else "default",
            "venue_text": None,
            "category_hint": category,
            "size": row.get("size") or None,
            "crowd_hint": int(row["crowd"]) if row.get("crowd") else None,
            "url": None,
            "fetched_at": None,
        })
    return records


def closure_rows(rows):
    return [{"event_date": r["event_date"], "event_name": r["event_name"], "road": r["road"],
             "from": datetime.fromisoformat(r["from"]).replace(tzinfo=SAST).isoformat(),
             "to": datetime.fromisoformat(r["to"]).replace(tzinfo=SAST).isoformat(),
             "source_url": r.get("source_url") or None} for r in rows]


def load():
    """(event records, closures) from events_manual.csv and closures_manual.csv."""
    return event_records(read_csv("events_manual.csv")), closure_rows(read_csv("closures_manual.csv"))
