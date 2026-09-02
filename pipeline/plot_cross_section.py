#!/usr/bin/env python3
"""
Cross-sectional debt comparison figure
MSc Dissertation, Technical Debt Evolution in Microservice Systems

Produces the two-panel figure used in Chapter Four: absolute technical debt at
each repository's most recent commit on a log scale, and debt density expressed
as remediation minutes per thousand lines of code.

Density is the more informative of the two. Absolute debt largely tracks
codebase size, so ranking systems by it mostly re-states which are biggest.
Dividing by size asks a different question: how much debt does this system
carry for the amount of code it has.

Usage:
    python3 plot_cross_section.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"


def final_measures():
    rows = []
    for path in sorted(RESULTS_DIR.glob("*_results.csv")):
        repo = path.name.replace("_results.csv", "")
        df = pd.read_csv(path)
        df["dt"] = pd.to_datetime(df["commit_date"], format="mixed", utc=True)
        df = df.dropna(subset=["sqale_index", "ncloc"]).sort_values("dt")
        if df.empty:
            continue
        last = df.iloc[-1]
        rows.append({
            "repo": repo,
            "sqale": float(last["sqale_index"]),
            "ncloc": float(last["ncloc"]),
            "density": float(last["sqale_index"]) / float(last["ncloc"]) * 1000,
        })
    return pd.DataFrame(rows)


def main() -> None:
    d = final_measures()
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5))

    a = d.sort_values("sqale", ascending=True)
    ax1.barh(a["repo"], a["sqale"], color="#2563eb", alpha=0.85)
    ax1.set_xscale("log")
    ax1.set_xlabel("Technical debt at most recent commit (remediation minutes, log scale)")
    ax1.set_title("(a) Absolute technical debt", fontweight="bold", loc="left")
    for i, v in enumerate(a["sqale"]):
        ax1.text(v * 1.1, i, f"{v:,.0f}", va="center", fontsize=8.5)
    ax1.set_xlim(right=a["sqale"].max() * 3)

    b = d.sort_values("density", ascending=True)
    ax2.barh(b["repo"], b["density"], color="#d97706", alpha=0.9)
    ax2.set_xlabel("Debt density (remediation minutes per 1,000 lines of code)")
    ax2.set_title("(b) Debt density, normalised by codebase size",
                  fontweight="bold", loc="left")
    for i, v in enumerate(b["density"]):
        ax2.text(v + b["density"].max() * 0.015, i, f"{v:,.0f}", va="center", fontsize=8.5)
    ax2.set_xlim(right=b["density"].max() * 1.18)

    for ax in (ax1, ax2):
        ax.tick_params(axis="y", labelsize=9)
        ax.grid(axis="y", visible=False)

    fig.suptitle("Technical Debt at Most Recent Commit Across Nine Repositories",
                 fontweight="bold", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = FIGURES_DIR / "cross_section_debt_density.png"
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}\n")

    print(f"{'repo':<32}{'sqale':>12}{'ncloc':>12}{'min/kLOC':>12}")
    for _, r in d.sort_values("density", ascending=False).iterrows():
        print(f"{r.repo:<32}{r.sqale:>12,.0f}{r.ncloc:>12,.0f}{r.density:>12,.1f}")


if __name__ == "__main__":
    main()
