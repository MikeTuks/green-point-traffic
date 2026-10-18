"""City of Cape Town media releases: flag only.

Each release not seen before is fetched once; if its title or text
mentions a Green Point road or place and a closure, it is returned for needs_review
(you copy any closures into the CSVs by hand). Nothing here creates or
changes events. The listing covers about two months and has no paging.
"""
import time
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import ScrapeError, get_html

LISTING = "https://web1.capetown.gov.za/web1/newsandnotices/Home/Releases"
PARAMS = {"category": "Media releases"}
KEYWORDS = ("green point", "dhl stadium", "cape town stadium", "fritz sonnenberg", "somerset road",
            "beach road", "mouille point", "helen suzman", "vlei road", "fan walk")
CLOSURE_WORDS = ("road closure", "closures", "closed to traffic", "detour", "traffic diversion")
PAUSE = 1.0


def parse_listing(html):
    """[{'url', 'title', 'date'}] for each release card, newest first."""
    cards = BeautifulSoup(html, "html.parser").select("article.media-release-card")
    if not cards:
        raise ScrapeError("capetown_gov: no release cards in listing")
    releases = []
    for card in cards:
        link, day = card.select_one("a.media-release-title"), card.select_one(".media-release-date")
        if not link or not link.get("href") or not day:
            raise ScrapeError("capetown_gov: release card without title link or date")
        url = urljoin(LISTING, urlsplit(link["href"]).path)  # drop ?category=
        date = datetime.strptime(day.get_text(strip=True), "%d %B %Y").date().isoformat()
        releases.append({"url": url, "title": link.get_text(" ", strip=True), "date": date})
    return releases


def release_text(html):
    body = BeautifulSoup(html, "html.parser").select_one("article.content")
    if body is None:
        raise ScrapeError("capetown_gov: release page without article.content")
    return body.get_text(" ", strip=True)


def matches(text):
    """Green Point keywords in the text, or [] if it says nothing about closures."""
    text = text.lower()
    if not any(w in text for w in CLOSURE_WORDS):
        return []
    return sorted(k for k in KEYWORDS if k in text)


def fetch(seen):
    """Return (flagged releases, URLs now seen). `seen` is a set of URLs."""
    releases = parse_listing(get_html(LISTING, PARAMS))
    flagged, seen = [], set(seen)
    for i, r in enumerate(x for x in releases if x["url"] not in seen):
        if i:
            time.sleep(PAUSE)
        hits = matches(r["title"] + " " + release_text(get_html(r["url"])))
        if hits:
            flagged.append({**r, "keywords": hits})
        seen.add(r["url"])
    return flagged, seen
