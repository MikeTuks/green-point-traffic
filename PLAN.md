# Green Point Event Traffic App: Plan (v5)

*v5 incorporates the review of 10 Oct 2026. Main changes:*
- *New **Phase 0**: a minimal traffic logger runs first, fed by the CSV,
  because missed traffic days can never be recovered (events can).*
- *Scraper scope cut: Ticketmaster dropped; City releases are flagged for
  review instead of parsed; closures are entered by hand in a CSV
  (`closure_pdf.py` removed).*
- *GitHub Actions fixed: separate concurrency groups, push retry, commit
  only on change, `data/raw/` no longer committed, heartbeat now needed.*
- *Repo is public; the raw traffic log is encrypted before commit.*
- *Routes are pinned with waypoints; URLs never logged.*
- *Delay model: arrival anchored to start, departure anchored to end,
  separate shapes per category and direction, starter magnitudes defined.*
- *Merge, classifier and health-check bugs fixed.*

## Goal
A free web app that shows upcoming events at and around DHL Stadium
(Green Point), labels each one (sport, concert, race, parade, other), and
predicts when traffic near home will get bad and when it will clear.
Predictions improve over time by learning from real event days.

**Build order:** a minimal traffic logger first (Phase 0, by 17 Oct), then
the event scraper, then predictions and the web app. Events can be added
to the CSV after the fact; traffic readings cannot.

## Constraints
- Must be 100% free (no paid hosting, no credit card).
- Phone-friendly, installable as a home-screen web app.
- Low maintenance: runs on its own once set up.
- No calendar accounts. Events come from scrapers, plus CSVs edited in
  GitHub as backup and override.

## Tech stack (all free)
| Part            | Tool                                              |
|-----------------|---------------------------------------------------|
| Hosting         | GitHub Pages (deployed from the daily workflow)   |
| Repo            | **Public** (unlimited Actions minutes)            |
| Scheduled jobs  | GitHub Actions (cron, UTC, off-the-hour minutes)  |
| Scripts         | Python 3                                          |
| Scraping        | requests + BeautifulSoup; Playwright only if needed |
| Fuzzy matching  | rapidfuzz                                         |
| Traffic data    | TomTom Routing API (free: 20,000 requests/month)  |
| Log encryption  | `age` (key in GitHub Secrets)                     |
| Charts          | Chart.js                                          |
| Alerts          | GitHub failure emails + ntfy (with account token) |
| Storage         | CSV/JSON(L) files in the repo                     |

A private repo is not an option: the logging cron runs ~2,900 jobs a
month, each billed as at least 1 minute, against 2,000 free minutes.

## Event sources

### Overview
| # | Source                              | Method            | Covers                              | Role |
|---|-------------------------------------|-------------------|-------------------------------------|------|
| 1 | DHL Stadium events                  | Hidden JSON / Playwright | Everything at the stadium    | Primary (dates, titles; times if JSON is UTC-correct) |
| 2 | Stormers tickets hub / match centre | WordPress JSON or HTML | Stormers home games, kick-offs | Primary (rugby times) |
| 3 | City of Cape Town media releases    | HTML listing, keyword filter | Races, parades, closures | **Flag only** → needs-review + alert |
| 4 | Manual CSVs (events + closures)     | Edited in GitHub  | Recurring events, closures, overrides | Backbone |
| – | Promoters (Big Concerts etc.)       | Manual check      | Concert announcements               | Manual only |
| – | Ticketmaster Discovery API          | —                 | —                                   | **Dropped** (SA events sold via partner/white-label shops) |
| – | Songkick                            | —                 | —                                   | **Dropped** (no new API keys) |
| – | Closure PDF parsing                 | —                 | —                                   | **Dropped** (3–5 PDFs a year, changing layouts; typed into CSV instead) |

### 1. DHL Stadium events
- `dhlstadium.co.za/events` is a JavaScript single-page app; the raw HTML
  is an empty shell. Find the JSON endpoint behind it via DevTools →
  Network → Fetch/XHR and call it directly. Playwright is the fallback.
- Lists Stormers (URC, Champions Cup, Currie Cup), Springbok tests,
  touring matches, HSBC SVNS, Bafana friendlies and concerts (Concerts
  tab). Detail pages contain FAQs with gate times, kick-off, shuttles and
  road closures.
