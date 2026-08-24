"""Fail the build when the layout cannot physically fit the round screen.

    python tools/knob_lint.py coffee-knob.yaml

The screen is a 360px CIRCLE and LVGL does not complain about a label whose
ends fall off the glass. It just draws it. Three failures render silently on
the device -- no error anywhere -- and this catches all three:

  * text wider than the chord available at its height
  * text written at runtime from an unbounded source with no width/long_mode
  * an MDI glyph used but never compiled into the font's glyphs: list

The second one is the one that shipped. lbl_cfg_value was declared as
"1 : 0.0" and then handed "Timothy - House Blend" at runtime: 21 characters
at 48px is 588px on a 344px screen, so it ran off both edges and erased the
labels either side of it. Checking the DECLARED text finds nothing wrong,
which is why this reads the lambdas that actually write each label.
"""

import os
import re
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knob_geometry import (SAFE_RADIUS, DEFAULT_FONT, FONT_ADV,
                           text_width, text_height, half_chord, fits)


class Loader(yaml.SafeLoader):
    pass


class Tagged(str):
    """An ESPHome !lambda / !secret. Subclasses str so the body is readable."""


def _tag(loader, suffix, node):
    return Tagged(node.value if isinstance(node, yaml.ScalarNode) else '')


Loader.add_multi_constructor('!', _tag)

WIDGET_KINDS = ('label', 'arc', 'obj', 'image', 'button', 'bar', 'line',
                'meter', 'spinner', 'led')

UNBOUNDED_CHARS = 24
LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"')
IDREF = re.compile(r'id\(\s*(\w+)\s*\)')


def string_sources(cfg):
    """Ids whose value is a STRING we do not control the length of.

    A numeric sensor is bounded the moment it goes through snprintf -- a
    float is six characters whatever the machine says. A text_sensor or a
    std::string global is not: it carries whatever Home Assistant put in it,
    which is how a 21-character bean name reached a 48px label.
    """
    out = set()
    for g in cfg.get('globals') or []:
        if 'std::string' in str(g.get('type', '')):
            out.add(g.get('id'))
    for ts in cfg.get('text_sensor') or []:
        if ts.get('id'):
            out.add(ts['id'])
    return out


def walk(widgets, page, out):
    for w in widgets or []:
        if not isinstance(w, dict):
            continue
        for kind in WIDGET_KINDS:
            if kind in w and isinstance(w[kind], dict):
                out.append((page, kind, w[kind]))
                walk(w[kind].get('widgets'), page, out)


def collect(cfg):
    found = []
    for pg in (cfg.get('lvgl') or {}).get('pages') or []:
        walk(pg.get('widgets'), pg.get('id', '?'), found)
    return found


def label_writes(node, out=None):
    """id -> {fonts seen, lambda sources} for every runtime label update."""
    if out is None:
        out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            if k == 'lvgl.label.update' and isinstance(v, dict) and 'id' in v:
                rec = out.setdefault(v['id'], [])
                t = v.get('text')
                if isinstance(t, Tagged):
                    rec.append((v.get('text_font'), str(t)))
                elif isinstance(t, str):
                    rec.append((v.get('text_font'), '"%s"' % t))
            label_writes(v, out)
    elif isinstance(node, list):
        for v in node:
            label_writes(v, out)
    return out


def worst_case(rec, declared_font, strings):
    """Widest (px, font, chars, unbounded) over every write to this label.

    Each write is judged with the font THAT write uses. Taking the largest
    font and the longest string independently is what made this useless at
    first: paint_cfg drops the value label to montserrat_20 for the bean
    name precisely so it fits, and pairing them wrongly hides that.
    """
    worst = (0.0, declared_font, 0, False)
    for font, src in rec:
        f = font or declared_font
        unb = any(n in strings for n in IDREF.findall(src))
        n = 0
        for lit in LITERAL.findall(src):
            if '%' in lit:
                lit = re.sub(r'%[-+0-9.]*[a-z]', '#####', lit)
            n = max(n, len(lit))
        if unb:
            n = max(n, UNBOUNDED_CHARS)
        px = text_width('x' * n, f)
        if px > worst[0]:
            worst = (px, f, n, unb)
    return worst[2], worst[1], worst[3]


