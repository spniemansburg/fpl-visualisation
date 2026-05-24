"""
FPL Race Animation
Animated bar-chart race — cumulative points building up gameweek by gameweek.
Produces a self-contained dark-themed HTML file for presentations.

Usage:
    uv run fpl_race.py
    uv run fpl_race.py --league-id 157910 --speed 700

Requirements (via uv): requests, plotly
"""

import argparse
import plotly.graph_objects as go

from fpl_visualisation import fetch_all_data, CHIPS, PALETTE, LEAGUE_ID

# ── Defaults ───────────────────────────────────────────────────────────────────
OUTPUT_FILE    = "fpl_race.html"
FRAME_DURATION = 700   # ms per GW frame
TRANSITION_MS  = 500   # bar-slide transition

# Dark FPL-purple theme
BG_DARK   = "#0e0e1a"
BG_PLOT   = "#0e0e1a"
PURPLE    = "#38003c"
ACCENT    = "#6a0dad"
TEXT_DIM  = "rgba(255,255,255,0.45)"
TEXT_MID  = "rgba(255,255,255,0.70)"
TEXT_FULL = "#ffffff"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pts_at(mgr: dict, gw_i: int) -> int:
    return mgr["cumulative"][min(gw_i, len(mgr["cumulative"]) - 1)]


def _season_label(all_data: list[dict]) -> str:
    """Derive '2025/26' from the earliest chip/GW timestamp in the data."""
    years: set[int] = set()
    for mgr in all_data:
        for c in mgr.get("chips", []):
            try:
                years.add(int(c["time"][:4]))
            except (ValueError, IndexError):
                pass
    if len(years) >= 2:
        lo, hi = min(years), max(years)
        return f"{lo}/{str(hi)[2:]}"
    if years:
        y = next(iter(years))
        return f"{y}/{str(y + 1)[2:]}"
    return "Season"


def _snapshot(all_data: list[dict], gw_i: int) -> list[tuple[int, dict, int]]:
    """Return [(original_index, mgr, pts)] sorted ascending (bottom = last place)."""
    snap = [(i, m, _pts_at(m, gw_i)) for i, m in enumerate(all_data)]
    snap.sort(key=lambda t: t[2])
    return snap


def _bar_trace(snap: list[tuple], gw_i: int, max_pts: int) -> go.Bar:
    """Build the Bar trace for one frame."""
    chip_map: dict[int, str] = {}
    for i, mgr, _ in snap:
        for c in mgr.get("chips", []):
            if c["event"] == gw_i + 1:
                chip_map[i] = CHIPS.get(c["name"], {}).get("label", "?")

    y_labels, x_vals, colors, texts = [], [], [], []
    for i, mgr, pts in snap:
        chip_tag = f"  [{chip_map[i]}]" if i in chip_map else ""
        y_labels.append(f"<b>{mgr['name']}</b>  ·  {mgr['team_name']}{chip_tag}")
        x_vals.append(pts)
        colors.append(PALETTE[i % len(PALETTE)]["bar"])
        texts.append(f"  {pts}")

    return go.Bar(
        x=x_vals,
        y=y_labels,
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=texts,
        textposition="outside",
        textfont=dict(size=15, color=TEXT_FULL, family="Arial Black, sans-serif"),
        cliponaxis=False,
        hoverinfo="skip",
    )


def _frame_layout(gw_i: int, n_gws: int) -> go.Layout:
    """Per-frame layout carrying the GW watermark and subtitle."""
    return go.Layout(
        annotations=[
            # Large faint watermark
            dict(
                x=0.98, y=0.03,
                xref="paper", yref="paper",
                text=f"<b>GW{gw_i + 1}</b>",
                showarrow=False,
                xanchor="right", yanchor="bottom",
                font=dict(size=90, color="rgba(255,255,255,0.06)",
                          family="Arial Black, sans-serif"),
            ),
            # Readable label top-right
            dict(
                x=0.99, y=0.99,
                xref="paper", yref="paper",
                text=f"Gameweek {gw_i + 1} of {n_gws}",
                showarrow=False,
                xanchor="right", yanchor="top",
                font=dict(size=13, color=TEXT_DIM, family="Arial, sans-serif"),
            ),
        ]
    )


# ── Main figure builder ────────────────────────────────────────────────────────

