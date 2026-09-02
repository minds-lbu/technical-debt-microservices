#!/usr/bin/env python3
"""
Statistical analysis of technical debt time series
MSc Dissertation, Technical Debt Evolution in Microservice Systems

Implements the three techniques specified in Chapter Three, Section 3.5:

  1. Augmented Dickey-Fuller stationarity testing on each repository's SQALE
     series, differencing until stationarity is reached and recording the order
     of differencing applied.
  2. Seasonal-Trend decomposition using Loess (STL) to separate the long-term
     trend from commit-level noise and one-off spikes.
  3. Granger causality testing of microservice count against SQALE index, with
     lag order selected by Akaike Information Criterion.

Commits are irregularly spaced in calendar time, so each series is resampled to
a regular weekly interval before analysis, taking the last observation in each
week and carrying the previous value forward across weeks with no commits. Debt
is a stock rather than a flow: between commits it holds its value rather than
falling to zero, so forward filling is the behaviour that matches the quantity
being measured.

Commits whose SonarQube analysis failed carry no SQALE value and are dropped
before resampling. They are not interpolated, because a failed scan is missing
information rather than an observed value.

Usage:
    python3 statistical_analysis.py                 # full run, writes CSV + figures
    python3 statistical_analysis.py --alpha 0.01    # stricter significance level
"""

import argparse
import contextlib
import csv
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from statsmodels.tsa.stattools import adfuller, grangercausalitytests
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.api import VAR

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
OUT_CSV = RESULTS_DIR / "statistical_analysis_summary.csv"

RESAMPLE = "W"          # weekly
RESAMPLE_ROBUST = "ME"  # monthly, used as a robustness check on Granger results
STL_PERIOD = 52         # weeks in a year
MAX_DIFF = 2            # differencing beyond second order is not interpreted here
MAX_LAG = 8             # upper bound on lag search for Granger causality

# Repositories whose deployment topology is declared in Docker Compose, so a
# microservice count exists at enough commits to support a causality test.
# taotao-cloud-project is excluded despite carrying some service counts: they
# are present at only 66 of its 3,323 commits (2.0 per cent), which is far too
# sparse a series to difference and lag-select against.
GRANGER_REPOS = [
    "piggymetrics",
    "train-ticket",
    "geoserver-cloud",
    "robot-shop",
    "spring-petclinic-microservices",
]


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def load_series(path: Path, rule: str = RESAMPLE) -> pd.DataFrame:
    """Return a resampled frame with sqale_index and microservice_count."""
    df = pd.read_csv(path)
    df["dt"] = pd.to_datetime(df["commit_date"], format="mixed", utc=True)
    df = df.dropna(subset=["sqale_index"]).sort_values("dt").set_index("dt")

    weekly = pd.DataFrame({
        "sqale": df["sqale_index"].resample(rule).last().ffill(),
        "services": df["microservice_count"].resample(rule).last().ffill(),
    })
    return weekly.dropna(subset=["sqale"])


# ---------------------------------------------------------------------------
# 1. Stationarity
# ---------------------------------------------------------------------------

def adf_to_stationary(series: pd.Series, alpha: float):
    """Difference until ADF rejects a unit root. Returns (order, p0, p_final)."""
    s = series.dropna()
    p0 = adfuller(s, autolag="AIC")[1]
    p = p0
    for order in range(MAX_DIFF + 1):
        if p < alpha:
            return order, p0, p
        s = s.diff().dropna()
        if len(s) < 20:
            break
        p = adfuller(s, autolag="AIC")[1]
    return MAX_DIFF, p0, p


# ---------------------------------------------------------------------------
# 2. STL decomposition
# ---------------------------------------------------------------------------