- **The "Starts" field looks shifted** (Stormers v Bristol "14:15" for a
  16:15 kick-off; Boks v All Blacks "15:10" for 17:10). Exactly 2 h in
  both cases suggests UTC shown as local time. **First check the raw
  JSON:** if it holds a UTC timestamp, parse it with the timezone and DHL
  becomes a reliable time source. Otherwise take times from Stormers or
  the detail-page FAQ. Either way, keep a fixture test against known
  kick-offs.
- Check `/robots.txt` and the site terms before scraping.

### 2. Stormers tickets hub / match centre
- Official home fixtures with kick-off times. About 14 home dates a season
  (9 URC, 2 Champions Cup pool, 3 Currie Cup).
- The site runs on WordPress: try `/wp-json/` for structured data,
  otherwise parse the tickets-hub HTML. No official `.ics` was found.
- Keep home games at DHL Stadium only.

### 3. City of Cape Town media releases (flag only)
- Listing at `web1.capetown.gov.za/web1/newsandnotices/` (category: Media
  releases). No RSS found; scrape the listing daily.
- Keep releases mentioning: Green Point, DHL Stadium, Cape Town Stadium,
  Fritz Sonnenberg, Somerset Road, Beach Road, Mouille Point, Helen Suzman,
  Green Point Main Road, Vlei Road, Fan Walk.
- **No date/closure extraction.** Each new matching release goes to
  `needs_review.json` (title, date, URL) and triggers an alert. You copy
  any closures and crowd numbers into the CSVs by hand.
- Seen release URLs are stored so each one alerts only once.

### 4. Manual CSVs
`data/events_manual.csv`:

    name,date,end_date,time,category,size,crowd
    HSBC SVNS Cape Town,2026-12-05,2026-12-06,08:00,sport,big,
    Cape Town Marathon,2027-05-22,2027-05-23,06:00,race,big,44500

`data/closures_manual.csv` (one row per road closure, from organiser
PDFs or City releases):

    event_date,event_name,road,from,to,source_url
    2026-09-12,Gun Run,Fritz Sonnenberg Rd,2026-09-12T03:00,2026-09-12T12:00,<pdf url>

- Blank fields = filled by sources/classifier; filled fields override,
  **but a conflict with a primary source is flagged in `needs_review`**
  (e.g. CSV says 16:15, Stormers now says 15:00), so stale overrides
  don't win silently.
- Closure rows attach to the event matched by date + name.
- A monthly reminder prompts a quick check.

### Annual events list (seed rows for the CSV)
| Event | Usual timing | Green Point impact (verified 2026) |
|---|---|---|
| Cape Town Street Parade | Early Jan (5 Jan 2026) | 2026 route via Somerset Rd into the stadium; closures 06:00–21:00. **Route contested; check each year.** |
| Cape Town Pride | Late Feb (28 Feb 2026) | De Waterkant → Somerset Rd → Green Point Track; Mardi Gras 11:00–21:00 |
| Cape Town Cycle Tour | Early March (5–8 Mar 2026) | **4-day event:** expo at DHL Stadium Thu–Sat (~35k visitors); Fritz Sonnenberg Rd closed Thu 06:00 to Sun 21:00; Beach Rd closed 05:00–18:30 on race day (~30k cyclists) |
| Cape Town Marathon | Late May (23–24 May 2026; first edition as an Abbott World Major on 23 May 2027) | Start Fritz Sonnenberg Rd and Beach Rd (Mouille Point), finish Vlei Rd; ~44,500 participants over the weekend; expect growth |
| Gun Run | Mid-Sept (12–13 Sep 2026) | Starts on Fritz Sonnenberg Rd (closed 03:00–12:00 both days); Beach Rd and Somerset Rd restrictions; ~21,000 participants |
| HSBC SVNS Cape Town | Early Dec (5–6 Dec 2026) | 2-day tournament, from 08:00 |
| Run Your City Cape Town 10K | May | **Low relevance:** Milnerton → CBD, not Green Point. 2026 race was cancelled due to weather. Keep only as a note. |

