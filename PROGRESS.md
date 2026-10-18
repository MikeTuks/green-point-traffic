# Progress

*Last updated: 18 Oct 2026. Update this file at the end of each session.*

Design and phases are in [PLAN.md](PLAN.md) (v5). This file tracks where
things actually stand.

## Status at a glance
| Phase | Status |
|---|---|
| 0. Traffic logger | **Done, running** |
| 6–9. Event scraper (DHL, TheSportsDB, City, CSV loader, merge, hardening) | **Done** (Phase 9 pushed 18 Oct); daily job now also checks the logger and opens issues for review items |
| Data collection | **Running until Feb 2027** (no starter rules; delays come only from logged games) |
| 10. Learning | `learn.py` built and running daily (18 Oct); revisit in Feb 2027 once ~9 games are logged |
| 11. Web page | **Live** (18 Oct): https://miketuks.github.io/green-point-traffic/ |
| 12. Extras (issue form, ntfy alerts) | Not started |

## Phase 0: what's in place
- `scripts/log_traffic.py` reads `data/events.json` (falls back to
  `events_manual.csv` if missing) plus the closure and control-day CSVs,
  and logs only during
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
  the log; also stored as the GitHub secret `AGE_IDENTITY` (18 Oct) so
  `learn.py` runs in `daily.yml`.
- **Pages:** source GitHub Actions; deployed by the `pages` job in
  `daily.yml` from `_site/` (built by `scripts/build_site.py`).
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
| Wed 18 Nov | Control day | 15:00–21:00 |
| Sat 28 Nov | Control day | 10:00–23:00 |
| 5–6 Dec | HSBC SVNS (10:00, end est. 20:00) | 05:00–23:00 each day |
| Sat 12 Dec, Sat 9 Jan | Control days | 10:00–23:00 |
| Wed 13 Jan | Control day | 15:00–21:00 |

More home games through April 2027, and the 2027 races and parades, are
in `data/events_manual.csv` (Cycle Tour closures in `closures_manual.csv`).

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
- 16 Oct: TheSportsDB `eventsnext`/`searchevents` returned 503 (their
  outage), so `daily.yml` failed and DHL's known 1 h-early times showed
  up as 4 `time_conflict` review items (Ulster, Lions, Bulls, Cardiff).
  Checked against TheSportsDB `eventsday`: CSV times are right; ignore.
- **First game logged (Stormers v Bristol, 17 Oct):** outbound +2–3 min
  about 2 h before kick-off, up to +10 min 30–75 min after the end; return
  no clear effect. The owner considers it a small game next to a
  Springbok test.
- 16–18 Oct: TheSportsDB failed from GitHub runners only (shared free key
  `123` rate limit). Fixed 18 Oct: 60/120 s waits on HTTP 429 and only
  games in the next 42 days are asked about.
- The Sharks home game on 10 Oct was missed (logger not yet live).
- November has no home club rugby (international window).

## Open to-dos
- [x] Back up `age-key.txt` off the laptop (done 12 Oct).
- [x] Check readings after Sat 17 Oct (`decrypt_log.py`).
      Found: 43/43 ok readings each way, 11:15–21:00, max gap 15.1 min, no failed runs.
- [ ] Before 10 Mar 2028: change the cron-job.org header
      `X-GitHub-Api-Version: 2022-11-28` (GitHub sunsets it then).
- [x] All-day events: optional `end_time` column added to
      `events_manual.csv` (12 Oct). SVNS set to 10:00–20:00 per day.
- [ ] Before 5 Dec: confirm SVNS 2026 daily end time (20:00 is an
      estimate; DHL API gives 10:00 start, no end).
- [ ] Confirm estimated 2027 dates/times in the CSVs (added 12 Oct):
      Street Parade 2 Jan (date and route both unknown; 2026 was 5 Jan
      via Somerset Rd), Pride Mardi Gras 27–28 Feb (one listing says 28
      Feb), Gun Run 11–12 Sep (mid-Sep pattern), Cycle Tour expo 11–13
      Mar and closures (2026 pattern). Confirmed: Cycle Tour race 14 Mar,
      Marathon 23 May (Saturday races 22 May).
- [ ] Optional: delete the unused "Traffic" environment in repo settings.

## Next step
Nothing to build until Feb 2027; the pipeline runs on its own.
- `daily.yml` (06:17 SAST): scrape and merge, `learn.py` → `data/curves.json`,
  build and deploy the page, open a GitHub issue for new review items, and
  fail (email) if fewer than 72 logger runs succeeded in 24 h or a source
  has failed 3 days running.
- City releases are flagged only if they mention a Green Point place and a
  closure/detour.
- In Feb 2027: review the learned curves (`learn.py` output) and decide
  whether a category-level fallback is needed for sizes without data.
- Not covered automatically: Currie Cup kick-offs (CSV/DHL only); games
  missing from DHL are only found when they are the next home game.
- Yearly: update next year's race and parade dates in the CSVs.

## Resuming in a new session
    cd "Side Projects/green-point-traffic"
    git pull
    .venv/Scripts/python -m pytest -q tests
    .venv/Scripts/python scripts/log_traffic.py --check
    .venv/Scripts/python scripts/merge_events.py    # ~1 min, live; writes events.json
    gh run list --workflow log_traffic.yml --limit 10
    .venv/Scripts/python scripts/learn.py           # needs age-key.txt; writes curves.json
    .venv/Scripts/python scripts/build_site.py      # writes _site/
