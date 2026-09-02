#!/usr/bin/env python3
"""Figure 3.1: three-strand research design.

Content unchanged apart from one correction the restructure made necessary: the
closing line read "Findings synthesised in Chapters Four and Five", and those two
chapters are now a single Chapter 4.

The sample split is preserved: nine repositories carry the quantitative strands,
and erda enters only through the exploratory AI strand, drawn dashed.

Laid out on a left-gutter grid, so the tier labels sit in the margin and never
cross the connectors running between tiers.
"""
import figstyle as fs

fig, ax = fs.canvas(11.8, 7.2)

L, R = 0.140, 0.988
SX = [0.278, 0.564, 0.850]          # the three strand columns
COL_W = 0.276

# ------------------------------------------------------------ sample definition
fs.gutter_label(ax, 0.888, "Sample")
fs.data_card(ax, 0.352, 0.898, 0.400, 0.086,
             "Quantitative dataset\n9 open-source microservice repositories",
             size=10.2, bold=True)
fs.excluded(ax, 0.800, 0.898, 0.352, 0.086,
            "Exploratory AI strand only\n+1 repository (erda)",
            size=10.2, bold=True)

# ------------------------------------------------------------- measured dataset
fs.gutter_label(ax, 0.726, "Measurement")
fs.data_card(ax, 0.564, 0.736, R - L, 0.086,
             "Commit-level dataset\n"
             "(SQALE index, NCLOC, complexity, microservice count, per commit)",
             size=9.9)
fs.down(ax, 0.352, 0.855, 0.779)

# --------------------------------------------------------------- three strands
fs.gutter_label(ax, 0.536, "Strands")
STRAND = [
    "Strand 1\nLongitudinal TD evolution\n(SonarQube pipeline)",
    "Strand 2\nManual commit inspection\nand activity classification",
    "Strand 3\nAI agent comparison\n(td-agent, exploratory)",
]
for x, t in zip(SX, STRAND):
    fs.process(ax, x, 0.546, COL_W, 0.126, t, size=9.9)

fs.distributor(ax, 0.564, 0.693, 0.648, SX, 0.609)

# erda reaches strand 3 only, never the quantitative dataset
fs.flow(ax, [(0.800, 0.855), (0.800, 0.816), (0.945, 0.816), (0.945, 0.609)],
        dashed=True, colour=fs.SLATE)

# --------------------------------------------------------------------- outputs
fs.gutter_label(ax, 0.336, "Outputs")
OUTPUTS = [
    "STL decomposition\nGranger causality\n→ RQ1, RQ2",
    "Classification of TD\nspike commits\n→ RQ3",
    "SonarQube vs LLM\nfindings comparison\n→ Exploratory strand",
]
for x, t in zip(SX, OUTPUTS):
    fs.down(ax, x, 0.483, 0.409)
    fs.output(ax, x, 0.346, COL_W, 0.126, t, size=9.9, bold=False)

# ------------------------------------------------------------------- synthesis
fs.collector(ax, SX, 0.283, 0.212, 0.564, 0.158, colour=fs.SLATE)
ax.text(0.564, 0.104, "Findings synthesised in Chapter Four", ha="center",
        va="center", fontsize=10.6, style="italic", color=fs.GRAPHITE, zorder=4)

fs.save(fig, "figure_3_1_research_design.png")