Also expected each year but not on a fixed date (come from sources 1–3):
Springbok tests, touring matches, Bafana Bafana friendlies, Currie Cup and
U20 games, stadium concerts and festivals (e.g. Calabash).

## Scraper design

### Common record
    {
      "source": "dhl_stadium",
      "source_id": "event-12",
      "name": "Springboks vs All Blacks",
      "start": "2026-08-29T17:10:00+02:00",
      "end": null,
      "time_confirmed": true,
      "time_source": "faq",            // json | faq | stormers | csv | default
      "venue_text": "DHL Stadium",
      "category_hint": "sport",
      "crowd_hint": 55000,
      "url": "https://...",
      "fetched_at": "2026-10-10T04:17:00Z"
    }

Closures come from `closures_manual.csv` and are attached at merge time
with full timestamps, so multi-day closures (Cycle Tour) work.

### Shared behaviour (`scrapers/base.py`)
- Descriptive User-Agent, 20 s timeout, 2 retries with backoff, one run
  per source per day.
- Raw pages cached for debugging via `actions/cache` / uploaded artifacts
  (short retention), **not committed**.
- All times in `Africa/Johannesburg`, ISO 8601 with `+02:00`.
- Date only → `time_confirmed: false`, default (sport 16:00, concert
  18:00, race 06:00), shown as "time TBC".
- Each scraper runs independently; one failure never stops the others.

### Merging (`merge_events.py`)
Match order:
1. Same `(source, source_id)` as a known event → same event, **even if
   the date changed** (reschedule: date updated, ID kept, change noted).
2. Same date (or overlapping date range for multi-day events) **and**
   rapidfuzz token-set ratio ≥ 80. Overlap alone never matches, so a
   multi-day CSV row can't absorb a separate event inside its range.
3. City releases never create or merge events; they only feed review.

Note: token-set ratio is 100 when one name's words are a subset of the
other's ("Stormers" vs "Stormers v Bulls"). At one venue that's
acceptable; two different events matching on the same day go to review.

Field priority:
- name, date: CSV > DHL Stadium > Stormers
- **time: CSV > Stormers > DHL JSON (if UTC-correct) > DHL FAQ > DHL "Starts"**
- crowd, closures: CSV > DHL FAQ
- category: CSV > source label > keyword classifier

Other rules:
- Stable IDs `YYYY-MM-DD-slug`, assigned once and never regenerated (the
  date in an ID is the original date, not necessarily the current one).
- A **future** event that vanishes from all sources → `status:
  "unconfirmed"`. Past events dropping off listings is normal; they keep
  their status. Cancelled → `"cancelled"`.

### Health checks
- `scrape_health.json`: last success, event count, error per source.
- Failure = **structural**: HTTP error, expected JSON key or HTML element
  missing, parse exception. Zero results is not a failure (normal for City
  most days, and for DHL in the off-season).
- Structural failure 3 days running → the workflow **fails** (GitHub
  emails you) and ntfy is tried as well.
- Fixture tests in `tests/fixtures/`, including a kick-off time check
  against known Stormers fixtures.

## Traffic measurement

### Route
- **Decided:** one route between the home end (on Beach Rd, by the beach)
  and the destination (a gym across town), in both directions:
  `outbound` = home → destination, `return` = destination → home. Exact
  points are kept out of this file and stored in GitHub Secrets
  (`TOMTOM_HOME`, `TOMTOM_DEST`).
- Each direction is pinned through two waypoints: Helen Suzman Blvd
  (past the stadium) and the N1 (near Paarden Eiland). Without pinning,
  TomTom reroutes around jams on bad days and understates the delay.
  Both roads are dual carriageways, so each direction has its own points
  on its own carriageway (taken from OpenStreetMap), stored in Secrets
  (`TOMTOM_OUT_WAYPOINTS`, `TOMTOM_RET_WAYPOINTS`). Phase 0 checks with
  one test call per direction that TomTom snaps them to the right side.
- **Home end is on Beach Rd, which races close** (Cycle Tour race day
  05:00–18:30; Gun Run and Marathon restrictions). TomTom may then return
  no route or a long detour. Log these as `status: "no_route"` (or
  `"detour"`) readings instead of failing, and treat closure windows as
  "bad" regardless.
