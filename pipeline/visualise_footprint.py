#!/usr/bin/env python3
"""
Debt Footprint Visualisation
MSc Dissertation — Technical Debt Evolution

Usage:
    python3 visualise_footprint.py --repo piggymetrics
    python3 visualise_footprint.py --mode compare
"""

import argparse
import csv
import sys
from pathlib import Path
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")  # headless — no display required
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
import numpy as np

RESULTS_DIR = Path(__file__).parent.parent / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
STYLE = "seaborn-v0_8-whitegrid"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_repo(repo_name: str) -> list[dict]:
    """Load and clean a repo's results CSV.  Returns rows sorted by commit_date."""
    path = RESULTS_DIR / f"{repo_name}_results.csv"
    if not path.exists():
        sys.exit(f"Error: {path} not found.")

    # Every dated row is collected first, valid or not.  Commits excluded by
    # SonarQube (SCAN_FAILED / ANALYSIS_FAILED) still occupy a position in the
    # repository's history, and that position is what makes a gap detectable
    # later.  Rows are written in git-log order, which is not commit-date order,
    # so adjacency has to be established after sorting rather than from the
    # file's own row order.
    all_rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            date_str = row.get("commit_date", "")
            try:
                # ISO 8601 with timezone offset — normalise to UTC
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            sqale_val = None
            if row.get("build_status") != "ANALYSIS_FAILED":
                try:
                    sqale_val = float(row.get("sqale_index", ""))
                except ValueError:
                    sqale_val = None
            ncloc_val = None
            if row.get("ncloc"):
                try:
                    ncloc_val = float(row["ncloc"])
                except ValueError:
                    pass

            all_rows.append({
                "date": dt,
                "sqale": sqale_val,
                "ncloc": ncloc_val,
                "status": row.get("build_status", ""),
                "message": row.get("commit_message", ""),
                "hash": row.get("commit_hash", "")[:8],
            })

    all_rows.sort(key=lambda r: r["date"])
    # seq is the row's position among *all* commits in chronological order, so
    # two measured commits are adjacent in history only when their seq values
    # differ by exactly one.
    for seq, row in enumerate(all_rows):
        row["seq"] = seq

    return [r for r in all_rows if r["sqale"] is not None]


# ---------------------------------------------------------------------------
# Single-repo chart (--mode single / default)
# ---------------------------------------------------------------------------

