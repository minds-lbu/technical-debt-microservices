#!/usr/bin/env python3
"""Figure 2.1: how the three identified gaps converge.

Content is unchanged from the previous version. Only the visual treatment moved,
onto the shared language in figstyle.py: square corners, Times New Roman to match
the body text, tracked small-capital band labels, and claret reserved for the
contribution tier so that everything upstream of it stays greyscale.

The contribution is still split the same way Figure 3.1 splits it: a solid box
for the nine-repository quantitative study and a dashed box for the AI-only
extension to erda.
"""
import figstyle as fs

fig, ax = fs.canvas(10.6, 6.5)

# ------------------------------------------------- the three gaps in the field
fs.band_label(ax, 0.070, 0.955, "Gaps identified in the literature", width=0.315)

GAPS = [(0.240, "Gap 1", "No multi-project\nquantitative evidence"),
        (0.500, "Gap 2", "No activity-type\nclassification"),
        (0.760, "Gap 3", "No AI vs rule-based\ncomparison")]
for x, head, body in GAPS:
    fs.process(ax, x, 0.845, 0.232, 0.112, "", fill=fs.WASH)
    ax.text(x, 0.879, head, ha="center", va="center", fontsize=11.4,
            fontweight="bold", color=fs.INK, zorder=4)
    ax.text(x, 0.822, body, ha="center", va="center", fontsize=9.9,
            color=fs.GRAPHITE, zorder=4, linespacing=1.45)

fs.collector(ax, [g[0] for g in GAPS], 0.789, 0.726, 0.500, 0.664)

# ------------------------------------------------------------ the shared cause
fs.band_label(ax, 0.070, 0.618, "Shared root cause", width=0.190)
fs.data_card(ax, 0.500, 0.536, 0.640, 0.098,
             "An immature empirical-methodology landscape at the\n"
             "intersection of technical debt and microservice research",
             size=10.1)
fs.down(ax, 0.500, 0.487, 0.427)

# -------------------------------------------------------------- the payoff tier
fs.band_label(ax, 0.070, 0.381, "This dissertation", width=0.160)
fs.output(ax, 0.500, 0.185, 0.860, 0.310, "", wash=True)
ax.text(0.500, 0.302, "This dissertation's contribution", ha="center",
        va="center", fontsize=12.0, fontweight="bold", color=fs.ACCENT, zorder=4)

fs.process(ax, 0.318, 0.198, 0.310, 0.078,
           "Quantitative study\n9 microservice systems", size=10.0, bold=True)
fs.excluded(ax, 0.682, 0.198, 0.310, 0.078,
            "Exploratory AI extension\n+1 repository (erda)", size=10.0, bold=True)

ax.text(0.500, 0.098, "One methodology applied consistently, closing all three gaps\n"
                      "together rather than one at a time",
        ha="center", va="center", fontsize=10.0, color=fs.GRAPHITE,
        zorder=4, linespacing=1.5)

fs.save(fig, "figure_2_1_research_gaps.png")