def stl_trend(series: pd.Series):
    """Fit STL and summarise the trend component.

    The seasonal window is deliberately wide. There is no mechanism by which
    technical debt would accumulate on an annual cycle, so a narrow seasonal
    window would absorb genuine trend movement into a spurious seasonal term.
    """
    s = series.dropna()
    if len(s) < 2 * STL_PERIOD:
        return None
    res = STL(s, period=STL_PERIOD, seasonal=STL_PERIOD * 2 + 1, robust=True).fit()
    trend = res.trend

    # Trend strength after Wang, Smith and Hyndman (2006): the proportion of
    # variance in the deseasonalised series that the trend explains, bounded to
    # [0, 1]. A raw residual-to-total variance ratio was tried first and is not
    # usable here, because robust STL lets the residual exceed the variance of
    # the original series when trend and remainder move against one another,
    # which produced a nonsensical value above 1.0 for taotao-cloud-project.
    deseasonalised = trend + res.resid
    var_deseason = np.var(deseasonalised)
    trend_strength = (max(0.0, 1.0 - np.var(res.resid) / var_deseason)
                      if var_deseason > 0 else float("nan"))

    return {
        "trend": trend,
        "resid": res.resid,
        "trend_start": trend.iloc[0],
        "trend_end": trend.iloc[-1],
        "trend_change": trend.iloc[-1] - trend.iloc[0],
        "trend_direction": "rising" if trend.iloc[-1] > trend.iloc[0] * 1.02
                           else ("falling" if trend.iloc[-1] < trend.iloc[0] * 0.98 else "flat"),
        "trend_strength": float(trend_strength),
    }


# ---------------------------------------------------------------------------
# 3. Granger causality
# ---------------------------------------------------------------------------