- Alternative considered: TomTom Traffic Flow Segment Data on 2–4 road
  points. It measures "near home" directly, but has no historic value, so
  the baseline method below wouldn't apply. Revisit if pinned routes are
  noisy.

### Readings
- One Calculate Route call per direction per reading, with
  `computeTravelTimeFor=all` and live traffic. Returns live, historic and
  no-traffic travel times, so the baseline comes from the same call.
- `departAt` is only used for morning forecasts on event days.

### Security (public repo, public Actions logs)
- `tomtom.py` never prints request URLs: the coordinates are in the path
  and the key in the query string. Catch `requests` exceptions and
  re-raise a sanitised message (status code + direction only).
- GitHub masks only exact secret strings, so don't rely on masking.

## How it works
1. **Daily job (`17 4 * * *` UTC = 06:17 SAST):** scrape, merge,
   classify, predict, forecast, alert, deploy Pages. Commits only if
   `events.json` / `curves.json` / `needs_review.json` actually changed
   (ignoring `fetched_at`).
2. **Logging job (`7,22,37,52 * * * *`):** `log_traffic.py` exits unless
   one of these is active:
   - event window: start − 5 h to end + 3 h
     (if `time_confirmed: false`: 10:00–23:00 that day)
   - closure window
   - scheduled control-day window
   Readings are appended to the current month's file, encrypted, and
   committed.
3. **Monthly heartbeat commit** (needed now that commits only happen on
   change) so scheduled workflows aren't disabled after 60 days with no
   activity.
