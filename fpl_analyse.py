"""
FPL Analysis Script
Reads fpl_raw.json and computes derived player + league stats.
Writes fpl_data.json — the input consumed by fpl_export.py.

Usage:
    uv run fpl_analyse.py
    uv run fpl_analyse.py --input fpl_raw.json --output fpl_data.json

Pipeline:
    fpl_fetch.py → fpl_raw.json → fpl_analyse.py → fpl_data.json → fpl_export.py → fpl_presentation.html
"""

import argparse
import json
import statistics

from fpl_visualisation import PALETTE, CHIPS

INPUT_RAW  = "fpl_raw.json"
OUTPUT_DATA = "fpl_data.json"


# ── Player stats ───────────────────────────────────────────────────────────────

def _player_stats(mgr: dict, first_gw: int, last_gw: int) -> list[dict]:
    """
    Compute per-player stats for one manager from their gw_history.
    Tracks all 15 squad positions (bench included).

    Returns list sorted by total_pts_contributed descending.
    """
    acc: dict[int, dict] = {}   # player_id → accumulator

    for gw_row in mgr["gw_history"]:
        gw = gw_row["gw"]
        for pick in gw_row["picks"]:
            pid  = pick["element"]
            pts  = pick["gw_points"]
            mult = pick.get("multiplier", 0)
            cap  = pick.get("is_captain", False)

            if pid not in acc:
                acc[pid] = {
                    "id":                  pid,
                    "total_pts_contributed": 0,   # pts × multiplier (score impact)
                    "total_pts_scored":    0,     # raw player output
                    "bench_pts":           0,     # pts while on bench
                    "gws_owned":           0,     # GWs in squad (any position)
                    "gws_in_xi":           0,     # GWs with multiplier > 0
                    "gws_as_captain":      0,
                    "gw_list":             [],    # for first/last owned
                }

            a = acc[pid]
            a["total_pts_contributed"] += pts * mult
            a["total_pts_scored"]      += pts
            a["gws_owned"]             += 1
            a["gw_list"].append(gw)
            if mult > 0:
                a["gws_in_xi"] += 1
            else:
                a["bench_pts"] += pts
            if cap:
                a["gws_as_captain"] += 1

    # Transfer in/out lookup
    in_events:  dict[int, list[dict]] = {}
    out_events: dict[int, list[dict]] = {}
    for t in mgr.get("transfers", []):
        ev = {"gw": t["event"], "date": t["time"][:10]}
        in_events.setdefault(t["element_in"],  []).append(ev)
        out_events.setdefault(t["element_out"], []).append(ev)

    result = []
    for pid, a in acc.items():
        gw_list      = sorted(a["gw_list"])
        first_owned  = gw_list[0]
        last_owned   = gw_list[-1]

        result.append({
            "id":                    pid,
            "total_pts_contributed": a["total_pts_contributed"],
            "total_pts_scored":      a["total_pts_scored"],
            "bench_pts":             a["bench_pts"],
            "gws_owned":             a["gws_owned"],
            "gws_in_xi":             a["gws_in_xi"],
            "gws_as_captain":        a["gws_as_captain"],
            "first_gw_owned":        first_owned,
            "last_gw_owned":         last_owned,
            "in_from_start":         first_owned == first_gw,
            "still_in":              last_owned  == last_gw,
            "transfer_in_events":    sorted(in_events.get(pid, []),  key=lambda e: e["gw"]),
            "transfer_out_events":   sorted(out_events.get(pid, []), key=lambda e: e["gw"]),
        })

    result.sort(key=lambda p: p["total_pts_contributed"], reverse=True)
    return result


# ── League stats ───────────────────────────────────────────────────────────────

def _compute_stats(managers: list[dict]) -> dict:
    """Best GW across all managers + widest in-league points gap per GW."""
    best_mgr, best_gw_i, best_pts = None, 0, 0
    for mgr in managers:
        for i, pts in enumerate(mgr["gw_points"]):
            if pts > best_pts:
                best_mgr, best_gw_i, best_pts = mgr, i, pts

    n_gws = max(len(m["cumulative"]) for m in managers)
    max_gap, max_gap_gw = 0, 1
    for gw_i in range(n_gws):
        vals = [m["cumulative"][gw_i] for m in managers if gw_i < len(m["cumulative"])]
        gap = max(vals) - min(vals)
        if gap > max_gap:
            max_gap, max_gap_gw = gap, gw_i + 1

    return {
        "best_gw": {
            "manager": best_mgr["name"],
            "team":    best_mgr["team_name"],
            "gw":      best_mgr["gw_nums"][best_gw_i],
            "pts":     best_pts,
        },
        "max_gap": {"gw": max_gap_gw, "pts": max_gap},
    }


