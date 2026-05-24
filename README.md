# FPL League Visualisation

Interactive dashboard for a Fantasy Premier League mini-league season.

## What it shows

| Chart | Description |
|---|---|
| 📈 Cumulative Points Race | Running total per manager across all gameweeks, with a dotted line marking the widest gap |
| 🏆 League Standing | Position within the mini-league each gameweek (gold/silver/bronze markers) |
| 📊 Points per Gameweek | Grouped bars showing each manager's raw GW score |

## Setup

```bash
uv sync
```

## Usage

```bash
uv run fpl_visualisation.py
# or via the installed script entry-point:
uv run fpl-vis
```

Set `LEAGUE_ID` at the top of the script to your own classic league ID.  
Output is saved to `fpl_league_visualisation.html` and opened in your browser.

## League

**Primeira Divisão de Rodrigues** — 2025/26 season

| # | Manager | Team | Total |
|---|---|---|---|
| 🥇 | Stephan Niemansburg | Steeph United | 2201 |
| 🥈 | Maurice Rodrigues | FC SIUUU | 2177 |
| 🥉 | Avelino Rodrigues | Benfica On Fire | 2102 |