4. **Pages** deployed from the daily workflow with `actions/deploy-pages`
   (commits made with `GITHUB_TOKEN` don't trigger other workflows).
5. **Concurrency:** each workflow has its **own** `concurrency:` group.
   A shared group would let a queued logging run replace a pending daily
   run, which shows as "cancelled" and sends no email.
6. **Pushing:** jobs write to different files; push with a retry loop
   (`git pull --rebase && git push`, up to 3 attempts).
7. Crons avoid minute 0 because runs at the top of the hour are often
   delayed or dropped. Readings store their actual timestamp, since runs
   can be late.

## Repo structure
    /
    ├── data/
    │   ├── events_manual.csv
    │   ├── closures_manual.csv
    │   ├── control_days.csv
    │   ├── events.json
    │   ├── needs_review.json
    │   ├── seen_releases.json
    │   ├── scrape_health.json
    │   ├── traffic/
    │   │   └── 2026-10.jsonl.age    # encrypted, one file per month
    │   └── curves.json              # aggregated, public
    ├── scripts/
    │   ├── scrapers/
    │   │   ├── base.py
    │   │   ├── dhl_stadium.py
    │   │   ├── stormers.py
    │   │   └── capetown_gov.py
    │   ├── scrape_events.py
    │   ├── load_manual.py
    │   ├── merge_events.py
    │   ├── classify.py
    │   ├── log_traffic.py
    │   ├── learn.py
    │   ├── predict.py
    │   ├── notify.py
    │   └── tomtom.py
    ├── tests/
    │   ├── fixtures/
    │   └── test_scrapers.py
    ├── docs/
    └── .github/workflows/
        ├── daily.yml                # scrape + predict + deploy Pages
        ├── log_traffic.yml
        ├── heartbeat.yml
        └── tests.yml

## Data model

### events.json
    {
      "id": "2026-10-17-stormers-bristol",
      "name": "Stormers vs Bristol Bears",
      "start": "2026-10-17T16:15:00+02:00",
      "end_estimate": "2026-10-17T18:15:00+02:00",
      "time_confirmed": true,
      "category": "sport",   // sport | concert | race | parade | other | unknown
      "size": "medium",      // small | medium | big
      "crowd_hint": null,
      "closures": [],
      "sources": ["dhl_stadium", "stormers"],
      "source_ids": {"dhl_stadium": "event-12"},
      "status": "confirmed", // confirmed | unconfirmed | cancelled
      "rescheduled_from": null,
      "override": false
    }

Default `end_estimate`: sport start + 2 h; concert start + 4 h; races and
parades use closure end, else start + 6 h.

### Traffic log (`data/traffic/YYYY-MM.jsonl.age`)
Append-only JSONL, one line per reading, encrypted with `age` before
commit; `learn.py` decrypts in the runner. Fields: actual timestamp,
`route` (direction key), event id (or null), `control_day` flag, minutes
from event start and from event end, `status` (`ok` | `no_route` |
`detour`), live / historic / no-traffic travel time (seconds). Route length and geometry are **not** stored. (No-traffic
time is a rough distance proxy, another reason to encrypt.)

### curves.json
Per category (sport, concert) and direction: an arrival shape aligned to
start and a departure shape aligned to end (15- or 30-minute steps),
multipliers per size, baseline correction from control days, number of
events used and their spread. Only this aggregated file is public.

## Classification rules
- **Category:** source label first. Keyword fallback, checked **in this
  order** (so "Cycle Tour" is a race, not a concert):
  1. Race: marathon, cycle tour, half marathon, 10K, fun run, gun run
  2. Parade: parade, carnival, pride, Tweede Nuwe Jaar
  3. Sport: " vs ", " v ", Stormers, Springboks, SVNS, Sevens, Currie Cup,
     URC, Champions Cup, Bafana
  4. Concert: tour, in concert, festival, Calabash
- No confident match → `unknown` + needs-review.
- **Size:** `crowd_hint` if known (< 15k small, 15–40k medium, > 40k
  big). Otherwise:
  - big: concerts, Springbok tests, All Blacks/touring matches, SA URC
    derbies (Bulls, Sharks, Lions), Champions Cup knockouts, SVNS,
    Marathon, Cycle Tour, Gun Run, Street Parade
  - medium: other URC and Champions Cup pool games, Bafana friendlies,
    Pride
  - small: Currie Cup, U20
- Sport capacity cap: 55,000 (stadium figure). Concert capacity with
  field seating is higher, but no exact verified figure.

## Prediction logic
1. **Baseline calibration:** control days are non-event days logged over
   the **same hours as event windows** (Saturdays 10:00–23:00; one weekday
   15:00–21:00 a month). The median of (live − historic) on control days,
   per route and hour band, is a correction to TomTom's historic profile.
2. **Delay:** live − (historic + correction).
3. **Delay model:** two anchors per event, arrival (relative to start)
   and departure (relative to `end_estimate`), with separate shapes per
   category (sport, concert) and per direction, scaled by size. Races and
   parades use their closure windows as hard "bad" periods.
4. **Blending:** w · learned + (1 − w) · starter, w = n / (n + 3), using
   medians, per category and direction.
5. **Starter rules** (magnitudes are placeholders, tuned after the first
   events):
   | Size   | Peak extra delay |
   |--------|------------------|
   | small  | 3 min            |
   | medium | 6 min            |
   | big    | 12 min           |
   - Sport: arrival ramps up from start − 3 h, peaks start − 1 h to start,
     clears by start + 15 min. Departure from end to end + 1.5 h.
   - Concert: arrival from start − 4 h to start; departure from end to
     end + 2 h.
   - Race/parade/expo: closure windows; if none, start − 1 h to
     start + 6 h.
6. **Output:** "bad from X, clear by Y" per direction, chart of expected
   vs normal, confidence from count and spread.

Expected data: roughly 25–30 events a year (about 14 Stormers dates plus
tests, SVNS, friendlies and about 6 races/parades). Sport curves should be
learned within a season; concerts (2–4 a year) stay on starter rules
longer.

## Web app features
- Upcoming events with badges; TBC, unconfirmed, cancelled, rescheduled
  states
- Road closures for races, parades and multi-day events
- Traffic chart per event, both directions
- Plain summary per direction
- Scraper status line
- Installable on the home screen; service worker is **network-first for
  data files** so the event list is never stale

## Free-tier budget
- **TomTom:** Routing API 20,000 free requests/month, no credit card.
  | Use | Calls/year |
  |---|---|
  | ~30 event days × ~40 readings × 2 directions | ~2,400 |
  | ~24 control days × ~52 readings × 2 directions | ~2,500 |
  | Multi-day closures (Cycle Tour ~4 days continuous) | ~800 |
  | Morning forecasts (`departAt`, ~24 per event day) | ~700 |
  | **Total** | **~6,400 (~530/month)** |
  Far under quota. Do not use Matrix Routing (only 2,500/month).
- **ntfy.sh:** anonymous limits are per IP, and shared GitHub runner IPs
  can exhaust them. Use a free ntfy.sh account with an access token so
  limits count per account. GitHub failure emails remain the reliable
  channel.
- **GitHub Actions/Pages:** free for public repos.

## Privacy, terms and security
- API keys, ntfy token, `age` key, coordinates and waypoints in GitHub
  Secrets.
- Raw traffic readings are encrypted in the repo; only aggregated curves
  and predictions are published. This also keeps the TomTom storage
  question minimal (read the full terms before publishing anything
  beyond aggregates).
- Request URLs never appear in logs (see Traffic measurement → Security).
- Respect robots.txt and site terms; scrape once a day.

## Build phases

### Phase 0: logger first (target: running by Sat 17 Oct)
1. Add `TOMTOM_HOME`, `TOMTOM_DEST`, `TOMTOM_OUT_WAYPOINTS` and
   `TOMTOM_RET_WAYPOINTS` secrets; make one pinned test call per
   direction and check locally that the route follows Helen Suzman → N1
   (and back) with no U-turns.
2. Repo (public), `age` key, `tomtom.py` (sanitised errors),
   `log_traffic.py` reading `events_manual.csv`, `control_days.csv` and
   `closures_manual.csv`.
3. `log_traffic.yml` with its own concurrency group and push retry;
   `heartbeat.yml`.
4. Seed the CSV with the remaining October home games: 17 Oct (Bristol,
   16:15), 24 Oct (Scarlets, 16:00), 31 Oct (Ulster, 14:45), plus 2
   non-event Saturdays a month as control days.
5. Verify: one manual workflow run produces an encrypted line that
   decrypts locally, and nothing sensitive appears in the Actions log.

### Then the scraper
6. **Setup + checks:** `base.py`, tests; read DHL Stadium and Stormers
   robots.txt/terms; check whether DHL's raw JSON times are UTC.
7. **Core scrapers:**
   a. `dhl_stadium.py` (find the JSON endpoint first)
   b. `stormers.py` (times)
   c. `capetown_gov.py` (flag-only + alert)
   d. `load_manual.py` (events + closures CSVs, annual list seeded)
8. **Merge and classify:** `merge_events.py`, `classify.py`,
   `events.json`, `daily.yml` (own concurrency group, commit on change).
   The logger switches from the CSV to `events.json`.
9. **Hardening:** structural health checks, failing-workflow alerts,
   fixture tests (including the kick-off time check). Run for 1–2 weeks
   and compare the output with known events.

### Then the app
10. **Predictions + web page:** starter rules, charts, event list.
11. **Learning:** `learn.py` with blending, two-anchor curves and
    baseline correction.
12. **Extras:** "Add event" issue form, ntfy event alerts.

## Known risks
- **Scrapers break** → structural health checks, failing workflow,
  fixtures, CSV.
- **Wrong times on the DHL page** → JSON/UTC check, time priority list,
  fixture test.
- **Closure details only in PDFs / releases** → City flagging + manual
  closures CSV.
- **Stale CSV overrides** → conflicts flagged in needs-review.
- **Rescheduled events** → match on `(source, source_id)`, keep ID.
- **Recurring events change** (marathon moved to May, Street Parade route
  contested, Run Your City route) → annual review of the CSV.
- **TomTom rerouting on bad days** → pinned waypoints; Flow Segment Data
  as fallback.
- **TomTom terms on storing results** → encrypted raw log, aggregates
  only in public.
- **Secrets in public logs** → sanitised errors, no URL logging.
- **ntfy quota on shared IPs** → account token; GitHub failure emails.
- **Cancelled runs** → separate concurrency groups.
- **Cron delays and 60-day pause** → off-the-hour crons, actual
  timestamps, heartbeat.
- **Small samples** → shared curves per category, blending, control-day
  calibration.
- **Free tiers change** → each API in its own module.

## Decisions still needed
- ~~Destinations, directions and waypoints~~ decided (see Traffic
  measurement → Route); verified in Phase 0 step 1.
- Control days (default: 2 non-event Saturdays a month, 10:00–23:00, plus
  one weekday 15:00–21:00).
- Alert time (default 07:00 on event days).
- Starter delay magnitudes (placeholders above).
