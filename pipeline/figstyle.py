#!/usr/bin/env python3
"""Shared visual language for the hand-drawn diagrams in this dissertation.

Every schematic figure imports its palette, type and drawing primitives from
here, so the diagrams read as one designed set rather than as separately
generated images. Data charts (debt footprints, STL trends, the density
comparison) are not covered: those are plots, not schematics, and keep their own
conventions.

Design brief this implements
----------------------------
1. Type is Times New Roman throughout, matching the body text of the document.
   Role labels are set as tracked small capitals, the way a section marker is set
   in a printed book.

2. Colour is near-monochrome. Structure, process and evidence are all rendered in
   warm greys; a single claret accent is reserved for the payoff of a diagram.
   In a flow that ends in a result, that is the finding, output or contribution.
   In a structural diagram with no result, it is the one element the figure
   exists to make a point about, such as the provider interface in Figure 3.5.
   Nothing upstream of the payoff carries colour.

3. Semantic role is carried by SHAPE and RULE WEIGHT, not by fill colour, so the
   diagrams survive greyscale printing intact. Colour is a redundant channel:
   remove it and the roles are still distinguishable.

       DATA / SOURCE   sharp rectangle with a doubled left edge, like a ledger card
       PROCESS         plain sharp rectangle, hairline border
       DECISION        rectangle with the top-right and bottom-left corners clipped
       OUTPUT / RESULT claret rule down the left edge, heavier border  <- only colour
       EXCLUDED        dashed hairline border, grey text
       ANNOTATION      no box at all: a tick-rule and italic text, set as marginalia

4. Corners are square. The uniformly rounded rectangle is the single strongest
   signal of a default flowchart template, so it is not used anywhere.

5. Connectors are hairline and orthogonal, with small solid arrowheads. Elbows
   are drawn explicitly rather than left to an auto-router.

6. Everything is placed on a declared modular grid with real optical spacing,
   rather than spread to fill the canvas.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle

FIGDIR = Path(__file__).resolve().parent.parent / "results" / "figures"

# --------------------------------------------------------------------- palette
INK = "#1A1A1A"      # primary text, primary rules
GRAPHITE = "#3D3D3D"  # secondary text
SLATE = "#6E6E6E"    # annotations, tertiary text
HAIRLINE = "#AFACA6"  # light rules, dashed edges
WASH = "#F4F3F0"     # pale warm grey fill, the paper tone
WASH_DEEP = "#E6E4DE"  # a step deeper, for emphasis without colour
PAPER = "white"

ACCENT = "#6E2A2A"       # claret. Outputs, findings, contributions only.
ACCENT_WASH = "#F6EDEB"  # very pale claret

SERIF = ["Times New Roman", "STIX Two Text", "Charter", "DejaVu Serif"]

# Rule weights, in points. Kept few and deliberate.
W_HAIR = 0.9
W_RULE = 1.15
W_HEAVY = 2.0
W_BAR = 4.2   # the accent bar and the data-card doubled edge


def setup():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": SERIF,
        "text.color": INK,
        "axes.linewidth": W_HAIR,
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
    })


def canvas(w, h):
    """A figure whose axes are a unit square, so all coordinates are 0..1."""
    setup()
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_position([0, 0, 1, 1])
    return fig, ax


# ------------------------------------------------------------------ type marks
def band_label(ax, x, y, text, *, align="left", width=None, colour=SLATE):
    """A tracked small-capitals section marker with a hairline beneath it.

    This is the strongest identity element in the set: it frames each tier of a
    diagram the way a running head frames a page.
    """
    # matplotlib has no letter-spacing, so tracking is done with thin spaces
    spaced = "\u2009".join(text.upper())
    ax.text(x, y, spaced, ha=align, va="baseline", fontsize=8.2,
            color=colour, zorder=5)
    if width:
        x0 = x if align == "left" else x - width / 2
        ax.plot([x0, x0 + width], [y - 0.021, y - 0.021],
                color=HAIRLINE, lw=W_HAIR, zorder=1, solid_capstyle="butt")


def caption_note(ax, x, y, text, *, size=8.6, width_hint=None):
    """Footnote-style marginalia beneath a diagram."""
    ax.text(x, y, text, ha="center", va="center", fontsize=size,
            style="italic", color=SLATE, linespacing=1.62, zorder=4)


def note(ax, x, y, text, *, size=8.8, align="left", height=None):
    """An annotation with a tick-rule instead of a box.

    Deliberately unboxed: caveats and side-notes read as editorial marginalia
    rather than as another node in the flow.
    """
    lines = text.count("\n") + 1
    h = height if height is not None else 0.030 * lines
    ax.plot([x, x], [y - h / 2, y + h / 2], color=ACCENT if False else SLATE,
            lw=W_RULE, zorder=3, solid_capstyle="butt")
    ax.text(x + 0.011, y, text, ha=align, va="center", fontsize=size,
            color=GRAPHITE, linespacing=1.55, zorder=4)


# ----------------------------------------------------------------- box shapes
def _place(ax, x, y, w, h, *, fill, edge, lw, dashed=False, z=2):
    ax.add_patch(Rectangle(
        (x - w / 2, y - h / 2), w, h,
        facecolor=fill, edgecolor=edge, linewidth=lw,
        linestyle=(0, (4, 2.6)) if dashed else "-",
        joinstyle="miter", zorder=z))


def _label(ax, x, y, text, *, size, colour, bold=False, italic=False,
           align="center", pad=0.0):
    ax.text(x + pad, y, text, ha=align, va="center", fontsize=size,
            color=colour, linespacing=1.5, zorder=4,
            fontweight="bold" if bold else "normal",
            style="italic" if italic else "normal")


def process(ax, x, y, w, h, text, *, size=10.4, fill=PAPER, bold=False,
            align="center", colour=INK):
    """A step. Plain square-cornered rectangle, hairline border."""
    _place(ax, x, y, w, h, fill=fill, edge=GRAPHITE, lw=W_HAIR)
    tx = x - w / 2 + 0.014 if align == "left" else x
    _label(ax, tx, y, text, size=size, colour=colour, bold=bold, align=align)


def data_card(ax, x, y, w, h, text, *, size=10.4, bold=False, align="center",
              fill=WASH):
    """A source of data. Square rectangle with a doubled left edge.

    The left edge is two hairlines rather than one thick bar, so that in
    greyscale it stays distinct from the single heavy bar that marks an output.
    """
    _place(ax, x, y, w, h, fill=fill, edge=GRAPHITE, lw=W_HAIR)
    x0 = x - w / 2
    for dx in (0.0, 0.0075):
        ax.plot([x0 + dx, x0 + dx], [y - h / 2, y + h / 2], color=INK,
                lw=W_RULE, zorder=3, solid_capstyle="butt")
    tx = x0 + 0.020 if align == "left" else x + 0.008
    _label(ax, tx, y, text, size=size, colour=INK, bold=bold, align=align)


def decision(ax, x, y, w, h, text, *, size=10.2, clip=None):
    """A test. Rectangle with top-right and bottom-left corners clipped.

    Chosen over a diamond: it holds a real line of text without ballooning, and
    the asymmetry makes it unmistakable at a glance.
    """
    # The axes are a unit square on a non-square canvas, so a chamfer specified
    # in data units would come out lopsided. Scale x by the figure aspect so the
    # clipped corners read as true 45-degree cuts.
    w_in, h_in = ax.figure.get_size_inches()
    cy = clip if clip is not None else h * 0.32
    cx = cy * h_in / w_in
    x0, y0, x1, y1 = x - w / 2, y - h / 2, x + w / 2, y + h / 2
    pts = [(x0, y0 + cy), (x0, y1), (x1 - cx, y1), (x1, y1 - cy), (x1, y0),
           (x0 + cx, y0)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=WASH_DEEP, edgecolor=INK,
                         linewidth=W_RULE, joinstyle="miter", zorder=2))
    _label(ax, x, y, text, size=size, colour=INK)


def output(ax, x, y, w, h, text, *, size=10.6, bold=True, align="center",
           wash=True, head=None, head_size=11.4):
    """A result, finding or contribution. The only element that carries colour.

    Carries three redundant cues so it still reads as the terminal element in
    greyscale: a heavy claret bar down the left edge, a heavier border, and
    (optionally) a pale wash.
    """
    _place(ax, x, y, w, h, fill=ACCENT_WASH if wash else PAPER,
           edge=ACCENT, lw=W_RULE)
    x0 = x - w / 2
    ax.plot([x0, x0], [y - h / 2, y + h / 2], color=ACCENT, lw=W_BAR,
            zorder=3, solid_capstyle="butt")
    if head:
        ax.text(x, y + h / 2 - 0.042, head, ha="center", va="center",
                fontsize=head_size, color=ACCENT, fontweight="bold", zorder=4)
        _label(ax, x, y - 0.020, text, size=size, colour=GRAPHITE, bold=False)
    else:
        tx = x0 + 0.018 if align == "left" else x + 0.006
        _label(ax, tx, y, text, size=size, colour=ACCENT, bold=bold, align=align)


def excluded(ax, x, y, w, h, text, *, size=10.2, bold=False, align="center"):
    """Something held out of scope, or an optional path. Dashed hairline."""
    _place(ax, x, y, w, h, fill=PAPER, edge=SLATE, lw=W_HAIR, dashed=True)
    tx = x - w / 2 + 0.014 if align == "left" else x
    _label(ax, tx, y, text, size=size, colour=GRAPHITE, bold=bold, align=align,
           italic=False)


def terminal(ax, x, y, w, h, text, *, size=10.0):
    """A neutral end state that is not a finding: excluded rows, dead ends."""
    _place(ax, x, y, w, h, fill=WASH, edge=SLATE, lw=W_HAIR)
    _label(ax, x, y, text, size=size, colour=GRAPHITE, italic=True)


# ------------------------------------------------------------------ connectors
def _arrowhead(ax, x, y, direction, *, colour=GRAPHITE, size=0.0115):
    """A small solid triangle. Drawn by hand so the weight stays consistent."""
    s = size
    if direction == "down":
        pts = [(x, y), (x - s * 0.62, y + s * 1.5), (x + s * 0.62, y + s * 1.5)]
    elif direction == "up":
        pts = [(x, y), (x - s * 0.62, y - s * 1.5), (x + s * 0.62, y - s * 1.5)]
    elif direction == "right":
        pts = [(x, y), (x - s * 1.5, y - s * 0.62), (x - s * 1.5, y + s * 0.62)]
    else:
        pts = [(x, y), (x + s * 1.5, y - s * 0.62), (x + s * 1.5, y + s * 0.62)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=colour, edgecolor="none",
                         zorder=4))


def flow(ax, pts, *, arrow=True, colour=GRAPHITE, lw=W_HAIR, dashed=False):
    """An orthogonal connector through an explicit list of points."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=colour, lw=lw, zorder=1, solid_capstyle="butt",
            linestyle=(0, (4, 2.6)) if dashed else "-")
    if arrow:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        if abs(x2 - x1) < 1e-9:
            _arrowhead(ax, x2, y2, "down" if y2 < y1 else "up", colour=colour)
        else:
            _arrowhead(ax, x2, y2, "right" if x2 > x1 else "left", colour=colour)


