# Web app plan

A GitHub Pages site, rebuilt by the daily workflow, installable on a phone.
Outlooks come only from logged games (no starter rules).

## What the page shows
1. **Event list:** upcoming events (date, start, size, category) with badges
   for TBC, unconfirmed, cancelled and rescheduled; road closures for races,
   parades and multi-day events.
2. **Outlook per event and direction:** "bad from X, clear by Y", read from
   the learned curve for that category/size/direction. "Bad" means a
   15-minute step with median extra delay of 2 min or more. No curve yet →
   "no data yet (n events logged)".
3. **Chart per event:** expected extra delay over time, both directions,
   with the low-high spread across past events. Inline SVG, no libraries.
4. **Status line:** when the scrapers and logger last succeeded.

## Design
A tide table for traffic. The memorable element is a day strip per
direction (event window, start − 5 h to end + 3 h), shaded lighthouse red
where traffic is bad, darker where worse, with ticks at kick-off and
expected end. Tapping a strip opens the full chart with the spread.
Everything else stays quiet.

- Colour: chart paper `#E9EFEE` (background), deep water `#12343B` (text),
  lighthouse red `#C8332B` (bad), freeway green `#00664F` (clear, OK),
  mist `#93A3A3` (secondary, empty strip). Dark mode: deep water
  background, red and green slightly brightened.
- Type: Overpass only; 14 / 17 / 22 / 34 px; times large in heavy weight
  with tabular figures.
- Layout: one left-aligned column. Next event first (two strips), then a
  plain "Later" list. No cards, all-caps labels, mono labels, middle dots
  or arrows.
- Motion: the next event's strips fill left to right once on load; off
  with reduced motion.
- Copy: "Going out to the N1", "Coming home", "Clear all day",
  "Not enough games logged yet".

## Files
- `site/index.html`, `site/app.js`, `site/style.css`
- `site/manifest.webmanifest`, `site/sw.js` (network-first for data files)
- Published data: `events.json`, `curves.json`, `scrape_health.json`
  (copied into the site at build time; raw readings never published)

## Steps
1. **You:** add the private age key as a GitHub secret, and set Pages to
   deploy from GitHub Actions (Settings → Pages → Source: GitHub Actions).

       gh secret set AGE_IDENTITY -R MikeTuks/green-point-traffic < age-key.txt

   → verify: `gh secret list` shows `AGE_IDENTITY`.
2. **daily.yml:** run `learn.py` with `AGE_IDENTITY`, commit `curves.json`,
   then build `site/` and deploy with `actions/deploy-pages`.
   → verify: a manual run publishes the site and `curves.json` matches a
   local run.
3. **Page:** event list, outlook, chart, status line; works at phone width
   and in dark mode.
   → verify: open the live site in the browser pane; check the 17 Oct game
   shows the outbound departure jam (about 18:45–19:30).
4. **Installable:** manifest and service worker.
   → verify: the page loads offline with the last data; new data shows after
   the next daily run.
5. **Tests:** the outlook rule ("bad from X, clear by Y") is computed in
   Python at build time (`scripts/build_site.py`) and tested with pytest;
   the page only displays it.

## Not included
- Category-level fallback when a size has no data yet (can add in Feb if
  big games are still missing).
- ntfy alerts and the "Add event" form (Phase 12).
