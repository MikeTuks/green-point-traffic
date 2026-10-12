"""DHL Stadium events from the site's public Strapi API.

Times in the API are UTC; the website shows them unconverted, which is
why its "Starts" field looks 2 h early. Even converted, some rugby
kick-offs are 1 h out (checked 12 Oct 2026), so Stormers times come from
sportsdb.py. Midnight SAST is treated as a "time TBC" placeholder.
"""
from datetime import datetime

from .base import DEFAULT_TIME, ScrapeError, get_json, now_utc, utc_to_sast

URL = "https://api.dhlstadium.co.za/api/events"
PARAMS = {"pagination[pageSize]": 100, "populate[event][populate][0]": "daterange"}
CATEGORY = {"Sporting": "sport", "Concerts": "concert"}


def parse(data, fetched_at):
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ScrapeError("dhl_stadium: no 'data' list")
    if data.get("meta", {}).get("pagination", {}).get("pageCount", 1) > 1:
        raise ScrapeError("dhl_stadium: more than one page of events")
    records = []
    for item in data["data"]:
        try:
            attrs = item["attributes"]
            ranges = sorted((dr for ev in attrs["event"] or [] for dr in ev["daterange"] or [] if dr.get("start")),
                            key=lambda dr: dr["start"])
            name = attrs["title"].strip()
        except (KeyError, TypeError) as e:
            raise ScrapeError(f"dhl_stadium: event {item.get('id')}: missing {e}") from None
        if not ranges:
            continue
        category = CATEGORY.get(attrs.get("category"))
        start = utc_to_sast(ranges[0]["start"])
        confirmed = (start.hour, start.minute) != (0, 0)
        if not confirmed:
            start = datetime.combine(start.date(), DEFAULT_TIME.get(category, DEFAULT_TIME["sport"]), start.tzinfo)
        last_day = utc_to_sast(ranges[-1]["start"]).date()
        end = ranges[-1].get("end")
        records.append({
            "source": "dhl_stadium",
            "source_id": f"event-{item['id']}",
            "name": name,
            "start": start.isoformat(),
            "end": utc_to_sast(end).isoformat() if end else None,
            "end_date": last_day.isoformat() if last_day != start.date() else None,
            "time_confirmed": confirmed,
            "time_source": "json" if confirmed else "default",
            "venue_text": "DHL Stadium",
            "category_hint": category,
            "crowd_hint": None,
            "url": "https://dhlstadium.co.za/events",
            "fetched_at": fetched_at,
        })
    return records


def fetch():
    return parse(get_json(URL, PARAMS), now_utc())
