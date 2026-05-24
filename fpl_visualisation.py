"""
FPL League Visualisation
Fetches weekly points for all managers in a classic league and
produces an interactive HTML dashboard.

Usage:
    python fpl_visualisation.py

Requirements:
    pip install requests plotly
"""

import time
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ─────────────────────────────────────────────────────────────────────
LEAGUE_ID   = 157910
OUTPUT_FILE = "fpl_league_visualisation.html"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FPL-vis/1.0)"})

# FPL-inspired palette — one colour set per manager
PALETTE = [
    {"line": "#00d2be", "fill": "rgba(0,210,190,0.12)", "bar": "#00d2be"},   # teal
    {"line": "#e8002d", "fill": "rgba(232,0,45,0.12)",   "bar": "#e8002d"},  # red
    {"line": "#963cff", "fill": "rgba(150,60,255,0.12)", "bar": "#963cff"},  # purple
]

RANK_COLORS = {1: "#ffd700", 2: "#c0c0c0", 3: "#cd7f32"}   # gold / silver / bronze

# Chip display config — label shown on chart, Plotly marker symbol, colour
CHIPS: dict[str, dict] = {
    "wildcard": {"label": "WC", "symbol": "diamond",     "color": "#ff8c00"},  # orange
    "freehit":  {"label": "FH", "symbol": "square",      "color": "#1e90ff"},  # blue
    "3xc":      {"label": "TC", "symbol": "star",         "color": "#ffd700"},  # gold
    "bboost":   {"label": "BB", "symbol": "triangle-up",  "color": "#32cd32"},  # green
}


# ── Data fetching ──────────────────────────────────────────────────────────────

def get_league_info(league_id: int) -> tuple[str, list[dict]]:
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    r = SESSION.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    name = data["league"]["name"]
    managers = data["standings"]["results"]
    return name, managers


def get_entry_history(entry_id: int) -> tuple[list[dict], list[dict]]:
    """Return (gw_records, chips). chips: [{name, event, time}, ...]"""
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    r = SESSION.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["current"], data.get("chips", [])


def fetch_all_data(league_id: int) -> tuple[str, list[dict]]:
    """
    Returns (league_name, managers_list).
    Each manager dict:
      name, team_name, entry_id, final_rank,
      gw_records  – raw API records (only finished GWs),
      gw_nums     – list of GW numbers,
      gw_points   – net GW points (after transfer hits),
      cumulative  – running total,
      transfer_hits – total points lost on hits,
      bench_pts   – total points left on bench,
    """
    print(f"Fetching league {league_id} …")
    league_name, managers = get_league_info(league_id)
    print(f"  League: {league_name}")

    all_data = []
    for mgr in managers:
        entry_id  = mgr["entry"]
        name      = mgr["player_name"]
        team_name = mgr["entry_name"]
        final_rank = mgr["rank"]
        print(f"  {name} ({team_name}, #{final_rank}) …")

        records, chips = get_entry_history(entry_id)
        time.sleep(0.3)

        # Drop unfinished GWs (points == 0 and rank is None)
        finished = [r for r in records if not (r["points"] == 0 and r["rank"] is None)]
        finished_gw_set = {r["event"] for r in finished}

        gw_nums = [r["event"] for r in finished]
        gw_pts  = [r["points"] - r.get("event_transfers_cost", 0) for r in finished]

        cumulative = []
        running = 0
        for p in gw_pts:
            running += p
            cumulative.append(running)

        # Only keep chips that were played in a finished GW
        finished_chips = [c for c in chips if c["event"] in finished_gw_set]

        all_data.append({
            "name":          name,
            "team_name":     team_name,
            "entry_id":      entry_id,
            "final_rank":    final_rank,
            "gw_records":    finished,
            "gw_nums":       gw_nums,
            "gw_points":     gw_pts,
            "cumulative":    cumulative,
            "transfer_hits": sum(r.get("event_transfers_cost", 0) for r in finished),
            "bench_pts":     sum(r.get("points_on_bench", 0)      for r in finished),
            "chips":         finished_chips,   # [{name, event, time}, ...]
        })

    return league_name, all_data


# ── League-rank helper ─────────────────────────────────────────────────────────

def compute_league_ranks(all_data: list[dict]) -> list[dict]:
    """Add a 'league_rank' list to each manager (rank within this mini-league per GW)."""
    n_gws = max(len(m["cumulative"]) for m in all_data)
    for gw_i in range(n_gws):
        snapshot = []
        for mi, mgr in enumerate(all_data):
            pts = mgr["cumulative"][gw_i] if gw_i < len(mgr["cumulative"]) else 0
            snapshot.append((mi, pts))
        snapshot.sort(key=lambda x: -x[1])
        for rank, (mi, _) in enumerate(snapshot):
            all_data[mi].setdefault("league_rank", []).append(rank + 1)
    return all_data


