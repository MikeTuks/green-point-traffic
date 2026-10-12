"""Phase 0 traffic logger.

Runs every 15 minutes from GitHub Actions. Exits quietly unless an event
window, closure window or control-day window is active (or --force).
Events come from data/events.json (written daily by merge_events.py), or
from events_manual.csv if that file does not exist yet.
Each reading is encrypted on its own with the public age key and
appended as one base64 line to data/traffic/YYYY-MM.jsonl.age, so the
logger never needs the private key.

    python scripts/log_traffic.py --check   # print active window, no API calls
    python scripts/log_traffic.py           # log if a window is active
    python scripts/log_traffic.py --force   # log now regardless
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SAST = timezone(timedelta(hours=2))  # Africa/Johannesburg has no DST

DEFAULT_TIME = {"sport": time(16, 0), "concert": time(18, 0), "race": time(6, 0), "parade": time(6, 0)}
DURATION = {"sport": timedelta(hours=2), "concert": timedelta(hours=4), "race": timedelta(hours=6), "parade": timedelta(hours=6)}
BEFORE, AFTER = timedelta(hours=5), timedelta(hours=3)
TBC_WINDOW = (time(10, 0), time(23, 0))
CONTROL_WINDOW = (time(10, 0), time(23, 0))
DIRECTIONS = ("outbound", "return")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def read_csv(name):
    path = DATA / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def at(day, t):
    return datetime.combine(day, t, tzinfo=SAST)


def event_windows(rows):
    """One window per event day: start - 5 h to end + 3 h (10:00-23:00 if time TBC).

    End is end_time if given, else start + the category's default duration.
    """
    windows = []
    for row in rows:
        first = date.fromisoformat(row["date"])
        last = date.fromisoformat(row["end_date"]) if row.get("end_date") else first
        category = row.get("category") or "sport"
        event_id = row.get("event_id") or f"{first.isoformat()}-{slug(row['name'])}"
        day = first
        while day <= last:
            start = at(day, time.fromisoformat(row["time"]) if row.get("time")
                       else DEFAULT_TIME.get(category, time(16, 0)))
            if row.get("end_time"):
                end = at(day, time.fromisoformat(row["end_time"]))
            else:
                end = start + DURATION.get(category, timedelta(hours=3))
            if end <= start:  # ends after midnight
                end += timedelta(days=1)
            if row.get("time"):
                win = (start - BEFORE, end + AFTER)
            else:
                win = (at(day, TBC_WINDOW[0]), at(day, TBC_WINDOW[1]))
            windows.append({"kind": "event", "event_id": event_id, "from": win[0], "to": win[1],
                            "start": start, "end": end})
            day += timedelta(days=1)
    return windows


def json_rows(events):
    """events.json events as event_windows() rows (start/end times apply to each day)."""
    rows = []
    for e in events:
        if e["status"] == "cancelled":
            continue
        start, end = datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end_estimate"])
        rows.append({"event_id": e["id"], "name": e["name"], "date": start.date().isoformat(),
                     "end_date": e.get("end_date") or "", "time": f"{start:%H:%M}" if e["time_confirmed"] else "",
                     "end_time": f"{end:%H:%M}", "category": e["category"]})
    return rows


def closure_windows(rows):
    windows = []
    for row in rows:
        event_id = f"{row['event_date']}-{slug(row['event_name'])}"
        start = datetime.fromisoformat(row["from"]).replace(tzinfo=SAST)
        end = datetime.fromisoformat(row["to"]).replace(tzinfo=SAST)
        windows.append({"kind": "closure", "event_id": event_id, "from": start, "to": end,
                        "start": start, "end": end})
    return windows


def control_windows(rows, event_days):
    """Control days on which an event also happens are skipped."""
    windows = []
    for row in rows:
        day = date.fromisoformat(row["date"])
        if day in event_days:
            continue
        start = at(day, time.fromisoformat(row["start"]) if row.get("start") else CONTROL_WINDOW[0])
        end = at(day, time.fromisoformat(row["end"]) if row.get("end") else CONTROL_WINDOW[1])
        windows.append({"kind": "control", "event_id": None, "from": start, "to": end,
                        "start": None, "end": None})
    return windows


def active_window(now):
    """Return the active window, preferring events, then closures, then control days."""
    path = DATA / "events.json"
    if path.exists():
        events = event_windows(json_rows(json.loads(path.read_text(encoding="utf-8"))))
    else:
        events = event_windows(read_csv("events_manual.csv"))
    closures = closure_windows(read_csv("closures_manual.csv"))
    event_days = {w["start"].date() for w in events + closures}
    controls = control_windows(read_csv("control_days.csv"), event_days)
    for w in events + closures + controls:
        if w["from"] <= now <= w["to"]:
            return w
    return None


def minutes_between(a, b):
    return None if a is None else round((b - a).total_seconds() / 60)


def append_encrypted(record, now):
    from pyrage import encrypt, x25519

    recipient = x25519.Recipient.from_str((DATA / "age_recipient.txt").read_text().strip())
    line = base64.b64encode(encrypt(json.dumps(record).encode(), [recipient])).decode()
    path = DATA / "traffic" / f"{now:%Y-%m}.jsonl.age"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="ascii") as f:
        f.write(line + "\n")


def log_readings(window, now):
    from tomtom import TomTomError, calculate_route, route_points

    api_key = os.environ["TOMTOM_API"]
    home, dest = os.environ["TOMTOM_HOME"], os.environ["TOMTOM_DEST"]
    waypoints = {"outbound": os.environ["TOMTOM_OUT_WAYPOINTS"], "return": os.environ["TOMTOM_RET_WAYPOINTS"]}

    failures = 0
    for direction in DIRECTIONS:
        try:
            result = calculate_route(api_key, route_points(home, dest, waypoints[direction], direction), direction)
        except TomTomError as e:
            print(f"error: {e}")
            failures += 1
            continue
        record = {
            "ts": now.isoformat(timespec="seconds"),
            "route": direction,
            "event_id": window["event_id"] if window else None,
            "control_day": bool(window and window["kind"] == "control"),
            "window": window["kind"] if window else "forced",
            "min_from_start": minutes_between(window and window["start"], now),
            "min_from_end": minutes_between(window and window["end"], now),
            **result,
        }
        append_encrypted(record, now)
        print(f"{direction}: {result['status']}")
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="only report whether a window is active")
    parser.add_argument("--force", action="store_true", help="log even if no window is active")
    args = parser.parse_args()

    now = datetime.now(SAST)
    window = active_window(now)
    active = window is not None or args.force
    label = f"{window['kind']} {window['event_id'] or ''}".strip() if window else ("forced" if args.force else "none")
    print(f"{now:%Y-%m-%d %H:%M} SAST, window: {label}")

    if args.check:
        if out := os.environ.get("GITHUB_OUTPUT"):
            with open(out, "a") as f:
                f.write(f"active={'true' if active else 'false'}\n")
        return 0
    if not active:
        return 0
    return 1 if log_readings(window, now) == len(DIRECTIONS) else 0


if __name__ == "__main__":
    sys.exit(main())
