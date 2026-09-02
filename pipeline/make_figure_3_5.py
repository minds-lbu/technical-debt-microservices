#!/usr/bin/env python3
"""Figure 3.5: td-agent architecture.

Previously produced by make_figures_ch4.py as figure_4_1, before the restructure
moved it into Chapter 3. Content is unchanged, and still drawn from the actual
source in td-agent/src/td_agent rather than from a design sketch, so the layer
boundaries match what the code does.

The four layer names were already present as small italic labels in the margin;
they are now set in the shared tracked small-capital gutter style, which is the
idiom this diagram suits best of the whole set.

The accent falls on LLMProvider. That is the point this figure exists to make:
callers depend on the abstract interface, never on a particular model.
"""
import figstyle as fs

fig, ax = fs.canvas(11.8, 7.0)

# ------------------------------------------------------------------ presentation
fs.gutter_label(ax, 0.902, "Presentation", x=0.014, width=0.104)
fs.process(ax, 0.400, 0.912, 0.340, 0.086,
           "Next.js dashboard (web-next)\nrepository views, charts, issue lists",
           size=9.9)
fs.process(ax, 0.790, 0.912, 0.340, 0.086,
           "Command line interface (cli.py)\nanalyse, report", size=9.9)

# ----------------------------------------------------------------------- service
fs.gutter_label(ax, 0.742, "Service", x=0.014, width=0.104)
fs.process(ax, 0.595, 0.752, 0.620, 0.090,
           "FastAPI service layer (web-api/main.py)\n"
           "background analysis jobs, results and comparison endpoints",
           size=9.9)
fs.flow(ax, [(0.400, 0.869), (0.400, 0.826), (0.470, 0.826), (0.470, 0.797)])
fs.flow(ax, [(0.790, 0.869), (0.790, 0.826), (0.720, 0.826), (0.720, 0.797)])

# -------------------------------------------------------------------------- core
fs.gutter_label(ax, 0.556, "Core", x=0.014, width=0.104)
fs.process(ax, 0.595, 0.566, 0.420, 0.116,
           "TechnicalDebtAnalyzer\n(analyzer.py)\nfile selection, prompt assembly,\n"
           "validation, dedup, scoring", size=9.4)
fs.down(ax, 0.595, 0.707, 0.624)

fs.data_card(ax, 0.196, 0.566, 0.172, 0.116,
             "git_utils.py\nchurn, history,\nfile listing", size=9.6)
fs.data_card(ax, 0.902, 0.566, 0.172, 0.116,
             "sampler.py\ncommit\nselection", size=9.6)
fs.across(ax, 0.566, 0.282, 0.385)
fs.across(ax, 0.566, 0.816, 0.805)

# ---------------------------------------------------------------------- provider
fs.gutter_label(ax, 0.386, "Provider", x=0.014, width=0.104)
fs.output(ax, 0.595, 0.396, 0.400, 0.082,
          "LLMProvider (providers/base.py)\nabstract interface: analyze(prompt, schema)",
          size=9.9, bold=True)
fs.down(ax, 0.595, 0.508, 0.437)

fs.process(ax, 0.372, 0.212, 0.300, 0.082,
           "GeminiProvider\ngemini-2.5-flash-lite", size=9.9)
fs.process(ax, 0.818, 0.212, 0.300, 0.082,
           "ClaudeProvider\nclaude-sonnet-4-5", size=9.9)
fs.flow(ax, [(0.595, 0.355), (0.595, 0.300), (0.372, 0.300), (0.372, 0.253)])
fs.flow(ax, [(0.595, 0.300), (0.818, 0.300), (0.818, 0.253)])

fs.caption_note(ax, 0.560, 0.092,
                "Callers depend only on the abstract interface, so the model serving a "
                "request is a runtime choice.\nEvery stored result records the exact model "
                "string that produced it.", size=9.2)

fs.save(fig, "figure_3_5_tdagent_architecture.png")