# ── Chart builder ──────────────────────────────────────────────────────────────

def build_figure(league_name: str, all_data: list[dict]) -> go.Figure:
    all_data = compute_league_ranks(all_data)

    # Sort by final rank for consistent legend ordering
    all_data = sorted(all_data, key=lambda m: m["final_rank"])

    n_gws = max(len(m["gw_nums"]) for m in all_data)
    all_gws = list(range(1, n_gws + 1))

    # ── Build subplots ──────────────────────────────────────────────────────
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            "📈  Cumulative Points Race",
            "🏆  League Standing per Gameweek",
            "📊  Points per Gameweek",
        ),
        vertical_spacing=0.10,
        row_heights=[0.45, 0.25, 0.30],
    )

    for i, mgr in enumerate(all_data):
        pal   = PALETTE[i % len(PALETTE)]
        gws   = mgr["gw_nums"]
        label = f"{mgr['name']}  ·  {mgr['team_name']}"

        # ── 1. Cumulative race ─────────────────────────────────────────────
        # Shaded fill-to-zero area
        fig.add_trace(
            go.Scatter(
                x=gws + gws[::-1],
                y=mgr["cumulative"] + [0] * len(gws),
                fill="toself",
                fillcolor=pal["fill"],
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
                name=label,
            ),
            row=1, col=1,
        )
        # Main line
        fig.add_trace(
            go.Scatter(
                x=gws,
                y=mgr["cumulative"],
                mode="lines+markers",
                name=label,
                line=dict(color=pal["line"], width=3),
                marker=dict(
                    size=5,
                    color=pal["line"],
                    line=dict(width=1, color="#ffffff"),
                ),
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "GW %{x}<br>"
                    "Total: <b>%{y} pts</b><extra></extra>"
                ),
            ),
            row=1, col=1,
        )

        # ── 1b. Chip markers on the cumulative line ────────────────────────
        if mgr.get("chips"):
            gw_to_idx = {gw: idx for idx, gw in enumerate(gws)}
            for chip in mgr["chips"]:
                gw = chip["event"]
                if gw not in gw_to_idx:
                    continue
                cfg      = CHIPS.get(chip["name"], {"label": chip["name"], "symbol": "circle", "color": "#888888"})
                cum_y    = mgr["cumulative"][gw_to_idx[gw]]
                played   = chip["time"][:10]
                fig.add_trace(
                    go.Scatter(
                        x=[gw],
                        y=[cum_y],
                        mode="markers+text",
                        showlegend=False,
                        text=[cfg["label"]],
                        textposition="top center",
                        textfont=dict(size=8, color=cfg["color"], family="Arial Black, sans-serif"),
                        marker=dict(
                            symbol=cfg["symbol"],
                            size=13,
                            color=cfg["color"],
                            line=dict(width=1.5, color="#ffffff"),
                        ),
                        hovertemplate=(
                            f"<b>{cfg['label']} — {label}</b><br>"
                            f"GW {gw}  ({played})<br>"
                            f"Total at this point: {cum_y} pts<extra></extra>"
                        ),
                        name=cfg["label"],
                    ),
                    row=1, col=1,
                )

        # ── 2. League rank (inverted — 1 is best) ──────────────────────────
        fig.add_trace(
            go.Scatter(
                x=gws,
                y=mgr["league_rank"],
                mode="lines+markers",
                name=label,
                showlegend=False,
                line=dict(color=pal["line"], width=2.5, dash="solid"),
                marker=dict(
                    size=8,
                    color=[
                        RANK_COLORS.get(r, pal["line"])
                        for r in mgr["league_rank"]
                    ],
                    line=dict(width=1.5, color="#ffffff"),
                    symbol="circle",
                ),
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "GW %{x}<br>"
                    "Position: <b>%{y}</b><extra></extra>"
                ),
            ),
            row=2, col=1,
        )

        # ── 3. Weekly bars ─────────────────────────────────────────────────
        chip_gw_map = {c["event"]: CHIPS.get(c["name"], {}).get("label", "?") for c in mgr.get("chips", [])}
        bar_borders  = ["#ffffff" if gw in chip_gw_map else "rgba(0,0,0,0)" for gw in gws]
        bar_widths   = [2.5      if gw in chip_gw_map else 0               for gw in gws]
        bar_labels   = [chip_gw_map[gw] if gw in chip_gw_map else "" for gw in gws]

        fig.add_trace(
            go.Bar(
                x=gws,
                y=mgr["gw_points"],
                name=label,
                showlegend=False,
                marker_color=pal["bar"],
                marker_line_color=bar_borders,
                marker_line_width=bar_widths,
                opacity=0.85,
                text=bar_labels,
                textposition="outside",
                textfont=dict(size=8, color=pal["line"], family="Arial Black, sans-serif"),
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "GW %{x}<br>"
                    "Points: <b>%{y}</b><extra></extra>"
                ),
            ),
            row=3, col=1,
        )

    # ── Add final-position annotation on the cumulative chart ──────────────
    for i, mgr in enumerate(all_data):
        pal = PALETTE[i % len(PALETTE)]
        last_gw  = mgr["gw_nums"][-1]
        last_cum = mgr["cumulative"][-1]
        medal    = {1: "🥇", 2: "🥈", 3: "🥉"}.get(mgr["final_rank"], "")
        fig.add_annotation(
            x=last_gw,
            y=last_cum,
            text=f" {medal} {last_cum}",
            showarrow=False,
            xanchor="left",
            font=dict(size=11, color=pal["line"], family="Arial Black, sans-serif"),
            bgcolor="rgba(255,255,255,0.75)",
            borderpad=2,
            row=1, col=1,
        )

    # ── Highlight max-gap GW on the cumulative chart ───────────────────────
    # Find the GW where the gap between 1st and last was largest
    if len(all_data) > 1:
        max_gap, max_gap_gw = 0, 1
        for gw_i, gw in enumerate(all_gws[:min(n_gws, len(all_data[0]["cumulative"]))]):
            vals = [
                m["cumulative"][gw_i]
                for m in all_data
                if gw_i < len(m["cumulative"])
            ]
            gap = max(vals) - min(vals)
            if gap > max_gap:
                max_gap, max_gap_gw = gap, gw
        fig.add_vline(
            x=max_gap_gw,
            line_width=1.2,
            line_dash="dot",
            line_color="rgba(100,100,100,0.45)",
            annotation_text=f"  Max gap  (GW{max_gap_gw}: {max_gap} pts)",
            annotation_font_size=10,
            annotation_font_color="#666666",
            row=1, col=1,
        )

    # ── Global layout ───────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=f"⚽  {league_name}  —  2024/25 Season",
            font=dict(size=24, color="#38003c", family="Arial Black, sans-serif"),
            x=0.5,
            y=0.99,
        ),
        template="plotly_white",
        paper_bgcolor="#f5f5f5",
        plot_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=12, color="#222222"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#dddddd",
            borderwidth=1,
            font=dict(size=13),
        ),
        barmode="group",
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", font_size=12),
        margin=dict(l=60, r=80, t=100, b=50),
        height=1000,
    )

    # Axes styling
    axis_style = dict(
        showgrid=True,
        gridcolor="#eeeeee",
        zeroline=False,
        linecolor="#cccccc",
        tickfont=dict(size=11),
    )
    # ── Chip legend (static annotation bottom-right of cumulative chart) ───
    chip_legend_lines = ["<b>Chips</b>"] + [
        f'<span style="color:{cfg["color"]}">◆</span> {cfg["label"]} = {name.replace("3xc","Triple Captain").replace("bboost","Bench Boost").replace("freehit","Free Hit").replace("wildcard","Wildcard")}'
        for name, cfg in CHIPS.items()
    ]
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.01, y=0.985,
        xanchor="left", yanchor="top",
        text="<br>".join(chip_legend_lines),
        showarrow=False,
        align="left",
        font=dict(size=10, family="Arial, sans-serif"),
        bgcolor="rgba(255,255,255,0.80)",
        bordercolor="#dddddd",
        borderwidth=1,
        borderpad=5,
    )

    fig.update_xaxes(**axis_style, title_text="Gameweek", dtick=2)
    fig.update_yaxes(**axis_style)
    fig.update_yaxes(title_text="Total Points", row=1, col=1)
    fig.update_yaxes(
        title_text="Position",
        row=2, col=1,
        autorange="reversed",
        tickvals=[1, 2, 3],
        ticktext=["🥇 1st", "🥈 2nd", "🥉 3rd"],
        range=[3.4, 0.6],
    )
    fig.update_yaxes(title_text="GW Points", row=3, col=1)

    return fig


# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary(all_data: list[dict]) -> None:
    print("\n── Season Summary ─────────────────────────────────────")
    for mgr in sorted(all_data, key=lambda m: m["final_rank"]):
        best_gw  = max(mgr["gw_points"])
        worst_gw = min(mgr["gw_points"])
        total    = mgr["cumulative"][-1]
        print(
            f"  #{mgr['final_rank']}  {mgr['name']} ({mgr['team_name']})"
            f"  —  {total} pts"
            f"  |  best GW: {best_gw}  worst: {worst_gw}"
            f"  |  hits: -{mgr['transfer_hits']}  bench pts left: {mgr['bench_pts']}"
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    league_name, all_data = fetch_all_data(LEAGUE_ID)
    print_summary(all_data)

    print("\nBuilding visualisation …")
    fig = build_figure(league_name, all_data)
    fig.write_html(OUTPUT_FILE, include_plotlyjs="cdn")
    print(f"Saved → {OUTPUT_FILE}")
    fig.show()


if __name__ == "__main__":
    main()
