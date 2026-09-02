#!/usr/bin/env python3
"""
Gap-aware single-commit debt spike analysis
MSc Dissertation — Technical Debt Evolution

A single-commit debt increase is only meaningful between two commits that are
adjacent in the repository's history.  Commits whose SonarQube analysis failed
(SCAN_FAILED / ANALYSIS_FAILED) carry no SQALE value, but they still happened:
if they are dropped before differencing, the debt accumulated across the whole
gap is misattributed to the one measured commit that follows it.

This produced a spurious "+237,133 minutes on 2022-12-14" for
taotao-cloud-project, which was in fact 237,133 minutes of change spread over a
13-commit SCAN_FAILED run between 2022-12-10 and 2022-12-14.

Two further details matter:
  * rows are written in git-log order, which is NOT commit-date order, so
    adjacency must be established after sorting by date; and
  * a repo may be perfectly clean (no excluded rows) yet still be misreported
    if either of the above is handled loosely.

Usage:
    python3 compute_spikes.py              # top spike per repo + artefact audit
    python3 compute_spikes.py --top 10     # top N spikes per repo (for RQ3)
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "results"

EXCLUDED_STATUSES = {"SCAN_FAILED", "ANALYSIS_FAILED"}


def load_commits(path: Path) -> list[dict]:
    """Return every dated commit in chronological order, valid or not.

    ``sqale`` is None for commits SonarQube could not measure.  Those rows are
    retained deliberately — they are what makes a gap visible.
    """
    commits = []
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                dt = datetime.fromisoformat(row.get("commit_date", ""))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            sqale = None
            if row.get("build_status") not in EXCLUDED_STATUSES:
                try:
                    sqale = float(row.get("sqale_index", ""))
                except ValueError:
                    sqale = None

            commits.append({
                "date": dt,
                "sqale": sqale,
                "status": row.get("build_status", ""),
                "message": (row.get("commit_message") or "").strip(),
                "hash": (row.get("commit_hash") or "")[:8],
            })

    commits.sort(key=lambda c: c["date"])
    return commits


def spikes(commits: list[dict]) -> tuple[list[dict], list[dict]]:
    """Compute deltas between chronologically adjacent commits.

    Returns (attributable, bridged): deltas where both endpoints are measured
    and adjacent, and deltas that span at least one excluded commit.  The
    second list exists so gap artefacts can be reported rather than silently
    dropped — a large bridged delta still marks a real period of change, it
    just cannot be pinned on a single commit.
    """
    attributable, bridged = [], []
    prev = None          # last measured commit
    gap = 0              # excluded commits seen since it

    for c in commits:
        if c["sqale"] is None:
            gap += 1
            continue
        if prev is not None:
            entry = {
                "date": c["date"], "hash": c["hash"], "message": c["message"],
                "delta": c["sqale"] - prev["sqale"],
                "from_date": prev["date"], "skipped": gap,
            }
            (bridged if gap else attributable).append(entry)
        prev, gap = c, 0

    return attributable, bridged


def main() -> None:
    ap = argparse.ArgumentParser(description="Gap-aware debt spike analysis")
    ap.add_argument("--top", type=int, default=1,
                    help="number of top spikes to report per repo (default 1)")
    args = ap.parse_args()

    paths = sorted(RESULTS_DIR.glob("*_results.csv"))
    if not paths:
        sys.exit(f"No result CSVs found in {RESULTS_DIR}")

    artefacts = []
    print(f"\n{'='*104}")
    print(f"  Gap-aware largest single-commit debt increases (top {args.top} per repo)")
    print(f"{'='*104}")
    print(f"  {'repo':<32}{'date':<12}{'delta':>11}  commit")
    print(f"  {'-'*100}")

    for path in paths:
        repo = path.name.replace("_results.csv", "")
        commits = load_commits(path)
        attributable, bridged = spikes(commits)
        if not attributable:
            print(f"  {repo:<32}{'-- no attributable deltas --'}")
            continue

        for entry in sorted(attributable, key=lambda e: e["delta"], reverse=True)[:args.top]:
            msg = entry["message"].replace("\n", " ")[:44]
            print(f"  {repo:<32}{entry['date']:%Y-%m-%d}  "
                  f"{entry['delta']:>+10,.0f}  [{entry['hash']}] {msg}")

        # Would a naive (gap-bridging) calculation have reported something
        # larger?  If so, this repo's published spike figure is an artefact.
        top_ok = max(e["delta"] for e in attributable)
        top_bridged = max((e["delta"] for e in bridged), default=float("-inf"))
        if top_bridged > top_ok:
            worst = max(bridged, key=lambda e: e["delta"])
            artefacts.append((repo, top_bridged, worst, top_ok))

    print(f"  {'-'*100}")
    print(f"\n{'='*104}")
    print("  ARTEFACT AUDIT — repos where a naive .diff() would overstate the largest spike")
    print(f"{'='*104}")
    if not artefacts:
        print("  None.  Every repo's largest increase is between two adjacent measured commits.")
    else:
        for repo, bad, worst, good in artefacts:
            print(f"\n  {repo}")
            print(f"    naive (WRONG) : {bad:+,.0f} on {worst['date']:%Y-%m-%d}")
            print(f"                    spans {worst['skipped']} excluded commit(s) "
                  f"back to {worst['from_date']:%Y-%m-%d} — not a single commit")
            print(f"    correct       : {good:+,.0f}")
    print()


if __name__ == "__main__":
    main()
