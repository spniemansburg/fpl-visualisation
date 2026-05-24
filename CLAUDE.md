# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install / sync dependencies
uv sync

# Full pipeline — run fpl_fetch.py once per season, then analyse + export freely
uv run fpl_fetch.py                                           # ~30 s, writes fpl_raw.json
uv run fpl_analyse.py                                         # instant, reads fpl_raw.json → fpl_data.json
uv run fpl_export.py                                          # instant, reads fpl_data.json → fpl_presentation.html

# Custom paths
uv run fpl_fetch.py --league-id 157910 --output my_raw.json
uv run fpl_analyse.py --input my_raw.json --output my_data.json
uv run fpl_export.py --input my_data.json --output my_presentation.html

# Standalone tools (fetch from API directly, no pipeline)
uv run fpl_visualisation.py                                   # 3-panel Plotly dashboard
uv run fpl_race.py                                            # animated bar-chart race
uv run fpl_race.py --speed 400 --output my_race.html
```

There are no tests or linter configs at this time.

## Repository layout

| File | Role | Committed? |
|---|---|---|
| `fpl_fetch.py` | Stage 1 — fetch raw data from FPL API | ✅ |
| `fpl_analyse.py` | Stage 2 — compute derived stats | ✅ |
| `fpl_export.py` | Stage 3 — generate Reveal.js presentation | ✅ |
| `fpl_visualisation.py` | Shared constants + standalone Plotly dashboard | ✅ |
| `fpl_race.py` | Standalone Plotly animated race | ✅ |
| `fpl_raw.json` | Raw API dump (re-fetchable, can be large) | ❌ gitignored |
| `fpl_data.json` | Processed season data (small, safe to commit) | ✅ |
| `fpl_presentation.html` | Generated presentation | ❌ gitignored |
| `fpl_*.html` | Other generated outputs | ❌ gitignored |

## Architecture

The project follows a three-stage pipeline:

```
fpl_fetch.py → fpl_raw.json → fpl_analyse.py → fpl_data.json → fpl_export.py → fpl_presentation.html
```

Re-run only the stages you need: `fpl_fetch.py` only when you need fresh API data; `fpl_analyse.py` when you change derived stats; `fpl_export.py` when you change the presentation.

### fpl_fetch.py — raw data capture

Hits the FPL public API (no auth required), writes a self-contained `fpl_raw.json`. Makes ~150 API calls:
- `GET /api/bootstrap-static/` — all player names/teams/positions
- `GET /api/leagues-classic/{id}/standings/` — league name + manager list
- Per finished GW: `GET /api/event/{gw}/live/` — all player points
- Per manager × GW: `GET /api/entry/{id}/event/{gw}/picks/` — squad + multipliers

`gw_points` is embedded in each pick at fetch time by joining with GW live data, making `fpl_raw.json` fully self-contained downstream.

### fpl_analyse.py — analysis

Reads `fpl_raw.json` (no API calls). Computes per-player stats for each manager across all 15 squad positions (bench included), enriches chips with labels/colours from `fpl_visualisation.CHIPS`, derives per-GW league ranks, and writes `fpl_data.json`.

Key per-player fields: `total_pts_contributed` (pts × multiplier), `total_pts_scored` (raw), `bench_pts`, `gws_owned`, `gws_in_xi`, `gws_as_captain`, `first_gw_owned`, `last_gw_owned`, `in_from_start`, `still_in`, `transfer_in_events`, `transfer_out_events`. Players are sorted by `total_pts_contributed` descending; `top_players` is the first 3.

### fpl_export.py — Reveal.js presentation

Reads `fpl_data.json` (no API calls). `generate_html()` replaces the `/*DATA_PLACEHOLDER*/` sentinel in `HTML_TEMPLATE` with the JSON blob. Writes `fpl_presentation.html` and opens it in the browser.

Slides: title card, D3 animated race, cumulative chart, per-GW bars, league standing, season's best players. All slides read from the single embedded JSON blob — no runtime fetch.

The D3 race (slide 2) uses a keyed data-join on manager name so D3 tracks bar identity across frames. Bar widths (points) and `transform` Y-positions (rank order) transition simultaneously on the same `d3.transition()`. A `setInterval` at `SPEED` ms advances the GW index; the transition runs for `TRANS` ms (< `SPEED`). Chip badges animate to opacity 1 only in the GW they were played. The race auto-starts via `Reveal.on('slidechanged', ...)` when slide 2 becomes active.

### fpl_visualisation.py — shared constants + static dashboard

Exports `LEAGUE_ID`, `PALETTE`, `CHIPS`, `RANK_COLORS`, and `fetch_all_data()` (used by `fpl_race.py`). The `if __name__ == "__main__"` guard runs a 3-panel Plotly dashboard: cumulative race (filled area + line), league standing (inverted y-axis, medal colours), and per-GW grouped bars.

`fetch_all_data()` only hits the standings + history APIs (no picks/live data), strips unfinished GWs (`points == 0` and `rank is None`), and returns manager dicts with pre-computed `gw_points`, `cumulative`, `transfer_hits`, and `bench_pts`.

### fpl_race.py — Plotly animated race

Imports `fetch_all_data` from `fpl_visualisation`. One `go.Frame` per finished GW; `_snapshot()` re-sorts managers by cumulative points each frame so bars reorder. Chip badges are appended to the y-axis label for the frame the chip was played.

## Key constants (in fpl_visualisation.py)

| Constant | Purpose |
|---|---|
| `LEAGUE_ID` | FPL classic league ID — change to target a different league |
| `PALETTE` | Per-manager colours (line/fill/bar) — index matches standings API order |
| `CHIPS` | Chip name → `{label, color}` for display |
| `RANK_COLORS` | Gold/silver/bronze hex values for the position chart markers |
