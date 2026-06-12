"""
FPL Gameweek-Data Exporter (Flourish line-chart-race format)
Reads fpl_data.json (produced by fpl_analyse.py) and writes a wide CSV:
one row per manager, one column per gameweek (cumulative points).

Usage:
    uv run fpl_export_gw_data.py
    uv run fpl_export_gw_data.py --input fpl_data.json --output fpl_gw_data.csv

Output layout (matches Flourish "Line chart race" Data tab):
    GW,      0,  1,   2,   3,   …
    Stephan, 0,  72,  108, 158, …
    Maurice, 0,  …
    Avelino, 0,  …

Pipeline:
    fpl_fetch.py → fpl_raw.json → fpl_analyse.py → fpl_data.json → fpl_export_gw_data.py → fpl_gw_data.csv
"""

import argparse
import csv
import json

INPUT_DATA = "fpl_data.json"
OUTPUT_CSV = "fpl_gw_data.csv"


def build_rows(payload: dict) -> list[list]:
    managers = payload["managers"]
    n = max(len(m["gw_nums"]) for m in managers)

    # Header: label column "GW", then 0, 1, 2, … n (GW0 = baseline, GW1…n = season)
    header = ["GW", *range(0, n + 1)]
    rows = [header]

    for m in managers:
        first_name = m["name"].split()[0]
        cum = m["cumulative"]
        # GW0 baseline = 0, then cumulative values; pad with "" if manager has fewer GWs
        vals = [0] + [cum[i] if i < len(cum) else "" for i in range(n)]
        rows.append([first_name, *vals])

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="FPL gameweek-data exporter (Flourish CSV)")
    parser.add_argument("--input",  default=INPUT_DATA, help="Input JSON  (default: %(default)s)")
    parser.add_argument("--output", default=OUTPUT_CSV, help="Output CSV  (default: %(default)s)")
    args = parser.parse_args()

    print(f"Reading {args.input} …")
    with open(args.input) as f:
        payload = json.load(f)

    rows = build_rows(payload)

    with open(args.output, "w", newline="") as f:
        csv.writer(f).writerows(rows)

    n_managers = len(rows) - 1
    n_cols = len(rows[0]) - 1
    print(f"Saved → {args.output}  ({n_managers} managers × {n_cols} columns)")


if __name__ == "__main__":
    main()