def main(path):
    cfg = yaml.load(open(path, encoding='utf-8').read(), Loader=Loader)
    writes = label_writes(cfg)
    strings = string_sources(cfg)
    glyphs = set()
    for f in cfg.get('font') or []:
        for ch in f.get('glyphs') or []:
            if isinstance(ch, str):
                glyphs.add(ch)

    errors, warnings, checked = [], [], 0

    # Opaque things a label can end up behind. A button has a background, so
    # a label sharing its box is not dimmed or overlapped -- it is invisible.
    # lbl_main_care sat at y=54 spanning +46..+62 with two 78px buttons at
    # y=86 spanning +47..+125, and "backflush due" was never once drawn where
    # a person could see it.
    solids = {}
    for page, kind, spec in collect(cfg):
        if kind in ('button', 'obj') and spec.get('bg_color') is not None:
            solids.setdefault(page, []).append(
                (spec.get('id', '(anon)'), spec.get('x', 0) or 0,
                 spec.get('y', 0) or 0, spec.get('width', 0),
                 spec.get('height', 0)))

    for page, kind, spec in collect(cfg):
        if kind != 'label':
            continue
        wid = spec.get('id')
        if spec.get('align', 'TOP_LEFT') != 'CENTER':
            continue
        checked += 1
        x, y = spec.get('x', 0) or 0, spec.get('y', 0) or 0
        declared_font = spec.get('text_font', DEFAULT_FONT)
        bounded_by_widget = (spec.get('width') is not None
                             and spec.get('long_mode'))

        for ch in str(spec.get('text', '')):
            if ord(ch) >= 0xE000 and ch not in glyphs:
                errors.append('%s/%s: glyph U+%04X is not in any font '
                              'glyphs: list -- it renders blank'
                              % (page, wid, ord(ch)))

        if wid in writes:
            n, font, unbounded = worst_case(writes[wid], declared_font, strings)
            if bounded_by_widget:
                continue
            if unbounded:
                # The string comes from Home Assistant, so its length is not
                # ours -- but it is not infinite either. The bean sanitiser
                # in this config caps at 24 characters, and HA option names
                # are of that order. Judge it on whether 24 characters FIT at
                # the font actually used: 24 at montserrat_16 is 226px and
                # survives; the same 24 at montserrat_48 is 672px and is what
                # ran "Timothy - House Blend" off both edges of the glass.
                n = max(n, UNBOUNDED_CHARS)
                warnings.append(
                    '%s/%s: runtime text from an unbounded source and no '
                    'long_mode -- it will clip mid-glyph, not ellipsise'
                    % (page, wid))
            if n == 0:
                continue
            w, h = text_width('x' * n, font), text_height(font)
        else:
            txt = str(spec.get('text', ''))
            font = declared_font
            w, h = text_width(txt, font), text_height(font)

        for sid, sx, sy, sw, sh in solids.get(page, []):
            if (abs(y - sy) < (h + sh) / 2 and abs(x - sx) < (w + sw) / 2):
                errors.append(
                    '%s/%s at (%+d,%+d) is behind %s, which is opaque and '
                    'spans %+d..%+d vertically -- the label is invisible'
                    % (page, wid, x, y, sid, sy - sh // 2, sy + sh // 2))

        ok, over = fits(x, y, w, h)
        if not ok:
            errors.append(
                '%s/%s at (%+d,%+d) %s: worst case %.0fpx wide, only %.0fpx '
                'of glass at that height -- off the edge by %.0fpx'
                % (page, wid, x, y, font, w,
                   half_chord(abs(y) + h / 2) * 2, over * 2))

    for w in warnings:
        print('WARN  ' + w)
    for e in errors:
        print('FAIL  ' + e)
    print('\n%d centred label(s): %d error(s), %d warning(s)'
          % (checked, len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'coffee-knob.yaml'))
