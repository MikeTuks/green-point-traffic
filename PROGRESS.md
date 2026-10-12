# Progress

*Last updated: 12 Oct 2026. Update this file at the end of each session.*

Design and phases are in [PLAN.md](PLAN.md) (v5). This file tracks where
things actually stand.

## Status at a glance
| Phase | Status |
|---|---|
| 0. Traffic logger | **Done, running** |
| 6–9. Event scraper (DHL, TheSportsDB, City, CSV loader, merge, hardening) | **In progress:** DHL + TheSportsDB scrapers done (12 Oct) |
| 10. Predictions + web page | Not started |
| 11. Learning | Not started |
| 12. Extras (issue form, ntfy alerts) | Not started |

## Phase 0: what's in place
- `scripts/log_traffic.py` checks the CSVs in `data/` and logs only during
  event windows (start − 5 h to end + 3 h; 10:00–23:00 if time TBC),
  closure windows and control days. Each reading is encrypted on its own
  with the public age key and appended to `data/traffic/YYYY-MM.jsonl.age`.
- `scripts/tomtom.py`: one Calculate Route call per direction,
  `computeTravelTimeFor=all`, errors sanitised (no URLs, coordinates or key
  in logs). Records `no_route` when Beach Rd is closed.
- Route: home end → destination and back, pinned through waypoints on
  Helen Suzman Blvd and the N1. Checked 11 Oct: outbound joins the N1 via
  Woodstock (~3 km longer than the return); kept as is on purpose, since
  the goal is a heads-up, not precision.
- Tests: `tests/test_log_traffic.py` (window logic, route order), all pass.
- Verified end to end on 10 Oct with a forced run: readings committed and
  decrypted locally. The two test readings are marked `"window": "forced"`.

## Infrastructure
- **Repo:** public, github.com/MikeTuks/green-point-traffic.
- **Repo secrets:** `TOMTOM_API`, `TOMTOM_HOME`, `TOMTOM_DEST`,
  `TOMTOM_OUT_WAYPOINTS`, `TOMTOM_RET_WAYPOINTS`. Local copies of the same
  values live in `.env` (git-ignored).
- **Scheduling:** cron-job.org (owner's account) calls the
  `workflow_dispatch` API every 15 min with a fine-grained token (Actions
  read/write on this repo only, no expiry). GitHub's own cron stays as a
  backup; on its own it only ran ~4 times a day. Checked 12 Oct: 73 runs in
  18 h, max gap 15.1 min.
- **Heartbeat:** monthly empty commit (`heartbeat.yml`).
- **Encryption:** public key in `data/age_recipient.txt`; private key in
  `age-key.txt` on the owner's laptop only (git-ignored). Needed to read
  the log and, from Phase 11, as a GitHub secret `AGE_IDENTITY`.
- **Local tooling quirks (Windows):** `gh` lives at
  `C:\Program Files\GitHub CLI\gh.exe` and may not be on PATH in older
  terminals. The repo uses a repo-local credential helper
  (`gh auth git-credential`) because Windows Credential Manager held a
  stale token. Python virtualenv in `.venv/`.

## Upcoming logging dates
| Date | What | Window |
|---|---|---|
| Sat 17 Oct | Stormers v Bristol Bears (16:15) | 11:15–21:15, **first real readings** |
| Wed 21 Oct | Control day | 15:00–21:00 |
| Sat 24 Oct | Stormers v Scarlets (16:00) | 11:00–21:00 |
| Sat 31 Oct | Stormers v Ulster (14:45) | 09:45–19:45 |
| Sat 7 & 14 Nov | Control days (checked: no stadium events) | 10:00–23:00 |
| 5–6 Dec | HSBC SVNS (10:00, end est. 20:00) | 05:00–23:00 each day |

More home games through April 2027 are in `data/events_manual.csv`.

## Findings worth remembering
- **DHL Stadium API (recon 12 Oct):** public Strapi API, no auth, no
  robots.txt (the path returns the SPA shell), no terms page found.
  `https://api.dhlstadium.co.za/api/events?pagination[pageSize]=100&populate[event][populate][0]=daterange`
  → `data[].attributes.{title,category,slug}`, dates in
  `attributes.event[].daterange[].start` (**UTC, `Z`**; `end` usually
  null). The page's "Starts" shows the UTC clock time unconverted. Even
  converted, DHL's data is 1 h early for Ulster, Lions, Bulls, Cardiff
  (vs Stormers), and lacks Zebre. SVNS: 10:00 SAST both days.
- **Stormers site (recon 12 Oct):** `/wp-json/` needs a login (401).
  `/match-centre/` embeds schema.org `SportsEvent` JSON-LD with local
  `startDate` and venue, plus a match JSON blob (`dateTime` UTC, `tbc`,
  `venue`). robots.txt allows it. **But their terms forbid any "robot,
  spider ... or manual process to monitor, copy" the site without written
  consent, and reuse on another website.** Decided 12 Oct: don't scrape
  it, don't ask for consent; use TheSportsDB instead.
- **TheSportsDB (free key `123`):** Stormers team 136670, URC league 4446,
  Champions Cup 4550. Times correct (UTC, no `Z`). Free caps: 3 results
  per `eventsday.php` (per league), 1 per `searchevents.php` (partial
  name match: `Stormers_vs_Racing` finds "Racing Métro 92"), 1 for
  `eventsnext.php`. A full live run takes ~55 s (2.5 s between calls).
- CSV corrected from Stormers times on 12 Oct: Bulls 15:00→16:00,
  Cardiff 16:00→17:00, added Zebre Parma 30 Jan 17:00, SVNS start
  08:00→10:00 (DHL).
- The Sharks home game on 10 Oct was missed (logger not yet live).
- November has no home club rugby (international window).

## Open to-dos
- [x] Back up `age-key.txt` off the laptop (done 12 Oct).
- [ ] Check readings after Sat 17 Oct (`decrypt_log.py`).
- [ ] Before 10 Mar 2028: change the cron-job.org header
      `X-GitHub-Api-Version: 2022-11-28` (GitHub sunsets it then).
- [x] All-day events: optional `end_time` column added to
      `events_manual.csv` (12 Oct). SVNS set to 10:00–20:00 per day.
- [ ] Before 5 Dec: confirm SVNS 2026 daily end time (20:00 is an
      estimate; DHL API gives 10:00 start, no end).
- [ ] Optional: delete the unused "Traffic" environment in repo settings.

## Next step
Phase 6–7a/b done: `scripts/scrapers/{base,dhl_stadium,sportsdb}.py`,
`scripts/scrape_events.py` (prints results; run from `scripts/`), tests
in `tests/test_scrapers.py` with fixtures. Next:
1. 7c `capetown_gov.py` (flag-only) and 7d `load_manual.py`.
2. 8 `merge_events.py` + `classify.py` → `events.json`, `daily.yml`;
   logger switches from the CSV to `events.json`.
Not covered automatically: Currie Cup kick-offs (CSV/DHL only).

## Resuming in a new session
    cd "Side Projects/green-point-traffic"
    git pull
    .venv/Scripts/python -m pytest -q tests
    .venv/Scripts/python scripts/log_traffic.py --check
    .venv/Scripts/python scripts/scrape_events.py   # ~1 min, live
    gh run list --workflow log_traffic.yml --limit 10
