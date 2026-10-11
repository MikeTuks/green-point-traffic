# Green Point Event Traffic

Free web app that lists upcoming events at and around DHL Stadium (Green
Point), and predicts when traffic near home gets bad and when it clears.
Predictions learn from real event days.

Runs entirely on GitHub Actions and GitHub Pages. See [PLAN.md](PLAN.md)
for the design and build phases.

## Status
Phase 0 (traffic logger): running. Route checked 11 Oct 2026 (outbound joins the N1 via Woodstock; kept as is).

## Phase 0: traffic logger
`log_traffic.yml` runs every 15 minutes. It does nothing unless an event,
closure or control-day window from the CSVs in `data/` is active. Each
reading is encrypted with the public age key in `data/age_recipient.txt`
and appended to `data/traffic/YYYY-MM.jsonl.age`.

Repo secrets: `TOMTOM_API`, `TOMTOM_HOME`, `TOMTOM_DEST`,
`TOMTOM_OUT_WAYPOINTS`, `TOMTOM_RET_WAYPOINTS`.

Local commands (after `pip install -r requirements.txt pytest`):

    python scripts/check_route.py                       # pinned route check, uses .env
    python scripts/log_traffic.py --check               # which window is active now
    python scripts/decrypt_log.py data/traffic/2026-10.jsonl.age
    python -m pytest tests

The private key (`age-key.txt`) is never committed; keep a backup of it.
