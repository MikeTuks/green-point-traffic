"""Shared helpers for the event scrapers.

Each scraper returns records in the common format (PLAN.md, Scraper
design). A ScrapeError means the source changed shape or could not be
reached (a structural failure); an empty list is a normal result.
"""
import time as _time
from datetime import datetime, time, timedelta, timezone

import requests

SAST = timezone(timedelta(hours=2))  # Africa/Johannesburg has no DST
USER_AGENT = "green-point-traffic/0.1 (+https://github.com/MikeTuks/green-point-traffic)"
TIMEOUT, RETRIES = 20, 2
DEFAULT_TIME = {"sport": time(16, 0), "concert": time(18, 0), "race": time(6, 0), "parade": time(6, 0)}


class ScrapeError(Exception):
    pass


def get_json(url, params=None):
    """GET a JSON document, retrying twice with backoff."""
    return _get(url, params, lambda resp: resp.json())


def get_html(url, params=None):
    return _get(url, params, lambda resp: resp.text)


def _get(url, params, decode):
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            resp.raise_for_status()
            return decode(resp)
        except (requests.RequestException, ValueError) as e:
            if attempt == RETRIES:
                raise ScrapeError(f"{url}: {type(e).__name__}") from None
            _time.sleep(5 * 2 ** attempt)


def utc_to_sast(text):
    """'2026-10-17T14:15:00.000Z' (or a naive UTC timestamp) -> aware SAST datetime."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST)


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
