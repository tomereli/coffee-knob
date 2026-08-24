"""Dump every LVGL page's real layout to JSON, for the simulator to consume.

    python tools/knob_export.py coffee-knob.yaml > tools/layout.json

Position, size, font and colour come out of coffee-knob.yaml, so the
simulator draws what the firmware draws. Content does not: it lives in
lambdas, which is why the simulator supplies text per page and per state.
That split is deliberate -- every mock of this device that guessed at
geometry has been wrong, and every one that guessed at content has been
flattering.
"""

import json
import sys
import yaml


class Loader(yaml.SafeLoader):
    pass


class Tagged(str):
    pass


Loader.add_multi_constructor(
    '!', lambda l, s, n: Tagged(n.value if isinstance(n, yaml.ScalarNode) else ''))

FONT_PX = {'montserrat_16': 16, 'montserrat_20': 20, 'montserrat_48': 48,
           'mdi_40': 40}


def col(v):
    if v is None:
        return None
    s = str(v)
    if s.startswith('0x'):
        return '#' + s[2:].upper().rjust(6, '0')
    if isinstance(v, int):
        return '#%06X' % v
    return None


def widgets_of(page):
    out = []

    def walk(ws, parent=None):
        for w in ws or []:
            if not isinstance(w, dict):
                continue
            for kind in ('label', 'arc', 'obj', 'image', 'button'):
                if kind in w and isinstance(w[kind], dict):
                    spec = w[kind]
                    out.append((kind, spec, parent))
                    walk(spec.get('widgets'), spec)
    walk(page.get('widgets'))
    return out


def main(path):
    cfg = yaml.load(open(path, encoding='utf-8').read(), Loader=Loader)

    # Which labels get their text rewritten at runtime -- those are the ones
    # the simulator must be given content for.
    dynamic = set()

    def scan(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == 'lvgl.label.update' and isinstance(v, dict) and 'id' in v:
                    if isinstance(v.get('text'), Tagged):
                        dynamic.add(v['id'])
                scan(v)
        elif isinstance(node, list):
            for v in node:
                scan(v)
    scan(cfg)

    pages = []
    for pg in (cfg.get('lvgl') or {}).get('pages') or []:
        items = []
        for kind, spec, parent in widgets_of(pg):
            e = {'k': kind, 'id': spec.get('id'),
                 'x': spec.get('x', 0) or 0, 'y': spec.get('y', 0) or 0}
            if parent is not None:
                e['in'] = parent.get('id') or 1
                e['x'] += parent.get('x', 0) or 0
                e['y'] += parent.get('y', 0) or 0
            if kind == 'label':
                e['f'] = FONT_PX.get(spec.get('text_font', 'montserrat_16'), 16)
                e['c'] = col(spec.get('text_color')) or '#FFFFFF'
                e['t'] = '' if isinstance(spec.get('text'), Tagged) \
                    else str(spec.get('text', ''))
                if spec.get('id') in dynamic:
                    e['dyn'] = 1
            elif kind in ('obj', 'button'):
                e['w'] = spec.get('width', 0)
                e['h'] = spec.get('height', 0)
                e['bw'] = spec.get('border_width', 0)
                e['bc'] = col(spec.get('border_color')) or '#333333'
                e['bg'] = col(spec.get('bg_color'))
                e['r'] = spec.get('radius', 0) or 0
            elif kind == 'arc':
                e['w'] = spec.get('width', 0)
                e['aw'] = spec.get('arc_width', 8)
                e['a0'] = spec.get('start_angle', 0)
                e['a1'] = spec.get('end_angle', 360)
                e['tc'] = col(spec.get('arc_color')) or '#2A2A2A'
                ind = spec.get('indicator') or {}
                e['ic'] = col(ind.get('arc_color')) or '#E31E24'
                e['max'] = spec.get('max_value', 100)
            elif kind == 'image':
                e['w'] = 124
                e['h'] = 60
            items.append(e)
        pages.append({'id': pg.get('id'), 'w': items})

    json.dump({'pages': pages}, sys.stdout, separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'coffee-knob.yaml')
