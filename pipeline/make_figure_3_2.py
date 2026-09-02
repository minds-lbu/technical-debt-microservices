#!/usr/bin/env python3
"""Figure 3.2: the per-commit pipeline loop.

Content unchanged: the same eight steps, the same three non-SUCCESS build
statuses, and the same loop back to the next commit.

Restyled onto the shared language. Two changes of treatment. The steps are now a
single uniform column, because a loop reads as one column rather than as a ragged
stack of content-width boxes. And the three failure annotations, previously boxed
in amber so that they looked like further steps, are set as unboxed marginalia
with tick-rules, which is what they actually are.
"""
import figstyle as fs

fig, ax = fs.canvas(11.6, 7.4)

CX, BW, H = 0.632, 0.560, 0.060
LEFT = CX - BW / 2

STEPS = [
    (0.940, "Clone or verify repository"),
    (0.826, "Enumerate commits (chronological, post-2015)"),
    (0.712, "Checkout next unprocessed commit (git checkout --force)"),
    (0.598, "Detect build tool (Maven / Gradle / npm / Go / Python / none)"),
    (0.484, "Attempt build with JDK selection and automatic fallback"),
    (0.370, "Run sonar-scanner analysis and poll Compute Engine task"),
    (0.256, "Read metrics via SonarQube Web API"),
    (0.142, "Append row to results CSV (with build status and JDK used)"),
]

fs.gutter_label(ax, 0.940, "Per commit", x=0.014, width=0.092)

for y, t in STEPS:
    fs.process(ax, CX, y, BW, H, t, size=10.2)
for (y1, _), (y2, _) in zip(STEPS, STEPS[1:]):
    fs.down(ax, CX, y1 - H / 2, y2 + H / 2)

# --- the three ways a commit leaves the loop without a SUCCESS row ----------
NOTES = [
    (0.484, "Build failure:\nsource-only scan proceeds\n(BUILD_FAILED_SCAN_OK)"),
    (0.370, "Scanner did not complete:\nrow recorded as SCAN_FAILED\nand excluded"),
    (0.256, "CE task timeout:\nrow recorded as ANALYSIS_FAILED\nand excluded"),
]
for y, t in NOTES:
    fs.note(ax, 0.016, y, t, size=8.9)
    fs.tick_link(ax, 0.286, LEFT, y)

# --- loop back to the next commit ------------------------------------------
fs.flow(ax, [(CX + BW / 2, 0.142), (0.960, 0.142), (0.960, 0.712),
             (CX + BW / 2, 0.712)])
ax.text(0.977, 0.427, "next commit", fontsize=9.6, style="italic",
        color=fs.SLATE, rotation=90, ha="center", va="center", zorder=4)

fs.save(fig, "figure_3_2_pipeline_loop.png")