def granger(frame: pd.DataFrame, alpha: float):
    """Test whether service count Granger-causes SQALE index.

    Both series are differenced to the higher of the two orders required for
    stationarity, since the test requires stationary inputs and the pair must be
    differenced consistently to remain aligned.
    """
    d = frame[["sqale", "services"]].dropna()
    if len(d) < 40 or d["services"].nunique() < 3:
        return {"status": "insufficient variation in service count"}

    d_sq, _, _ = adf_to_stationary(d["sqale"], alpha)
    d_sv, _, _ = adf_to_stationary(d["services"], alpha)
    order = max(d_sq, d_sv)

    work = d.copy()
    for _ in range(order):
        work = work.diff().dropna()
    work = work.loc[:, ["sqale", "services"]]
    work = work.loc[~(work.std() == 0).reindex(work.index, method="ffill").any(axis=1)] \
        if False else work
    if work["services"].std() == 0 or work["sqale"].std() == 0:
        return {"status": "series constant after differencing", "diff_order": order}

    try:
        sel = VAR(work).select_order(maxlags=min(MAX_LAG, max(1, len(work) // 10)))
        lag = int(sel.aic) or 1
    except Exception:
        lag = 1
    lag = max(1, min(lag, MAX_LAG))

    try:
        # column order is [caused, causing]: does `services` help predict `sqale`?
        # statsmodels prints a full report per lag; suppress it so the summary
        # table below stays readable.
        with contextlib.redirect_stdout(io.StringIO()):
            res = grangercausalitytests(work[["sqale", "services"]], maxlag=[lag])
        f_stat, p_val = res[lag][0]["ssr_ftest"][0], res[lag][0]["ssr_ftest"][1]
    except Exception as exc:
        return {"status": f"test failed: {exc}", "diff_order": order, "lag": lag}

    return {
        "status": "ok", "diff_order": order, "lag": lag,
        "f_stat": f_stat, "p_value": p_val,
        "significant": p_val < alpha, "n": len(work),
    }


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Debt time-series statistical analysis")
    ap.add_argument("--alpha", type=float, default=0.05, help="significance level")
    args = ap.parse_args()
    alpha = args.alpha

    paths = sorted(RESULTS_DIR.glob("*_results.csv"))
    if not paths:
        sys.exit(f"No result CSVs in {RESULTS_DIR}")

    rows = []
    trends = {}

    print(f"\n{'='*112}")
    print(f"  Statistical analysis, weekly resampling, alpha = {alpha}")
    print(f"{'='*112}")
    print(f"  {'repo':<32}{'n':>5}{'ADF p (raw)':>13}{'d':>3}{'ADF p (diff)':>14}"
          f"{'STL trend':>11}{'trend strength':>16}")
    print(f"  {'-'*108}")

    for path in paths:
        repo = path.name.replace("_results.csv", "")
        w = load_series(path)
        order, p_raw, p_fin = adf_to_stationary(w["sqale"], alpha)
        st = stl_trend(w["sqale"])
        if st:
            trends[repo] = st

        print(f"  {repo:<32}{len(w):>5}{p_raw:>13.4f}{order:>3}{p_fin:>14.4f}"
              f"{(st['trend_direction'] if st else 'n/a'):>11}"
              f"{(f"{st['trend_strength']:.3f}" if st else 'n/a'):>16}")

        rows.append({
            "repo": repo, "weeks": len(w),
            "adf_p_raw": round(p_raw, 4), "diff_order": order,
            "adf_p_differenced": round(p_fin, 4),
            "stl_trend_direction": st["trend_direction"] if st else "n/a",
            "stl_trend_change_min": round(st["trend_change"], 0) if st else "",
            "stl_trend_strength": round(st["trend_strength"], 3) if st else "",
            "granger_lag": "", "granger_f": "", "granger_p": "",
            "granger_significant": "", "granger_note": "",
        })

    print(f"  {'-'*108}")

    print(f"\n{'='*112}")
    print("  Granger causality: does microservice count help predict SQALE index?")
    print(f"{'='*112}")
    print(f"  {'repo':<32}{'d':>3}{'lag':>5}{'F':>10}{'p':>10}{'n':>6}   verdict")
    print(f"  {'-'*108}")

    by_repo = {r["repo"]: r for r in rows}
    for repo in GRANGER_REPOS:
        path = RESULTS_DIR / f"{repo}_results.csv"
        if not path.exists():
            continue
        g = granger(load_series(path), alpha)
        r = by_repo[repo]
        if g["status"] != "ok":
            r["granger_note"] = g["status"]
            print(f"  {repo:<32}{'':>3}{'':>5}{'':>10}{'':>10}{'':>6}   {g['status']}")
            continue
        verdict = ("service count Granger-causes debt" if g["significant"]
                   else "no Granger causality detected")

        # Robustness check. Weekly resampling forward-fills debt across weeks
        # with no commits, which manufactures serial persistence that a Granger
        # test can read as predictive structure. Repeating the test on monthly
        # data reduces the number of carried-forward observations sharply. A
        # result that survives both is not an artefact of the sampling interval.
        gm = granger(load_series(path, RESAMPLE_ROBUST), alpha)
        if gm.get("status") == "ok":
            agree = "holds" if gm["significant"] == g["significant"] else "DIVERGES"
            robust = f"monthly p={gm['p_value']:.4f} ({agree})"
        else:
            robust = f"monthly: {gm.get('status', 'n/a')}"

        r.update({"granger_lag": g["lag"], "granger_f": round(g["f_stat"], 3),
                  "granger_p": round(g["p_value"], 4),
                  "granger_significant": "yes" if g["significant"] else "no",
                  "granger_note": robust})
        print(f"  {repo:<32}{g['diff_order']:>3}{g['lag']:>5}{g['f_stat']:>10.3f}"
              f"{g['p_value']:>10.4f}{g['n']:>6}   {verdict}")
        print(f"  {'':<32}{'':>3}{'':>5}{'':>10}{'':>10}{'':>6}   {robust}")

    for repo in by_repo:
        if repo not in GRANGER_REPOS and not by_repo[repo]["granger_note"]:
            by_repo[repo]["granger_note"] = "no Docker Compose service count"
    print(f"  {'-'*108}\n")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"  Summary written: {OUT_CSV}")

    # STL trend overlay figure
    if trends:
        fig, ax = plt.subplots(figsize=(13, 6))
        for repo, st in sorted(trends.items()):
            t = st["trend"]
            norm = (t - t.min()) / (t.max() - t.min()) * 100 if t.max() > t.min() else t * 0
            ax.plot(np.linspace(0, 100, len(norm)), norm, linewidth=1.6,
                    label=repo.replace("-", " ").title(), alpha=0.85)
        ax.set_xlabel("Position through observation window (%)")
        ax.set_ylabel("Normalised STL trend component (0 = min, 100 = max)")
        ax.set_title("STL Trend Components, Technical Debt Across Nine Repositories",
                     fontweight="bold")
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        out = FIGURES_DIR / "stl_trends_all_repos.png"
        fig.savefig(out, dpi=150)
        print(f"  Figure written: {out}\n")


if __name__ == "__main__":
    main()