def down(ax, x, y_from, y_to, **kw):
    flow(ax, [(x, y_from), (x, y_to)], **kw)


def across(ax, y, x_from, x_to, **kw):
    flow(ax, [(x_from, y), (x_to, y)], **kw)


def elbow(ax, x1, y1, x2, y2, *, first="v", **kw):
    """A right-angled connector: vertical then horizontal, or the reverse."""
    mid = (x1, y2) if first == "v" else (x2, y1)
    flow(ax, [(x1, y1), mid, (x2, y2)], **kw)


def collector(ax, xs, y_top, y_bus, x_out, y_out, **kw):
    """Many sources dropping onto a shared horizontal bus, then one arrow out."""
    for x in xs:
        flow(ax, [(x, y_top), (x, y_bus)], arrow=False, **kw)
    across(ax, y_bus, min(xs), max(xs), arrow=False, **kw)
    flow(ax, [(x_out, y_bus), (x_out, y_out)], **kw)


def tick_link(ax, x_from, x_to, y, *, colour=SLATE):
    """A hairline leader joining marginalia to the step it annotates."""
    ax.plot([x_from, x_to], [y, y], color=colour, lw=W_HAIR, zorder=1,
            solid_capstyle="butt", linestyle=(0, (2.4, 2.4)))


def gutter_label(ax, y, text, *, x=0.016, width=0.098, colour=SLATE):
    """A tier label set in a left gutter, vertically centred on its row.

    Used where a diagram has clearly banded tiers: keeping the label out in the
    margin means it never collides with the connectors running between tiers.
    """
    spaced = "\u2009".join(text.upper())
    ax.text(x, y + 0.012, spaced, ha="left", va="baseline", fontsize=8.0,
            color=colour, zorder=5)
    ax.plot([x, x + width], [y - 0.006, y - 0.006], color=HAIRLINE, lw=W_HAIR,
            zorder=1, solid_capstyle="butt")


def distributor(ax, x_in, y_in, y_bus, xs, y_out, **kw):
    """One source feeding many targets: drop to a bus, then one arrow per target."""
    flow(ax, [(x_in, y_in), (x_in, y_bus)], arrow=False, **kw)
    across(ax, y_bus, min(xs + [x_in]), max(xs + [x_in]), arrow=False, **kw)
    for x in xs:
        flow(ax, [(x, y_bus), (x, y_out)], **kw)


# ----------------------------------------------------------------------- save
def save(fig, name):
    out = FIGDIR / name
    fig.savefig(out, dpi=220, bbox_inches="tight", pad_inches=0.16,
                facecolor="white")
    plt.close(fig)
    print(f"Saved: {out}")
    return out