def plot_single(repo_name: str) -> None:
    rows = load_repo(repo_name)
    if len(rows) < 2:
        sys.exit(f"Not enough data points for {repo_name} (need ≥ 2).")

    dates   = [r["date"]  for r in rows]
    sqale   = [r["sqale"] for r in rows]
    ncloc   = [r["ncloc"] for r in rows]
    statuses = [r["status"] for r in rows]

    # ---- Identify top-3 single-commit debt increases ----
    # A delta is only a *single-commit* increase when the two rows it spans are
    # adjacent in the source CSV.  Where excluded commits sit between them the
    # change accumulated over the whole gap, so it is not attributable to one
    # commit and is skipped rather than reported.
    deltas = [(0, 0)]
    for i in range(1, len(rows)):
        if rows[i]["seq"] - rows[i - 1]["seq"] != 1:
            continue  # gap: excluded commit(s) in between
        deltas.append((i, sqale[i] - sqale[i - 1]))
    top3 = sorted(deltas, key=lambda x: x[1], reverse=True)[:3]
    top3 = [(i, d) for (i, d) in top3 if d > 0]

    # ---- Summary to stdout ----
    start_debt = sqale[0]
    end_debt   = sqale[-1]
    growth     = end_debt - start_debt
    pct_growth = (growth / start_debt * 100) if start_debt > 0 else float("inf")

    best_i, best_delta = max(deltas, key=lambda x: x[1])
    best_row = rows[best_i]

    # Monotonicity check
    declines = sum(1 for i in range(1, len(sqale)) if sqale[i] < sqale[i - 1])
    plateaus = sum(1 for i in range(1, len(sqale)) if sqale[i] == sqale[i - 1])
    if declines == 0 and plateaus == 0:
        shape = "monotonically increasing"
    elif declines == 0:
        shape = f"generally increasing with {plateaus} plateau periods"
    else:
        shape = f"non-monotonic ({declines} decline commits, {plateaus} plateau commits)"

    print(f"\n{'='*60}")
    print(f"  {repo_name} — Debt Footprint Summary")
    print(f"{'='*60}")
    print(f"  Commits analysed : {len(rows)}")
    print(f"  Date range       : {dates[0].strftime('%Y-%m-%d')} → {dates[-1].strftime('%Y-%m-%d')}")
    print(f"  Start debt       : {start_debt:,.0f} min")
    print(f"  End debt         : {end_debt:,.0f} min")
    print(f"  Total growth     : {growth:+,.0f} min ({pct_growth:+.1f}%)")
    print(f"  Debt shape       : {shape}")
    print(f"  Largest jump     : +{best_delta:,.0f} min on {best_row['date'].strftime('%Y-%m-%d')}")
    print(f"                     [{best_row['hash']}] {best_row['message'][:70]}")
    print(f"{'='*60}\n")

    # ---- Plot ----
    plt.style.use(STYLE)
    fig, ax1 = plt.subplots(figsize=(14, 6))

    # Shaded regions for BUILD_FAILED_SCAN_OK
    in_region = False
    region_start = None
    for i, (d, s) in enumerate(zip(dates, statuses)):
        if s == "BUILD_FAILED_SCAN_OK" and not in_region:
            region_start = d
            in_region = True
        elif s != "BUILD_FAILED_SCAN_OK" and in_region:
            ax1.axvspan(region_start, d, color="#f5e642", alpha=0.15, linewidth=0)
            in_region = False
    if in_region:
        ax1.axvspan(region_start, dates[-1], color="#f5e642", alpha=0.15, linewidth=0)

    # Primary line: sqale_index
    # Break the line wherever excluded commits sit between two measurements.
    # Drawn continuously, a gap renders as a single near-vertical cliff and
    # reads as one enormous commit — which is precisely the misreading the
    # gap-aware delta calculation above exists to prevent.
    sqale_gapped = list(sqale)
    for i in range(1, len(rows)):
        if rows[i]["seq"] - rows[i - 1]["seq"] != 1:
            sqale_gapped[i] = float("nan")
    ax1.plot(dates, sqale_gapped, color="#2563eb", linewidth=1.5, zorder=3, label="_nolegend_")
    ax1.set_xlabel("Commit date", fontsize=11)
    ax1.set_ylabel("Technical debt (remediation minutes)", fontsize=11, color="#1e3a8a")
    ax1.tick_params(axis="y", labelcolor="#1e3a8a")
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda x, _: f"{int(x):,}"
    ))

    # X-axis date formatting
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate(rotation=30, ha="right")

    # Secondary axis: ncloc
    ax2 = ax1.twinx()
    ncloc_clean = [v if v is not None else float("nan") for v in ncloc]
    ax2.plot(dates, ncloc_clean, color="#9ca3af", linewidth=1.0,
             linestyle="--", zorder=2, label="_nolegend_")
    ax2.set_ylabel("Lines of code (ncloc)", fontsize=10, color="#6b7280")
    ax2.tick_params(axis="y", labelcolor="#6b7280")
    ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda x, _: f"{int(x):,}"
    ))

    # Annotations for top-3 jumps
    for rank, (i, delta) in enumerate(top3):
        d = dates[i]
        y = sqale[i]
        msg = rows[i]["message"][:40]
        ax1.axvline(x=d, color="#dc2626", linewidth=0.8, linestyle=":", alpha=0.7, zorder=4)
        va = "bottom" if rank % 2 == 0 else "top"
        offset = 0.03 if va == "bottom" else -0.03
        ax1.annotate(
            f"+{delta:,.0f} min\n{msg}",
            xy=(d, y),
            xytext=(d, ax1.get_ylim()[0] + (ax1.get_ylim()[1] - ax1.get_ylim()[0]) * (0.72 - rank * 0.22)),
            fontsize=6.5,
            color="#dc2626",
            ha="center",
            arrowprops=None,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#dc2626", alpha=0.7, linewidth=0.5),
        )

    # Grid — horizontal only
    ax1.yaxis.grid(True, color="#d1d5db", alpha=0.3, linewidth=0.7)
    ax1.xaxis.grid(False)
    ax2.yaxis.grid(False)

    # Legend
    legend_elements = [
        Line2D([0], [0], color="#2563eb", linewidth=1.5, label="TD (SQALE index)"),
        Line2D([0], [0], color="#9ca3af", linewidth=1.0, linestyle="--", label="Lines of code (ncloc)"),
        matplotlib.patches.Patch(facecolor="#f5e642", alpha=0.4, label="Build failed, source scan only"),
    ]
    ax1.legend(handles=legend_elements, loc="upper left", fontsize=9,
               framealpha=0.9, edgecolor="#e5e7eb")

    repo_title = repo_name.replace("-", " ").replace("_", " ").title()
    ax1.set_title(f"{repo_title}: Technical Debt Evolution", fontsize=13, fontweight="bold", pad=12)

    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIGURES_DIR / f"{repo_name}_footprint.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