def _compute_league_ranks(managers: list[dict]) -> list[dict]:
    """Add per-GW mini-league rank to each manager dict."""
    n_gws = max(len(m["cumulative"]) for m in managers)
    for gw_i in range(n_gws):
        snapshot = [(i, m["cumulative"][gw_i] if gw_i < len(m["cumulative"]) else 0)
                    for i, m in enumerate(managers)]
        snapshot.sort(key=lambda x: -x[1])
        for rank, (mi, _) in enumerate(snapshot):
            managers[mi].setdefault("league_rank", []).append(rank + 1)
    return managers


# ── Season analysis ────────────────────────────────────────────────────────────

def _compute_season_decided(managers: list[dict]) -> dict:
    """Compute four decisive-factor metrics for the 'Where Was The Race Decided?' slide.
    managers must be sorted by final_rank ascending (index 0 = winner).
    """
    # Consistency: stdev of GW scores — lower = steadier
    consistency = [round(statistics.stdev(m["gw_points"]), 1) for m in managers]

    # Chip returns: avg score on chip weeks minus that manager's season average
    def chip_return(m: dict) -> float:
        season_avg = sum(m["gw_points"]) / len(m["gw_points"])
        chip_gws   = {c["event"] for c in m.get("chips", [])}
        scores     = [m["gw_points"][m["gw_nums"].index(gw)]
                      for gw in chip_gws if gw in m["gw_nums"]]
        return round(sum(scores) / len(scores) - season_avg, 1) if scores else 0.0

    chip_returns = [chip_return(m) for m in managers]

    # Captaincy: total bonus pts from the armband (multiplier − 1) × player pts
    captaincy = [m["captain_bonus"] for m in managers]

    # Mistakes: points left on bench + transfer hit cost (lower = better)
    mistakes = [m["bench_pts"] + m["transfer_hits"] for m in managers]

    # Verdict sentence comparing the top two
    leader, runner = managers[0], managers[1]
    margin   = leader["cumulative"][-1] - runner["cumulative"][-1]
    ln, rn   = leader["name"].split()[0], runner["name"].split()[0]

    advantages = []
    cap_diff     = captaincy[0] - captaincy[1]
    mistake_diff = mistakes[1] - mistakes[0]  # positive = runner wasted more
    chip_diff    = chip_returns[0] - chip_returns[1]
    cons_diff    = consistency[1] - consistency[0]  # positive = leader is steadier

    if cap_diff > 5:
        advantages.append(f"+{cap_diff} aanvoerdersbonus")
    if cons_diff > 0:
        advantages.append(f"stabieler scoren ({consistency[0]} vs {consistency[1]} σ)")
    if mistake_diff > 5:
        advantages.append(f"{mistake_diff} minder punten verspild")
    if chip_diff > 2:
        advantages.append(f"betere chip-timing (+{round(chip_diff, 1)}/chip GW)")

    if advantages:
        verdict = f"{ln}'s {' en '.join(advantages[:2])} tegenover {rn} besliste de race met {margin} punten verschil."
    else:
        verdict = (f"Een haarfijn verschil van {margin} punten — kleine voordelen over 38 speelweken "
                   f"scheidden {ln} en {rn} aan het einde.")

    return {
        "consistency":  consistency,
        "chip_returns": chip_returns,
        "captaincy":    captaincy,
        "mistakes":     mistakes,
        "verdict":      verdict,
    }


# ── Main analysis ──────────────────────────────────────────────────────────────

