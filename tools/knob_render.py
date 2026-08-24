"""Draw a page of the real config as a PNG, using the font LVGL compiles.

    python tools/knob_render.py coffee-knob.yaml page_cfg states.json out.png

Montserrat-Medium.ttf arrives with the LVGL source that ESPHome downloads,
and montserrat_16 / _20 / _48 are rasterised from that exact file at those
exact pixel sizes. Rendering with it here is therefore not an impression of
the screen, it is the same glyphs at the same size on the same 360px circle.

Everything outside the circle is cut, because the glass is round. A label
that runs off the edge is cut in the PNG in the same place it is cut on the
device -- which is the only property that matters, and the one every
hand-drawn mock of this thing has lacked.
"""

import json
import os
import sys
import math
import yaml
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knob_geometry import SIZE

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

FONT_CANDIDATES = [
    os.path.join(REPO, '.esphome', '.espressif', 'service_d92d8f1e',
                 'lvgl__lvgl_9.5.0_184e5325', 'scripts', 'built_in_font',
                 'Montserrat-Medium.ttf'),
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    for root, _, files in os.walk(os.path.join(REPO, '.esphome')):
        for f in files:
            if f.lower() == 'montserrat-medium.ttf':
                return os.path.join(root, f)
    raise SystemExit('Montserrat-Medium.ttf not found; run a build first')


FONT_PATH = find_font()
SIZES = {'montserrat_16': 16, 'montserrat_20': 20, 'montserrat_48': 48,
         'mdi_40': 40}
_cache = {}


def font(name):
    px = SIZES.get(name, 16)
    if px not in _cache:
        _cache[px] = ImageFont.truetype(FONT_PATH, px)
    return _cache[px]


def measure(text, name):
    f = font(name)
    box = f.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


class Loader(yaml.SafeLoader):
    pass


class Tagged(str):
    pass


Loader.add_multi_constructor(
    '!', lambda l, s, n: Tagged(n.value if isinstance(n, yaml.ScalarNode) else ''))


def rgb(v, default=(255, 255, 255)):
    """Accept 0xRRGGBB from the config and #RRGGBB from a states file."""
    if v is None:
        return default
    if isinstance(v, tuple):
        return v
    if isinstance(v, int):
        n = v
    else:
        s = str(v).strip()
        if s.startswith('#'):
            s = '0x' + s[1:]
        if not s.startswith('0x'):
            return default
        try:
            n = int(s, 16)
        except ValueError:
            return default
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)


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


def render(page, state):
    img = Image.new('RGB', (SIZE, SIZE), (0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = SIZE / 2

    for kind, spec in widgets_of(page):
        wid = spec.get('id', '')
        if spec.get('hidden') and wid not in state:
            continue
        x = spec.get('x', 0) or 0
        y = spec.get('y', 0) or 0

        if kind == 'obj':
            w = spec.get('width', 0)
            h = spec.get('height', 0)
            bw = state.get(wid + '#bw', spec.get('border_width', 0))
            col = rgb(state.get(wid + '#border', spec.get('border_color')),
                      (60, 60, 60))
            if bw:
                d.ellipse([cx + x - w / 2, cy + y - h / 2,
                           cx + x + w / 2, cy + y + h / 2],
                          outline=col, width=int(bw))
        elif kind == 'arc':
            w = spec.get('width', 0)
            aw = spec.get('arc_width', 8)
            ind = spec.get('indicator') or {}
            d.arc([cx + x - w / 2, cy + y - w / 2,
                   cx + x + w / 2, cy + y + w / 2],
                  spec.get('start_angle', 0), spec.get('end_angle', 360),
                  fill=rgb(ind.get('arc_color'), (227, 30, 36)), width=int(aw))
        elif kind == 'label':
            text = state.get(wid, spec.get('text', ''))
            if isinstance(text, Tagged):
                text = '{lambda}'
            text = str(text)
            if not text:
                continue
            fname = spec.get('text_font', 'montserrat_16')
            col = state.get(wid + '#color')
            col = rgb(col) if isinstance(col, str) and col.startswith('#') \
                else rgb(spec.get('text_color'))
            if isinstance(state.get(wid + '#color'), str):
                c = state[wid + '#color'].lstrip('#')
                col = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
            d.text((cx + x, cy + y), text, font=font(fname), fill=col,
                   anchor='mm')

    # The glass is round. Everything past the rim simply is not there.
    mask = Image.new('L', (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, SIZE - 1, SIZE - 1], fill=255)
    out = Image.new('RGB', (SIZE, SIZE), (26, 26, 26))
    out.paste(img, (0, 0), mask)
    ImageDraw.Draw(out).ellipse([0, 0, SIZE - 1, SIZE - 1],
                                outline=(43, 43, 43), width=6)
    return out


def main(cfg_path, page_id, states_path, out_path):
    cfg = yaml.load(open(cfg_path, encoding='utf-8').read(), Loader=Loader)
    page = next((p for p in (cfg.get('lvgl') or {}).get('pages') or []
                 if p.get('id') == page_id), None)
    if page is None:
        raise SystemExit('no such page: %s' % page_id)

    states = json.load(open(states_path, encoding='utf-8'))
    cols = min(3, len(states))
    rows = (len(states) + cols - 1) // cols
    pad, cap = 16, 26
    sheet = Image.new('RGB', (cols * (SIZE + pad) + pad,
                              rows * (SIZE + pad + cap) + pad), (26, 26, 26))
    dd = ImageDraw.Draw(sheet)
    small = ImageFont.truetype(FONT_PATH, 15)

    for i, st in enumerate(states):
        st = dict(st)
        title = st.pop('_title', '')
        r, c = divmod(i, cols)
        ox = pad + c * (SIZE + pad)
        oy = pad + r * (SIZE + pad + cap)
        dd.text((ox + SIZE / 2, oy + 11), title, font=small,
                fill=(170, 170, 170), anchor='mm')
        sheet.paste(render(page, st), (ox, oy + cap))

    sheet.save(out_path)
    print('wrote %s  (%dx%d, font %s)'
          % (out_path, sheet.width, sheet.height, os.path.basename(FONT_PATH)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
