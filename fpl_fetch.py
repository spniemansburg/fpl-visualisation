"""
FPL Raw Data Fetcher
Fetches all data for a classic league and writes a self-contained fpl_raw.json.
Run this once per season (or when you want fresh data).

Usage:
    uv run fpl_fetch.py
    uv run fpl_fetch.py --league-id 157910 --output fpl_raw.json

Pipeline:
    fpl_fetch.py → fpl_raw.json → fpl_analyse.py → fpl_data.json → fpl_export.py → fpl_presentation.html
"""

import argparse
import json
import time
from datetime import datetime, timezone

import requests

from fpl_visualisation import LEAGUE_ID

OUTPUT_RAW = "fpl_raw.json"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FPL-vis/1.0)"})


# ── API helpers ────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 15) -> dict:
    r = SESSION.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_bootstrap() -> dict[int, dict]:
    """Return {player_id: {name, team, position}} for every FPL element."""
    print("  Bootstrap …", end=" ", flush=True)
    bs = _get("https://fantasy.premierleague.com/api/bootstrap-static/")
    teams = {t["id"]: t["short_name"] for t in bs["teams"]}
    players = {
        e["id"]: {
            "name":     e["web_name"],
            "team":     teams[e["team"]],
            "position": ["", "GK", "DEF", "MID", "FWD"][e["element_type"]],
        }
        for e in bs["elements"]
    }
    time.sleep(0.3)
    print(f"✓  ({len(players)} players)")
    return players