def analyse(raw: dict) -> dict:
    """
    Build the fpl_data.json payload from fpl_raw.json.

    Manager fields added vs raw:
      color, gw_nums, gw_points, cumulative, transfer_hits, bench_pts (season total),
      chips (enriched with label/color), players (full per-player stats), top_players (top 3),
      league_rank (per-GW position)
    """
    meta          = raw["meta"]
    player_meta   = raw["players"]   # str(id) → {name, team, position}
    finished_gws  = meta["finished_gws"]
    first_gw      = finished_gws[0]
    last_gw       = finished_gws[-1]

    managers_out: list[dict] = []
    for i, mgr in enumerate(sorted(raw["managers"], key=lambda m: m["final_rank"])):
        pal = PALETTE[i % len(PALETTE)]

        # ── GW-level series ────────────────────────────────────────────────
        gw_nums, gw_points, cumulative = [], [], []
        running = 0
        captain_bonus = 0
        for row in mgr["gw_history"]:
            net = row["points"] - row.get("event_transfers_cost", 0)
            running += net
            gw_nums.append(row["gw"])
            gw_points.append(net)
            cumulative.append(running)
            for pick in row.get("picks", []):
                if pick.get("is_captain", False) and pick.get("multiplier", 0) > 0:
                    captain_bonus += pick["gw_points"] * (pick["multiplier"] - 1)

        transfer_hits = sum(r.get("event_transfers_cost", 0) for r in mgr["gw_history"])
        bench_total   = sum(r.get("points_on_bench", 0)      for r in mgr["gw_history"])

        # ── Chips (enriched) ───────────────────────────────────────────────
        chips_out = []
        for c in mgr.get("chips", []):
            # Only include chips played in a finished GW
            if c["event"] not in finished_gws:
                continue
            cfg = CHIPS.get(c["name"], {"label": c["name"], "color": "#888"})
            chips_out.append({
                "name":  c["name"],
                "label": cfg["label"],
                "color": cfg["color"],
                "event": c["event"],
                "date":  c["time"][:10],
            })

        # ── Per-player stats ───────────────────────────────────────────────
        players = _player_stats(mgr, first_gw, last_gw)

        # Attach player name/team/position from bootstrap
        for p in players:
            meta_p = player_meta.get(str(p["id"]), {})
            p["name"]     = meta_p.get("name", f"#{p['id']}")
            p["team"]     = meta_p.get("team", "?")
            p["position"] = meta_p.get("position", "?")

        managers_out.append({
            "name":          mgr["name"],
            "team_name":     mgr["team_name"],
            "entry_id":      mgr["entry_id"],
            "final_rank":    mgr["final_rank"],
            "color":         pal["bar"],
            "gw_nums":       gw_nums,
            "gw_points":     gw_points,
            "cumulative":    cumulative,
            "transfer_hits": transfer_hits,
            "bench_pts":     bench_total,
            "captain_bonus": captain_bonus,
            "chips":         chips_out,
            "players":       players,
            "top_players":   [
                {
                    "id":            p["id"],
                    "name":          p["name"],
                    "team":          p["team"],
                    "position":      p["position"],
                    "total_pts":     p["total_pts_contributed"],
                    "gws_owned":     p["gws_owned"],
                    "gws_in_xi":     p["gws_in_xi"],
                    "first_gw":      p["first_gw_owned"],
                    "last_gw":       p["last_gw_owned"],
                    "in_from_start": p["in_from_start"],
                    "still_in":      p["still_in"],
                }
                for p in players[:5]
            ],
        })

    # Add league ranks
    managers_out = _compute_league_ranks(managers_out)

    stats = _compute_stats(managers_out)
    stats["season_decided"] = _compute_season_decided(managers_out)

    return {
        "league": {
            "name":   meta["league_name"],
            "season": meta["season"],
        },
        "managers": managers_out,
        "stats":    stats,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FPL analysis — raw JSON → data JSON")
    parser.add_argument("--input",  default=INPUT_RAW)
    parser.add_argument("--output", default=OUTPUT_DATA)
    args = parser.parse_args()

    print(f"Reading {args.input} …")
    with open(args.input) as f:
        raw = json.load(f)

    payload = analyse(raw)

    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved → {args.output}")
    print("\nSeason summary:")
    for mgr in sorted(payload["managers"], key=lambda m: m["final_rank"]):
        total = mgr["cumulative"][-1]
        top3  = ", ".join(p["name"] for p in mgr["top_players"])
        all_p = len(mgr["players"])
        print(f"  #{mgr['final_rank']}  {mgr['name']} ({mgr['team_name']})  —  {total} pts")
        print(f"        Top players: {top3}  ({all_p} unique players tracked)")


if __name__ == "__main__":
    main()
