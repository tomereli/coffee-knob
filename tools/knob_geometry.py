"""Shared model of what this display can actually draw.

Both the linter and the mock renderer import from here, so a rule can never
be enforced in one and ignored in the other.

The screen is a 360x360 CIRCLE. Anything outside radius 180 is not merely
clipped, it is physically not there -- the glass is round. LVGL will happily
lay out a label whose ends fall off the edge and report no error, which is
how EXIT shipped as EXI.
"""

import math

SIZE = 360
CX = CY = SIZE / 2
RADIUS = SIZE / 2

# Keep real content off the last few pixels: the bezel curves, and a glyph
# touching the exact edge reads as broken even when it is technically inside.
SAFE_RADIUS = 172

# Average advance width per character, in px, measured per compiled font.
# These are ESTIMATES until calibrate.py replaces them with numbers measured
# from a photograph of the real panel -- see the skill. They are deliberately
# a little generous: over-estimating width makes the linter cautious, and a
# false warning costs a comment while a false pass costs a reflash.
FONT_ADV = {
    'montserrat_16': 9.4,
    'montserrat_20': 11.8,
    'montserrat_48': 28.0,
    'mdi_40': 40.0,
}
FONT_HEIGHT = {
    'montserrat_16': 16,
    'montserrat_20': 20,
    'montserrat_48': 48,
    'mdi_40': 40,
}
DEFAULT_FONT = 'montserrat_16'

# What a lambda-driven label might hold at its worst. A label whose text is
# computed has no fixed length, so the linter assumes the longest thing it
# could plausibly carry unless the widget declares a width.
ASSUMED_DYNAMIC_CHARS = 22


def text_width(text, font):
    return len(text) * FONT_ADV.get(font, FONT_ADV[DEFAULT_FONT])


def text_height(font):
    return FONT_HEIGHT.get(font, FONT_HEIGHT[DEFAULT_FONT])


def half_chord(dy):
    """Half the width available at vertical offset dy from the centre."""
    d = SAFE_RADIUS ** 2 - dy ** 2
    return math.sqrt(d) if d > 0 else 0.0


def fits(cx_off, cy_off, w, h):
    """Does a box centred at (cx_off, cy_off) from screen centre fit the glass?

    Checks the two worst corners: the outer top and outer bottom. Returns
    (ok, overflow_px).
    """
    worst = 0.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            px = cx_off + sx * w / 2
            py = cy_off + sy * h / 2
            r = math.hypot(px, py)
            worst = max(worst, r)
    return worst <= SAFE_RADIUS, worst - SAFE_RADIUS
