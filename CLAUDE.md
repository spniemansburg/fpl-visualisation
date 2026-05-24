# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install / sync dependencies
uv sync

# Run the visualisation (fetches live data, writes HTML, opens browser)
uv run fpl_visualisation.py
# or via the entry-point
uv run fpl-vis
```

There are no tests or linter configs at this time.

## Architecture

The project is a single-file script (`fpl_visualisation.py`) with three clearly separated sections:

**1. Data fetching** — two FPL public API endpoints, no auth required:
- `GET /api/leagues-classic/{league_id}/standings/` → league name + list of managers
- `GET /api/entry/{entry_id}/history/` → per-GW records for one manager

`fetch_all_data()` calls both, strips unfinished gameweeks (identified by `points == 0` and `rank is None`), and returns a list of manager dicts. Each dict carries pre-computed `gw_points` (net of transfer hits), `cumulative` running totals, `transfer_hits`, and `bench_pts`.

**2. Rank computation** — `compute_league_ranks()` derives each manager's position within the mini-league at every gameweek from the cumulative totals. This is a derived field; the FPL API does not expose it directly.

**3. Chart building** — `build_figure()` produces a single `plotly.graph_objects.Figure` with three vertically stacked subplots:
- Row 1 (45 %): cumulative points race — filled area + line per manager, end-of-season medal annotations, dotted vline at max-gap GW
- Row 2 (25 %): league standing per GW — inverted y-axis, dots coloured gold/silver/bronze
- Row 3 (30 %): grouped bars for raw GW points

The figure is written to `fpl_league_visualisation.html` (Plotly loaded from CDN, so the file is self-contained at ~20 KB).

## Key constants

| Constant | Purpose |
|---|---|
| `LEAGUE_ID` | FPL classic league ID — change this to target a different league |
| `OUTPUT_FILE` | Path for the generated HTML |
| `PALETTE` | Per-manager colours (line, shaded fill, bar) — index matches order from the standings API |
| `RANK_COLORS` | Gold/silver/bronze hex values for the position chart markers |
