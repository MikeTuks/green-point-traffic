"""Learn event delay curves from the traffic log (Phase 10).

    python scripts/learn.py [--key age-key.txt]

Decrypts data/traffic/*.jsonl.age and writes data/curves.json: for each
category/size/direction, the median extra delay (minutes) in 15-minute
steps before the start (arrival), from the start until the end (during)
and after the end (departure), with the
lowest and highest event and the number of events. Extra delay is
live - historic, minus the control-day median for that direction and hour.
"""
import argparse
import base64
import json
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import median

from pyrage import decrypt

from decrypt_log import load_identity

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STEP = 15
ARRIVAL = (-300, 0)  # minutes from start
DURING = (0, 24 * 60)  # minutes from start, until the end
DEPARTURE = (0, 180)  # minutes from end


def read_readings(paths, identity):
    readings = []
    for path in paths:
        for line in Path(path).read_text(encoding="ascii").splitlines():
            if line.strip():
                readings.append(json.loads(decrypt(base64.b64decode(line), [identity])))
    return [r for r in readings if r["status"] == "ok" and r["live_s"] and r["historic_s"]]


def hour_key(r):
    return r["route"], datetime.fromisoformat(r["ts"]).hour


def corrections(readings):
    """Median live - historic (seconds) on control days, per direction and hour."""
    groups = {}
    for r in readings:
        if r["control_day"]:
            groups.setdefault(hour_key(r), []).append(r["live_s"] - r["historic_s"])
    return {k: median(v) for k, v in groups.items()}


def extra_delay(r, corr):
    return (r["live_s"] - r["historic_s"] - corr.get(hour_key(r), 0)) / 60


def bin_of(minutes, span):
    if minutes is None or not span[0] <= minutes < span[1]:
        return None
    return minutes // STEP * STEP


def learn(readings, events):
    """Return {"category/size/route": {"events": n, "arrival": {...}, "departure": {...}}}."""
    corr = corrections(readings)
    by_id = {e["id"]: e for e in events}
    per_event = {}  # (key, anchor, bin) -> {event_id: [delays]}
    for r in readings:
        e = by_id.get(r["event_id"])
        if r["window"] != "event" or e is None:
            continue
        key = f"{e['category']}/{e['size']}/{r['route']}"
        during = r["min_from_end"] is not None and r["min_from_end"] < 0
        for anchor, minutes, span in (("arrival", r["min_from_start"], ARRIVAL),
                                      ("during", r["min_from_start"] if during else None, DURING),
                                      ("departure", r["min_from_end"], DEPARTURE)):
            b = bin_of(minutes, span)
            if b is not None:
                per_event.setdefault((key, anchor, b), {}).setdefault(e["id"], []).append(extra_delay(r, corr))

    curves = {}
    for (key, anchor, b), by_event in sorted(per_event.items()):
        values = [median(v) for v in by_event.values()]
        curve = curves.setdefault(key, {"events": set(), "arrival": {}, "during": {}, "departure": {}})
        curve["events"].update(by_event)
        curve[anchor][str(b)] = {"median": round(median(values), 1), "low": round(min(values), 1),
                                 "high": round(max(values), 1), "n": len(values)}
    for curve in curves.values():
        curve["events"] = len(curve["events"])
    return curves


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default="age-key.txt")
    args = parser.parse_args()

    readings = read_readings(sorted((DATA / "traffic").glob("*.jsonl.age")), load_identity(args.key))
    events = json.loads((DATA / "events.json").read_text(encoding="utf-8"))
    curves = learn(readings, events)
    out = {"generated": date.today().isoformat(), "control_readings": sum(r["control_day"] for r in readings),
           "curves": curves}
    (DATA / "curves.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for key, c in curves.items():
        peak = max(c["departure"].values(), key=lambda x: x["median"], default=None)
        print(f"{key}: {c['events']} events, departure peak {peak['median'] if peak else '-'} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
