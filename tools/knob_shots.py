"""Drive the simulator in a real browser and photograph every screen.

    python tools/knob_shots.py knob-sim.html out/

This exists because reading source is not looking. A subagent audited the
simulator's JavaScript and found twenty behavioural mismatches, and could not
see that every icon was rendering as a tofu box -- that defect only exists in
pixels. So: load the page, click the real controls, screenshot the glass.

Each shot is the 360px circle only, cropped, so what comes back is what the
panel would show and nothing else.
"""

import os
import sys
import asyncio
from playwright.async_api import async_playwright

# (label, [clicks to get there from a fresh load])
SHOTS = [
    ('main-ready',        []),
    ('main-heating',      [('#mach button[data-s="heat"]', 1)]),
    ('main-standby',      [('#mach button[data-s="off"]', 1)]),
    ('card-result',       [('#cw', 1)]),
    ('card-grinder',      [('#cw', 2)]),
    ('card-care',         [('#cw', 3)]),
    ('card-boilers',      [('#cw', 4)]),
    ('shot-live',         [('#scene button[data-v="shot"]', 1)]),
    ('shot-waiting',      [('#scene button[data-v="wait"]', 1)]),
    ('backflush',         [('#scene button[data-v="clean"]', 1)]),
    ('rating-serve',      [('#scene button[data-v="result"]', 1), ('#hold', 1)]),
    ('rating-taste',      [('#scene button[data-v="result"]', 1), ('#hold', 1),
                           ('#tap', 1)]),
    ('rating-score',      [('#scene button[data-v="result"]', 1), ('#hold', 1),
                           ('#tap', 2)]),
    ('cfg-steam-boiler',  [('#tap', 1)]),
    ('cfg-coffee-temp',   [('#tap', 1), ('#cw', 2)]),
    ('cfg-temp-editing',  [('#tap', 1), ('#cw', 2), ('#tap', 1)]),
    ('cfg-target-time',   [('#tap', 1), ('#cw', 4)]),
    ('cfg-beans-long',    [('#bean button[data-b="2"]', 1), ('#tap', 1),
                           ('#cw', 5)]),
    ('cfg-preinf-off',    [('#tap', 1), ('#cw', 6)]),
    ('cfg-dead-screen',   [('#tap', 1), ('#cw', 7)]),
    ('cfg-preinf-live',   [('#mode button[data-m="2"]', 1), ('#tap', 1),
                           ('#cw', 7)]),
    ('cfg-backflush',     [('#tap', 1), ('#cw', 10)]),
]


async def main(page_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    url = 'file:///' + os.path.abspath(page_path).replace('\\', '/')
    problems = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for name, steps in SHOTS:
            pg = await browser.new_page(viewport={'width': 1100, 'height': 900})
            errors = []
            pg.on('console', lambda m: errors.append(m.text)
                  if m.type == 'error' else None)
            pg.on('pageerror', lambda e: errors.append(str(e)))
            await pg.goto(url)
            # Webfonts decide whether an icon is a glyph or a tofu box, so
            # nothing is photographed until they have actually loaded.
            await pg.evaluate('document.fonts.ready')
            for sel, n in steps:
                for _ in range(n):
                    await pg.click(sel)
            await pg.wait_for_timeout(120)

            glass = await pg.query_selector('.glass')
            await glass.screenshot(path=os.path.join(out_dir, name + '.png'))

            # What the fit checker says about this exact screen.
            flag = await pg.eval_on_selector('#fit', 'e=>e.textContent')
            cls = await pg.eval_on_selector('#fit', 'e=>e.className')
            if 'bad' in cls:
                problems.append('%-18s %s' % (name, flag))
            if errors:
                problems.append('%-18s JS ERROR: %s' % (name, errors[0][:90]))
            await pg.close()
        await browser.close()

    print('%d screens photographed into %s' % (len(SHOTS), out_dir))
    if problems:
        print('\nflagged:')
        for p in problems:
            print('  ' + p)
    else:
        print('no overflow and no console errors on any screen')


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
