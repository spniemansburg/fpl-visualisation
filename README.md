# FPL League Visualisation

Interactive Reveal.js + D3 presentation for a Fantasy Premier League mini-league season.

## Quick start

```bash
uv sync
make presentation   # analyse + export → opens fpl_presentation.html
```

## Pipeline

```
fpl_fetch.py → fpl_raw.json → fpl_analyse.py → fpl_data.json → fpl_export.py → fpl_presentation.html
```

| Stage | Command | When to run |
|---|---|---|
| Fetch | `uv run fpl_fetch.py` | Once per season (hits FPL API, ~150 calls, ~30 s) |
| Analyse | `uv run fpl_analyse.py` | When changing derived stats |
| Export | `uv run fpl_export.py` | When changing the presentation |
| Both | `make presentation` | Analyse + export in one go |

## Makefile targets

```bash
make presentation   # analyse + export
make fetch          # fetch raw data from FPL API
make analyse        # recompute fpl_data.json from fpl_raw.json
make export         # regenerate fpl_presentation.html from fpl_data.json
```

## Presentation slides

| # | Slide | Description |
|---|---|---|
| 1 | Title | League name, season, manager cards with final totals |
| 2 | 📈 Points Race | Animated D3 bar-chart race, GW by GW |
| 3 | 🏆 Final Standings | Podium with final scores |
| 4 | 📊 Season by the Numbers | Best GW, widest gap, transfer hits, bench points |
| 5 | 🃏 Chip Timeline | When each manager played their 8 chips |
| 6 | 🎯 Where Was The Race Decided? | Lead tracker chart + captaincy, consistency, chip returns, mistakes |
| 7 | ⭐ Season's Best Players | Top 5 players per manager by points contributed |

## Standalone tools

```bash
uv run fpl_visualisation.py   # 3-panel Plotly dashboard (cumulative, standing, GW bars)
uv run fpl_race.py            # Plotly animated bar-chart race
uv run fpl_race.py --speed 400 --output my_race.html
```

## Custom league

```bash
uv run fpl_fetch.py --league-id 157910 --output my_raw.json
uv run fpl_analyse.py --input my_raw.json --output my_data.json
uv run fpl_export.py --input my_data.json --output my_presentation.html
```

Or set `LEAGUE_ID` in `fpl_visualisation.py` for the standalone tools.

## 2025/26 standings — Primeira Divisão de Rodrigues

| # | Manager | Team | Total |
|---|---|---|---|
| 🥇 | Stephan Niemansburg | Steeph United | 2249 |
| 🥈 | Maurice Rodrigues | FC SIUUU | 2239 |
| 🥉 | Avelino Rodrigues | Benfica On Fire | 2151 |
