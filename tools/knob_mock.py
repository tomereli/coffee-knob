"""Render a page of the real config as it will actually look on the glass.

    python tools/knob_mock.py coffee-knob.yaml page_cfg > mock.html

Geometry, fonts, sizes and colours are read from coffee-knob.yaml, so the
mock cannot drift from the firmware -- they are the same source. What the
mock CANNOT know is what a lambda will put in a label at runtime, so states
are supplied explicitly and every one of them is drawn. That is the whole
point: the first mock of the radial dial was hand-drawn in an idealised SVG
that had no way to show a 21-character bean name running off both edges,
so it showed a design that does not exist.

Rules this enforces by construction:
  * the canvas is a CIRCLE and overflow is hidden, so anything off the glass
    is visibly cut here exactly as it is cut there
  * text never wraps, because LVGL labels do not wrap
  * only the fonts compiled into the firmware are available
"""

import json
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knob_geometry import SIZE, SAFE_RADIUS

# Montserrat is fetched if the page has a real origin, but a data: URL has
# none and silently falls back -- which rendered the first mock entirely in
# the browser's serif default. The stack ends in a concrete sans so a failed
# fetch still looks like the device instead of like a book.
SANS = "Montserrat,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
CSS_FONT = {
    'montserrat_16': (SANS, 16, 500),
    'montserrat_20': (SANS, 20, 500),
    'montserrat_48': (SANS, 48, 500),
    'mdi_40': ("'Material Design Icons'," + SANS, 40, 400),
}


class Loader(yaml.SafeLoader):
    pass


class Tagged(str):
    pass


Loader.add_multi_constructor(
    '!', lambda l, s, n: Tagged(n.value if isinstance(n, yaml.ScalarNode) else ''))


def hexcolor(v, default='#FFFFFF'):
    if v is None:
        return default
    if isinstance(v, int):
        return '#%06X' % v
    s = str(v)
    if s.startswith('0x'):
        return '#' + s[2:].upper().rjust(6, '0')
    return s


def widgets_of(page):
    out = []

    def walk(ws):
        for w in ws or []:
            if not isinstance(w, dict):
                continue
            for kind in ('label', 'arc', 'obj', 'image', 'button'):
                if kind in w and isinstance(w[kind], dict):
                    out.append((kind, w[kind]))
                    walk(w[kind].get('widgets'))
    walk(page.get('widgets'))
    return out


def render_state(page, state, title):
    """One circular screen with the label texts from `state` applied."""
    parts = ['<div class="wrap"><div class="cap">%s</div><div class="glass">'
             % title]
    for kind, spec in widgets_of(page):
        wid = spec.get('id', '')
        if spec.get('hidden') and wid not in state:
            continue
        x = spec.get('x', 0) or 0
        y = spec.get('y', 0) or 0

        if kind == 'obj':
            w = spec.get('width', 0)
            h = spec.get('height', 0)
            bw = spec.get('border_width', 0)
            parts.append(
                '<div class="obj" style="width:%dpx;height:%dpx;margin-left:'
                '%dpx;margin-top:%dpx;border:%dpx solid %s;border-radius:%dpx">'
                '</div>' % (w, h, x, y, bw,
                            hexcolor(spec.get('border_color'), '#333'),
                            spec.get('radius', 0) or 0))
        elif kind == 'arc':
            w = spec.get('width', 0)
            ind = spec.get('indicator') or {}
            a0 = spec.get('start_angle', 0)
            a1 = spec.get('end_angle', 360)
            parts.append(
                '<svg class="arc" width="%d" height="%d" style="margin-left:'
                '%dpx;margin-top:%dpx" viewBox="0 0 %d %d">%s</svg>'
                % (w, w, x, y, w, w,
                   svg_arc(w / 2, w / 2, w / 2 - spec.get('arc_width', 8) / 2,
                           a0, a1, spec.get('arc_width', 8),
                           hexcolor(ind.get('arc_color'), '#E31E24'))))
        elif kind == 'label':
            text = state.get(wid, spec.get('text', ''))
            if isinstance(text, Tagged):
                text = '{lambda}'
            fam, size, weight = CSS_FONT.get(
                spec.get('text_font', 'montserrat_16'),
                CSS_FONT['montserrat_16'])
            colour = hexcolor(spec.get('text_color'), '#FFFFFF')
            if wid + '#color' in state:
                colour = state[wid + '#color']
            parts.append(
                '<div class="lbl" style="margin-left:%dpx;margin-top:%dpx;'
                'font-family:\'%s\';font-size:%dpx;font-weight:%d;color:%s">'
                '%s</div>'
                % (x, y, fam, size, weight, colour,
                   str(text).replace('<', '&lt;')))
    parts.append('</div></div>')
    return ''.join(parts)


def svg_arc(cx, cy, r, a0, a1, width, colour):
    import math
    if a1 < a0:
        a1 += 360
    large = 1 if (a1 - a0) > 180 else 0
    p0 = (cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    p1 = (cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1)))
    if abs(a1 - a0) >= 359:
        return ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
                'stroke-width="%d"/>' % (cx, cy, r, colour, width))
    return ('<path d="M %.1f %.1f A %.1f %.1f 0 %d 1 %.1f %.1f" fill="none" '
            'stroke="%s" stroke-width="%d"/>'
            % (p0[0], p0[1], r, r, large, p1[0], p1[1], colour, width))


HEAD = """<style>
body{background:#1a1a1a;color:#ddd;font-family:system-ui;margin:0;padding:24px}
.grid{display:flex;flex-wrap:wrap;gap:28px}
.wrap{width:%dpx}
.cap{font-size:13px;color:#999;margin-bottom:8px;text-align:center}
.glass{position:relative;width:%dpx;height:%dpx;border-radius:50%%;
  background:#000;overflow:hidden;border:6px solid #2b2b2b}
.glass>*{position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%)}
.lbl{white-space:nowrap}
.edge{position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%);
  width:%dpx;height:%dpx;border-radius:50%%;border:1px dashed #444;
  pointer-events:none}
</style>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css" rel="stylesheet">
""" % (SIZE, SIZE, SIZE, SAFE_RADIUS * 2, SAFE_RADIUS * 2)


def main(path, page_id, states_path=None):
    cfg = yaml.load(open(path, encoding='utf-8').read(), Loader=Loader)
    page = None
    for pg in (cfg.get('lvgl') or {}).get('pages') or []:
        if pg.get('id') == page_id:
            page = pg
    if page is None:
        print('no such page: %s' % page_id, file=sys.stderr)
        return 2

    states = json.load(open(states_path, encoding='utf-8')) if states_path \
        else [{'_title': 'as declared'}]

    out = [HEAD, '<div class="grid">']
    for st in states:
        title = st.pop('_title', '')
        out.append(render_state(page, st, title))
    out.append('</div>')
    print(''.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2],
                  sys.argv[3] if len(sys.argv) > 3 else None))