# ---------------------------------------------------------------------------
# Multi-repo comparison chart (--mode compare)
# ---------------------------------------------------------------------------

def plot_compare() -> None:
    csv_files = sorted(RESULTS_DIR.glob("*_results.csv"))
    if not csv_files:
        sys.exit("No results CSVs found in results/")

    plt.style.use(STYLE)
    fig, ax = plt.subplots(figsize=(14, 6))

    # Colour cycle — use tab10 for up to 10 repos
    colours = plt.cm.tab10.colors
    plotted = 0

    for i, csv_path in enumerate(csv_files):
        repo_name = csv_path.stem.replace("_results", "")
        rows = load_repo(repo_name)
        if len(rows) < 10:
            print(f"Skipping {repo_name}: only {len(rows)} valid data points (need ≥ 10)")
            continue

        sqale = [r["sqale"] for r in rows]
        sq_min, sq_max = min(sqale), max(sqale)
        if sq_max == sq_min:
            print(f"Skipping {repo_name}: flat sqale_index (no variation)")
            continue

        # Normalise sqale to 0-100
        norm = [(v - sq_min) / (sq_max - sq_min) * 100 for v in sqale]
        # Normalise time to 0-100
        n = len(rows)
        time_norm = [j / (n - 1) * 100 for j in range(n)]

        colour = colours[plotted % len(colours)]
        label = repo_name.replace("-", " ").replace("_", " ").title()
        ax.plot(time_norm, norm, color=colour, linewidth=1.5, label=label, alpha=0.85)
        plotted += 1

    if plotted == 0:
        sys.exit("No repos had enough data points to plot.")

    ax.set_xlabel("Commit history (% through total commits)", fontsize=11)
    ax.set_ylabel("Normalised technical debt (0 = min, 100 = max)", fontsize=11)
    ax.set_title("Technical Debt Evolution: Cross-Repository Comparison", fontsize=13, fontweight="bold", pad=12)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9, edgecolor="#e5e7eb")
    ax.set_xlim(0, 100)
    ax.set_ylim(-2, 105)
    ax.yaxis.grid(True, color="#d1d5db", alpha=0.3, linewidth=0.7)
    ax.xaxis.grid(False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{int(x)}%"))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{int(x)}"))

    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIGURES_DIR / "all_repos_comparison.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {out}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Debt footprint visualisation")
    parser.add_argument("--repo", help="Repo name (e.g. piggymetrics)")
    parser.add_argument("--mode", choices=["single", "compare"], default="single",
                        help="'single' for one repo, 'compare' for all repos overlaid")
    args = parser.parse_args()

    if args.mode == "compare":
        plot_compare()
    else:
        if not args.repo:
            parser.error("--repo is required in single mode")
        plot_single(args.repo)


if __name__ == "__main__":
    main()