def build_race(league_name: str, all_data: list[dict],
               frame_ms: int = FRAME_DURATION,
               transition_ms: int = TRANSITION_MS) -> go.Figure:

    n_gws   = max(len(m["gw_nums"]) for m in all_data)
    max_pts = max(m["cumulative"][-1] for m in all_data)
    season  = _season_label(all_data)

    # ── Frames ─────────────────────────────────────────────────────────────
    frames = [
        go.Frame(
            data=[_bar_trace(_snapshot(all_data, gw_i), gw_i, max_pts)],
            layout=_frame_layout(gw_i, n_gws),
            name=str(gw_i + 1),
        )
        for gw_i in range(n_gws)
    ]

    # ── Slider ─────────────────────────────────────────────────────────────
    slider_steps = [
        dict(
            args=[[str(gw + 1)], dict(
                frame=dict(duration=frame_ms, redraw=True),
                mode="immediate",
                transition=dict(duration=transition_ms),
            )],
            label=str(gw + 1),
            method="animate",
        )
        for gw in range(n_gws)
    ]

    # ── Figure ─────────────────────────────────────────────────────────────
    initial_snap = _snapshot(all_data, 0)

    fig = go.Figure(
        data=[_bar_trace(initial_snap, 0, max_pts)],
        frames=frames,
        layout=go.Layout(
            title=dict(
                text=f"⚽  {league_name}  —  {season} Points Race",
                font=dict(size=22, color=TEXT_FULL, family="Arial Black, sans-serif"),
                x=0.5,
            ),
            paper_bgcolor=BG_DARK,
            plot_bgcolor=BG_PLOT,
            font=dict(color=TEXT_FULL, family="Arial, sans-serif"),

            xaxis=dict(
                range=[0, max_pts * 1.14],
                showgrid=True,
                gridcolor="rgba(255,255,255,0.06)",
                tickfont=dict(size=11, color=TEXT_DIM),
                zeroline=False,
                showline=False,
                title=dict(text="Cumulative Points", font=dict(color=TEXT_DIM, size=12)),
            ),
            yaxis=dict(
                showgrid=False,
                tickfont=dict(size=13, color=TEXT_FULL),
                zeroline=False,
                automargin=True,
            ),

            bargap=0.35,
            height=380,
            margin=dict(l=20, r=100, t=70, b=110),

            annotations=_frame_layout(0, n_gws).annotations,

            # ── Play / Pause ───────────────────────────────────────────────
            updatemenus=[dict(
                type="buttons",
                showactive=False,
                x=0.0, y=-0.22,
                xanchor="left", yanchor="top",
                buttons=[
                    dict(
                        label="▶  Play",
                        method="animate",
                        args=[None, dict(
                            frame=dict(duration=frame_ms, redraw=True),
                            fromcurrent=True,
                            transition=dict(duration=transition_ms,
                                            easing="cubic-in-out"),
                        )],
                    ),
                    dict(
                        label="⏸  Pause",
                        method="animate",
                        args=[[None], dict(
                            frame=dict(duration=0, redraw=False),
                            mode="immediate",
                            transition=dict(duration=0),
                        )],
                    ),
                ],
                font=dict(size=13, color=TEXT_FULL),
                bgcolor=PURPLE,
                bordercolor=ACCENT,
                borderwidth=1,
                pad=dict(r=8, l=8, t=6, b=6),
            )],

            # ── GW scrubber ────────────────────────────────────────────────
            sliders=[dict(
                active=0,
                x=0.0, y=0,
                len=1.0,
                xanchor="left", yanchor="top",
                pad=dict(b=10, t=55),
                currentvalue=dict(
                    prefix="GW ",
                    visible=True,
                    xanchor="center",
                    font=dict(size=14, color=TEXT_FULL),
                ),
                transition=dict(duration=transition_ms, easing="cubic-in-out"),
                steps=slider_steps,
                bgcolor=PURPLE,
                bordercolor=ACCENT,
                tickcolor=TEXT_DIM,
                font=dict(color=TEXT_DIM, size=9),
            )],
        ),
    )

    return fig


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FPL animated race chart")
    parser.add_argument("--league-id", type=int, default=LEAGUE_ID,
                        help="FPL classic league ID (default: %(default)s)")
    parser.add_argument("--speed", type=int, default=FRAME_DURATION,
                        help="ms per gameweek frame (lower = faster, default: %(default)s)")
    parser.add_argument("--output", default=OUTPUT_FILE,
                        help="Output HTML path (default: %(default)s)")
    args = parser.parse_args()

    league_name, all_data = fetch_all_data(args.league_id)

    print("\nBuilding race animation …")
    fig = build_race(league_name, all_data, frame_ms=args.speed)
    fig.write_html(args.output, include_plotlyjs="cdn")
    print(f"Saved → {args.output}")
    fig.show()


if __name__ == "__main__":
    main()
