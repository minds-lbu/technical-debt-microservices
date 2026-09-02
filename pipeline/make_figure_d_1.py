#!/usr/bin/env python3
"""Figure D.1: project timeline against the module deadlines.

Previously make_figure_pm_timeline.py, producing figure_7_1, before the
restructure moved the Project Management content into Appendix D. Every task,
date, milestone and legend label is unchanged.

Restyled onto the shared language. Because this is a chart rather than a box
diagram, category is carried by fill tone plus hatching rather than by hue, which
is what keeps the four categories separable in greyscale. Claret marks the
assessed milestones, consistent with the accent meaning "the thing that matters"
everywhere else in the set.
"""
from datetime import date

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

import figstyle as fs

fs.setup()

# Category treatments: (face, edge, hatch). Separable without colour.
WORK = (fs.WASH_DEEP, fs.INK, None)          # development and writing
COLLECT = ("white", fs.INK, "////")          # data collection
MILESTONE = (fs.ACCENT_WASH, fs.ACCENT, None)  # assessed milestone
ALLOC = ("white", fs.SLATE, "....")          # allocation

# label, start, end, treatment
TASKS = [
    ("Topic selection and supervisor allocation", date(2026, 3, 9),  date(2026, 3, 27), ALLOC),
    ("Literature review",                         date(2026, 4, 1),  date(2026, 6, 15), WORK),
    ("Proposal",                                  date(2026, 4, 10), date(2026, 5, 8),  MILESTONE),
    ("Ethics application and approval",           date(2026, 5, 8),  date(2026, 5, 29), MILESTONE),
    ("Pipeline development",                      date(2026, 4, 20), date(2026, 6, 10), WORK),
    ("Data collection, local machine",            date(2026, 5, 20), date(2026, 6, 20), COLLECT),
    ("Data collection, cloud VM",                 date(2026, 6, 15), date(2026, 7, 25), COLLECT),
    ("taotao re-run after remediation",           date(2026, 7, 1),  date(2026, 7, 25), COLLECT),
    ("td-agent development",                      date(2026, 6, 1),  date(2026, 7, 20), WORK),
    ("Claude comparison (5 of 9 repos)",          date(2026, 8, 1),  date(2026, 8, 8),  COLLECT),
    ("Draft chapter submission",                  date(2026, 6, 1),  date(2026, 6, 12), MILESTONE),
    ("Statistical analysis and RQ3 classification", date(2026, 8, 1), date(2026, 8, 12), WORK),
    ("Writing and revision",                      date(2026, 7, 1),  date(2026, 9, 5),  WORK),
    ("Dissertation and demo video due",           date(2026, 9, 5),  date(2026, 9, 7),  MILESTONE),
]

MILESTONES = [
    (date(2026, 5, 8),  "Proposal"),
    (date(2026, 5, 29), "Ethics"),
    (date(2026, 6, 12), "Draft chapter"),
    (date(2026, 9, 7),  "Submission"),
]

fig, ax = plt.subplots(figsize=(11.8, 6.2))

for i, (label, s, e, (face, edge, hatch)) in enumerate(reversed(TASKS)):
    ax.barh(i, (e - s).days, left=s, height=0.56, facecolor=face,
            edgecolor=edge, linewidth=fs.W_HAIR, hatch=hatch, zorder=3)

ax.set_yticks(range(len(TASKS)))
ax.set_yticklabels([t[0] for t in reversed(TASKS)], fontsize=9.6, color=fs.INK)
ax.set_ylim(-0.9, len(TASKS) - 0.1)

for m, lbl in MILESTONES:
    ax.axvline(m, color=fs.ACCENT, linestyle=(0, (4, 2.6)), linewidth=fs.W_HAIR,
               zorder=2)
    ax.text(m, len(TASKS) - 0.30, lbl, rotation=90, fontsize=8.4,
            color=fs.ACCENT, ha="right", va="top", zorder=5)

ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.set_xlim(date(2026, 3, 1), date(2026, 10, 4))
ax.tick_params(axis="x", labelsize=9.4, colors=fs.GRAPHITE, length=3)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color=fs.HAIRLINE, linewidth=fs.W_HAIR, alpha=0.55, zorder=0)
ax.set_axisbelow(True)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(fs.GRAPHITE)
ax.spines["bottom"].set_linewidth(fs.W_HAIR)

# The band label, set in the same tracked small capitals as the box diagrams.
ax.set_title(" ".join("PROJECT TIMELINE AGAINST MODULE DEADLINES"),
             fontsize=9.2, color=fs.SLATE, loc="left", pad=16)

handles = [plt.Rectangle((0, 0), 1, 1, facecolor=f, edgecolor=e,
                         linewidth=fs.W_HAIR, hatch=h)
           for f, e, h in (WORK, COLLECT, MILESTONE, ALLOC)]
leg = ax.legend(handles,
                ["Development and writing", "Data collection",
                 "Assessed milestone", "Allocation"],
                loc="upper left", bbox_to_anchor=(0.0, -0.09), ncol=4,
                fontsize=9.0, frameon=False, handlelength=1.9,
                columnspacing=2.2, borderpad=0.0)

fig.tight_layout()
fs.save(fig, "figure_d_1_project_timeline.png")
