# Progress

*Last updated: 12 Oct 2026. Update this file at the end of each session.*

Design and phases are in [PLAN.md](PLAN.md) (v5). This file tracks where
things actually stand.

## Status at a glance
| Phase | Status |
|---|---|
| 0. Traffic logger | **Done, running** |
| 6–9. Event scraper (DHL, Stormers, City, CSV loader, merge, hardening) | Not started; **next up** |
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
| 5–6 Dec | HSBC SVNS | 03:00–13:00 each day |

More home games through April 2027 are in `data/events_manual.csv`.

## Findings worth remembering
- DHL Stadium's "Starts" times are unreliable, now by 1 h: Ulster shown
  13:45 (RugbyPass 14:45), Lions 15:00 (RugbyPass 16:00). Bristol and
  Scarlets match. CSV uses the RugbyPass times.
- The Sharks home game on 10 Oct was missed (logger not yet live).
- November has no home club rugby (international window).

## Open to-dos
- [ ] **Back up `age-key.txt`** off the laptop (password manager or USB).
      Without it the log can never be decrypted.
- [ ] Check readings after Sat 17 Oct (`decrypt_log.py`).
- [ ] Before 10 Mar 2028: change the cron-job.org header
      `X-GitHub-Api-Version: 2022-11-28` (GitHub sunsets it then).
- [ ] Before 5 Dec: SVNS runs all day, but the logger assumes a 2 h sport
      event, so its window ends at 13:00. Add an optional duration column
      to `events_manual.csv` (or similar) so all-day events are covered.
- [ ] Optional: delete the unused "Traffic" environment in repo settings.

## Next step
Phase 6 recon (read-only):
1. Read robots.txt and terms for dhlstadium.co.za and stormers.co.za.
2. Find the JSON feed behind dhlstadium.co.za/events (DevTools → Network
   → Fetch/XHR); check whether its times are UTC (would explain the
   shifted "Starts" field).
3. Check the Stormers site for `/wp-json/` fixture data.

## Resuming in a new session
    cd "Side Projects/green-point-traffic"
    git pull
    .venv/Scripts/python -m pytest -q tests
    .venv/Scripts/python scripts/log_traffic.py --check
    gh run list --workflow log_traffic.yml --limit 10
