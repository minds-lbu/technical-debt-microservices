#!/usr/bin/env python3
"""Figure 3.3: dynamic JDK selection and fallback logic.

Content unchanged apart from one correction the restructure made necessary: the
footnote cited "Section 3.4.2" for the unreliable jdk_used labels, and that
section number no longer exists. The content it refers to is now Section 3.5.1.
Everything else in the footnote, including the macOS variant, the reference to
pipeline_mac_archived.py and the Java 25/26 escalation, is preserved verbatim.

The logic still matches pipeline.py rather than the archived macOS variant:
two signal groups, not three, and no escalation path above Java 17 because the
collection VM had only Java 11 and 17 installed.
"""
import figstyle as fs

fig, ax = fs.canvas(12.4, 7.6)

fs.gutter_label(ax, 0.938, "Build attempt", x=0.014, width=0.104)

# --- primary attempt --------------------------------------------------------
fs.process(ax, 0.500, 0.945, 0.440, 0.058,
           "Maven build attempt with primary JDK (Java 17)", size=10.4)
fs.down(ax, 0.500, 0.916, 0.869)

# --- the single test --------------------------------------------------------
fs.decision(ax, 0.500, 0.822, 0.215, 0.078, "Build succeeded?", size=10.4)

# success, to the left
ax.text(0.352, 0.845, "yes", fontsize=9.6, style="italic", color=fs.SLATE, zorder=4)
fs.flow(ax, [(0.392, 0.822), (0.196, 0.822), (0.196, 0.749)])
fs.output(ax, 0.196, 0.708, 0.268, 0.078,
          "Record SUCCESS\n(jdk_used = 17)", size=10.2, bold=True)

# failure, straight down
ax.text(0.520, 0.768, "no", fontsize=9.6, style="italic", color=fs.SLATE, zorder=4)
fs.down(ax, 0.500, 0.783, 0.747)
fs.process(ax, 0.606, 0.708, 0.420, 0.078,
           "Inspect combined stdout and stderr\nfor version-mismatch signals",
           size=10.2)

# --- two signal groups, matching the two tuples in the code -----------------
fs.gutter_label(ax, 0.528, "Signal groups", x=0.014, width=0.104)
fs.flow(ax, [(0.606, 0.669), (0.606, 0.630), (0.348, 0.630), (0.348, 0.592)])
fs.flow(ax, [(0.606, 0.630), (0.812, 0.630), (0.812, 0.592)], arrow=True)

fs.data_card(ax, 0.348, 0.518, 0.352, 0.132,
             'Signals: "class file version",\n"Invalid CEN header",\n'
             '\'does not "opens com.sun.tools\'\n'
             "→ JDK too new for this commit",
             size=10.0)
fs.data_card(ax, 0.812, 0.518, 0.330, 0.132,
             'Signals: "not in the allowed range",\n"RequireJavaVersion failed"\n'
             "→ Enforcer requires a\nnewer JDK than Java 17",
             size=10.0)

fs.down(ax, 0.348, 0.452, 0.382)
fs.down(ax, 0.812, 0.452, 0.382)

# --- consequences -----------------------------------------------------------
fs.process(ax, 0.348, 0.330, 0.310, 0.080,
           "Retry the build with Java 11\n(single fallback attempt)", size=10.2)
fs.terminal(ax, 0.812, 0.330, 0.336, 0.080,
            "No newer JDK installed on the\ncollection VM: build fails", size=10.0)

fs.flow(ax, [(0.348, 0.290), (0.348, 0.236), (0.470, 0.236), (0.470, 0.200)])
fs.flow(ax, [(0.812, 0.290), (0.812, 0.236), (0.620, 0.236), (0.620, 0.200)])

fs.terminal(ax, 0.545, 0.162, 0.800, 0.070,
            "No signal matched, or the fallback also failed: proceed to source-only "
            "scan (BUILD_FAILED_SCAN_OK)", size=10.0)

# --- footnote ---------------------------------------------------------------
fs.caption_note(ax, 0.500, 0.045,
                "Only Java 11 and Java 17 were installed on the collection VM. An earlier "
                "macOS configuration additionally escalated to\nJava 25 and Java 26 on the "
                "enforcer branch; that variant is retained in pipeline_mac_archived.py and "
                "is the origin of the\nunreliable jdk_used labels noted in Section 3.5.1.",
                size=8.8)

fs.save(fig, "figure_3_3_jdk_fallback.png")
