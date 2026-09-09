"""Shared model of what this display can actually draw.

Both the linter and the mock renderer import from here, so a rule can never
be enforced in one and ignored in the other.

The screen is a 360x360 CIRCLE. Anything outside radius 180 is not merely
clipped, it is physically not there -- the glass is round. LVGL will happily
lay out a label whose ends fall off the edge and report no error, which is
how EXIT shipped as EXI.
"""

import math
import re

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
# Advance as a fraction of the nominal size. Montserrat Medium measured
# 9.4/16, 11.8/20 and 28/48 -- 0.587 within a percent across the range -- so
# one ratio covers every size instead of a row per size. Icon fonts are
# square by construction.
MONTSERRAT_ADV = 0.59
MDI_ADV = 1.0

# Populated from the config being checked, by register_fonts(). Empty here on
# purpose: a table written into this file only ever covers the device it was
# written for.
FONT_ADV = {}
FONT_HEIGHT = {}
DEFAULT_FONT = 'montserrat_16'

# LVGL ships these and no font: entry declares them, so they are resolved
# from the name rather than looked up.
_BUILTIN = re.compile(r'^montserrat_(\d+)$')


class UnknownFont(KeyError):
    """A font neither declared in the config nor an LVGL built-in."""


def register_fonts(cfg):
    """Take every font size from the config's own font: block.

    This replaced a table of the four fonts the coffee knob happens to use,
    with `SIZES.get(name, 16)` behind it. Pointed at the bedside knob -- whose
    fonts are named value_60, label_28, label_18 and mdi_44 -- every lookup
    missed and silently became 16px, so a 60px clock was checked as a 16px
    one and every clean result it gave about that device meant nothing. The
    lookups below now raise instead, because a checker that cannot measure
    something must say so rather than measure a smaller imaginary one.
    """
    FONT_ADV.clear()
    FONT_HEIGHT.clear()
    for entry in cfg.get('font') or []:
        fid, size = entry.get('id'), entry.get('size')
        if not fid or not size:
            continue
        ratio = MDI_ADV if 'mdi' in str(fid).lower() else MONTSERRAT_ADV
        FONT_HEIGHT[fid] = int(size)
        FONT_ADV[fid] = int(size) * ratio
    return dict(FONT_HEIGHT)


def _metrics(name):
    name = name or DEFAULT_FONT
    if name in FONT_HEIGHT:
        return FONT_ADV[name], FONT_HEIGHT[name]
    found = _BUILTIN.match(name)
    if found:
        size = int(found.group(1))
        FONT_HEIGHT[name] = size
        FONT_ADV[name] = size * MONTSERRAT_ADV
        return FONT_ADV[name], FONT_HEIGHT[name]
    raise UnknownFont(
        '%s: not declared in the config and not an LVGL built-in. Add it to '
        'font: with a size, or fix the reference -- this used to become 16px '
        'in silence.' % name)

# What a lambda-driven label might hold at its worst. A label whose text is
# computed has no fixed length, so the linter assumes the longest thing it
# could plausibly carry unless the widget declares a width.
ASSUMED_DYNAMIC_CHARS = 22


def text_width(text, font):
    return len(text) * _metrics(font)[0]


def text_height(font):
    return _metrics(font)[1]


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
