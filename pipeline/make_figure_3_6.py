#!/usr/bin/env python3
"""Figure 3.6: the per-commit analysis flow inside td-agent.

Previously produced by make_figures_ch4.py as figure_4_2, before the restructure
moved it into Chapter 3. Content unchanged, including the three code references
and the budget constants, which are taken from the actual source.

Restyled onto the shared language. The three code references were amber boxes,
which made them read as steps in the flow; they are now marginalia with
tick-rules, set on the right where they annotate. The claret accent falls on the
provider call and on the scoring step it feeds, which are the two elements the
surrounding text makes claims about.
"""
import figstyle as fs

fig, ax = fs.canvas(11.8, 7.0)

CX, BW, H = 0.462, 0.600, 0.060
RIGHT = CX + BW / 2

fs.gutter_label(ax, 0.940, "File selection", x=0.010, width=0.092)

# Step pitch matches Figure 3.2, so the two flow diagrams read as siblings.
STEPS = [
    (0.940, "Check out commit and list source files"),
    (0.826, "Exclude generated code, lock files and build artefacts"),
    (0.712, "Prioritise: high-churn, debt-prone paths, recently modified, entry points"),
    (0.598, "Apply budget: first 80 files, up to 400,000 characters"),
    (0.484, "Assemble single structured prompt with the ten-category JSON schema"),
]
for y, t in STEPS:
    fs.process(ax, CX, y, BW, H, t, size=10.0)
for (y1, _), (y2, _) in zip(STEPS, STEPS[1:]):
    fs.down(ax, CX, y1 - H / 2, y2 + H / 2)

# --- the code that implements each rule -------------------------------------
REFS = [(0.826, "_is_excluded_file()"),
        (0.712, "_prioritize_paths()"),
        (0.598, "MAX_FILES / MAX_CHARS")]
for y, t in REFS:
    fs.tick_link(ax, RIGHT, 0.792, y)
    fs.note(ax, 0.800, y, t, size=9.2)

# --- the model boundary -----------------------------------------------------
fs.gutter_label(ax, 0.360, "Model call", x=0.010, width=0.092)
fs.down(ax, CX, 0.454, 0.400)
fs.output(ax, CX, 0.360, 0.320, 0.070, "LLMProvider.analyze()", size=10.2, bold=True)

fs.across(ax, 0.360, 0.622, 0.676)
fs.process(ax, 0.836, 0.360, 0.300, 0.070,
           "Validate against schema;\nretry on 503 with backoff", size=9.4,
           fill=fs.WASH)

# --- scoring ----------------------------------------------------------------
fs.gutter_label(ax, 0.212, "Scoring", x=0.010, width=0.092)
fs.down(ax, CX, 0.325, 0.271)
fs.output(ax, CX, 0.212, 0.700, 0.096,
          "Dedup exact location and description pairs; retain repeats across services "
          "and flag as\ncross-service; sum remediation_minutes into the AI debt score; "
          "persist with model string",
          size=9.4, bold=False)

fs.save(fig, "figure_3_6_tdagent_analysis_flow.png")