def fetch_league(league_id: int) -> tuple[str, list[dict]]:
    """Return (league_name, raw standings results)."""
    data = _get(f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/")
    time.sleep(0.3)
    return data["league"]["name"], data["standings"]["results"]


def fetch_entry_history(entry_id: int) -> tuple[list[dict], list[dict]]:
    """Return (gw_records, chips) for one manager."""
    data = _get(f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/")
    time.sleep(0.3)
    return data["current"], data.get("chips", [])


def fetch_gw_live(gw: int) -> dict[int, int]:
    """Return {player_id: total_points} for one finished GW."""
    data = _get(f"https://fantasy.premierleague.com/api/event/{gw}/live/")
    time.sleep(0.2)
    return {e["id"]: e["stats"]["total_points"] for e in data["elements"]}


def fetch_gw_picks(entry_id: int, gw: int) -> list[dict]:
    """Return full picks list for one manager in one GW ([] on 404)."""
    r = SESSION.get(
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/",
        timeout=10,
    )
    time.sleep(0.2)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    data = r.json()
    return data["picks"], data.get("active_chip")


def fetch_transfers(entry_id: int) -> list[dict]:
    """Return full transfer history for one manager (newest first)."""
    data = _get(f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/")
    time.sleep(0.2)
    return data


# ── Season label ───────────────────────────────────────────────────────────────

def _season_label(chips: list[dict]) -> str:
    years: set[int] = set()
    for c in chips:
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


# ── Main fetch orchestration ───────────────────────────────────────────────────

def fetch_all(league_id: int) -> dict:
    """
    Fetch everything and return the raw payload dict.

    Structure:
      meta       – league info, season, fetch timestamp, finished GW list
      players    – {str(id): {name, team, position}}
      managers   – list of manager dicts with gw_history, transfers, chips
    """
    print(f"\nFetching league {league_id} …")
    players = fetch_bootstrap()

    league_name, standings = fetch_league(league_id)
    print(f"  League: {league_name}  ({len(standings)} managers)")

    # ── GW live data (one call per finished GW) ────────────────────────────
    # We derive finished GWs from the first manager's history
    first_entry = standings[0]["entry"]
    raw_history, _ = fetch_entry_history(first_entry)
    finished_gws = [r["event"] for r in raw_history if not (r["points"] == 0 and r["rank"] is None)]
    print(f"  Finished GWs: {len(finished_gws)} ({finished_gws[0]}–{finished_gws[-1]})")

    print(f"  GW live data ({len(finished_gws)} GWs) …", end=" ", flush=True)
    gw_live: dict[int, dict[int, int]] = {}
    for i, gw in enumerate(finished_gws):
        gw_live[gw] = fetch_gw_live(gw)
        if (i + 1) % 10 == 0:
            print(f"GW{gw}…", end=" ", flush=True)
    print("✓")

    # ── Per-manager data ───────────────────────────────────────────────────
    all_chips: list[dict] = []
    managers_out: list[dict] = []

    for standing in standings:
        entry_id  = standing["entry"]
        name      = standing["player_name"]
        team_name = standing["entry_name"]
        rank      = standing["rank"]
        print(f"\n  [{rank}] {name} ({team_name}, entry {entry_id})")

        # GW history + chips (re-fetch properly for each manager)
        gw_records, chips = fetch_entry_history(entry_id)
        all_chips.extend(chips)

        finished = [r for r in gw_records if not (r["points"] == 0 and r["rank"] is None)]

        # Transfers
        print(f"      Transfers …", end=" ", flush=True)
        transfers = fetch_transfers(entry_id)
        print(f"✓  ({len(transfers)} transfers)")

        # Picks per GW — embed gw_points from live data
        print(f"      Picks ({len(finished)} GWs) …", end=" ", flush=True)
        gw_history_out: list[dict] = []
        for fi, rec in enumerate(finished):
            gw = rec["event"]
            live = gw_live.get(gw, {})
            raw_picks, active_chip = fetch_gw_picks(entry_id, gw)

            picks_out = [
                {
                    "element":        p["element"],
                    "position":       p["position"],
                    "multiplier":     p.get("multiplier", 0),
                    "is_captain":     p.get("is_captain", False),
                    "is_vice_captain":p.get("is_vice_captain", False),
                    "gw_points":      live.get(p["element"], 0),
                }
                for p in raw_picks
            ]

            gw_history_out.append({
                "gw":                    gw,
                "points":                rec["points"],
                "total_points":          rec["total_points"],
                "event_transfers":       rec.get("event_transfers", 0),
                "event_transfers_cost":  rec.get("event_transfers_cost", 0),
                "points_on_bench":       rec.get("points_on_bench", 0),
                "overall_rank":          rec.get("overall_rank"),
                "active_chip":           active_chip,
                "picks":                 picks_out,
            })
            if (fi + 1) % 10 == 0:
                print(f"GW{gw}…", end=" ", flush=True)

        print("✓")

        managers_out.append({
            "entry_id":   entry_id,
            "name":       name,
            "team_name":  team_name,
            "final_rank": rank,
            "gw_history": gw_history_out,
            "transfers":  [
                {
                    "element_in":       t["element_in"],
                    "element_out":      t["element_out"],
                    "element_in_cost":  t.get("element_in_cost"),
                    "element_out_cost": t.get("element_out_cost"),
                    "event":            t["event"],
                    "time":             t["time"],
                }
                for t in transfers
            ],
            "chips": [
                {"name": c["name"], "event": c["event"], "time": c["time"]}
                for c in chips
            ],
        })

    season = _season_label(all_chips)

    return {
        "meta": {
            "league_id":    league_id,
            "league_name":  league_name,
            "season":       season,
            "fetched_at":   datetime.now(timezone.utc).isoformat(),
            "finished_gws": finished_gws,
        },
        # keys are strings so JSON round-trips cleanly
        "players": {str(k): v for k, v in players.items()},
        "managers": managers_out,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FPL raw data fetcher")
    parser.add_argument("--league-id", type=int, default=LEAGUE_ID)
    parser.add_argument("--output", default=OUTPUT_RAW)
    args = parser.parse_args()

    payload = fetch_all(args.league_id)

    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)

    n_mgrs = len(payload["managers"])
    n_gws  = len(payload["meta"]["finished_gws"])
    n_pl   = len(payload["players"])
    print(f"\nSaved → {args.output}")
    print(f"  {n_mgrs} managers · {n_gws} finished GWs · {n_pl} players in metadata")


if __name__ == "__main__":
    main()
