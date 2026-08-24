---
name: round-lcd-ui
description: >
  Building and changing a user interface on a small round LCD driven by a
  rotary encoder, under ESPHome + LVGL. Use whenever a screen, page, label,
  menu or gesture is being added or altered on such a device, and before
  flashing any layout change.

  TRIGGER WHEN: adding or moving a widget, changing a font size, adding a
  menu item, changing what a turn/tap/hold does, or "make the screen show X".

  SYMPTOMS THIS PREVENTS: text clipped at the edge of the glass, a label
  overwriting its neighbours, an icon rendering blank, a gesture that means
  two different things, a screen approved from a drawing that could not have
  shown the defect.
---

# Round LCD UI, driven by a knob

Written from the ground up on a 360x360 round panel in a rotary knob. Every
rule below is here because it was learned by shipping the mistake.

## The one rule

**Never flash a layout change the user has not seen rendered.**

Not a description of it. Not a hand-drawn SVG of what it should look like.
A render produced *from the config that is about to be flashed*, looked at
by you, then shown to them.

A hand-drawn mock is an argument for a design. A rendered mock is evidence
about one. The first radial-menu design on this device was approved from a
drawing made in idealised SVG with system fonts and no clipping. On the
glass, half the labels were cut mid-word and a bean name ran across the
whole screen. The drawing was incapable of showing either failure, so it
showed a design that did not exist.

## Why a round screen is different

The panel is a circle. Horizontal room is not the screen width, it is the
**chord at that height**:

    available_half_width(dy) = sqrt(radius^2 - dy^2)

At the vertical centre a label has the full diameter. Sixty pixels above it,
noticeably less. Near the top or bottom, almost none. A label that fits
perfectly at y=0 is cut in half at y=-140, and nothing in the toolchain will
say so: LVGL lays it out, the compiler is happy, and the defect appears only
on the glass.

Keep real content inside a safe radius a few pixels short of the physical
one. The rim curves and the bezel overlaps; a glyph touching the true edge
reads as broken even when it is technically inside.

## LVGL facts that bite

- **Labels do not wrap.** A long string is one long line. Any label whose
  text is written at runtime needs `width:` *and* `long_mode:` or it will run
  off both edges. `long_mode: DOTS` to ellipsise, `SCROLL_CIRCULAR` to move.
- **Fonts are compiled in at fixed pixel sizes.** Only the sizes declared in
  the config exist. There is no "slightly smaller".
- **Icon fonts carry an explicit glyph list.** A glyph used but not listed
  renders as *nothing* -- no error, no box, no warning. Adding one forces a
  full rebuild.
- **The declared `text:` on a widget is a placeholder.** The content comes
  from whatever writes it at runtime. Checking the declared text tells you
  nothing about what will be on screen.
- **The font can be changed per write.** A paint routine may drop a label to
  a smaller size for the one item that needs it. Judging a label by its
  declared font alone finds bugs that are not there and misses ones that are.

## Gestures on a knob

The whole vocabulary is turn, tap, hold. That is three verbs, so each one
gets exactly one meaning:

- **turn** moves within the current context. Never commits, never fires.
- **tap** is the affirmative: enter, advance, commit.
- **hold** leaves. Everywhere. No exceptions.

The temptation is to hang a second action on hold "just here". Do not. A
destructive action reachable by the same gesture that means *leave*
everywhere else will eventually be triggered by someone reaching to leave.
Destructive actions get two deliberate taps on their own screen, with the
armed state visible.

**A press on a dark screen must only wake it.** These panels sleep. The
first press of the day lands on a screen the user cannot read, and without a
guard it activates whatever is under the finger. Stamp the moment the
backlight comes up and ignore input for a few hundred milliseconds after it.

## Three checks, and none of them substitutes for another

They fail differently, which is the point. Every regression on this project
got past two of them because only one was run.

**Geometry lint** -- reads the config, computes the chord at each label's
height, fails on text that cannot fit, on a glyph missing from the font's
list, and on a label sitting behind an opaque widget. Catches what is
computable. Blind to anything about behaviour or rendering.

**A subagent reading the source** -- give it the simulator and the firmware
config and ask where they disagree. One pass found twenty behavioural
mismatches: a gesture bound to one action in the simulator and three in the
firmware, rotation that adjusts a value on the device and does nothing in the
mock, a ring that carries a verdict colour on the glass and a fixed colour in
the preview. It cannot see anything that only exists in pixels.

**A browser, driven, screenshotted, looked at** -- load the page, click the
real controls, photograph each screen, and *look at the images*. This is the
only check that finds a font that failed to load, a CSS rule losing to a more
specific one, or a glyph rendering as a tofu box. All three of those shipped
past the other two checks in a single afternoon.

**A checking tool is broken until it has been demonstrated against a known
failure.** The geometry lint reported "0 errors" on the exact layout that had
just been photographed as broken, and took three attempts to become useful.
Run any new check against the last thing that actually went wrong; if it
passes that, it is decoration.

## Process for any layout change

1. Change the config.
2. Run the geometry lint. It reads the config, computes the chord at each
   label's height, and fails on anything that cannot fit.
3. Render the affected pages **including their ugly states** -- longest
   possible string, unavailable data, the mode that makes an item read
   "n/a". A mock of the happy path is the same lie as a drawing.
4. Drive it in a browser and look at the screenshots yourself. Reading the
   source is not looking; a subagent auditing the JavaScript found twenty
   real defects and could not see that every icon on the page was a tofu box.
5. Show it to the user and get a yes.
6. Only then flash.

Skipping step 4 has caused every UI regression on this project, including
one where the mock renderer's own bug was shipped as a finding to the user.

## Judgement

- **A dead screen is worse than a missing one.** An item that reads "n/a" in
  the mode the user is actually in is a stop on the daily path that answers
  nothing. Fold it into a contextual item that only shows the fields the
  current mode has.
- **Show one thing large.** Small round screens read at a glance from across
  a room. Eight labels around the rim plus a value plus a hint is a debug
  page. The screens people liked on this device showed a single number.
- **An edit indicator should be quieter than the content.** A hard white ring
  around a black screen is the brightest thing on the panel, and it is only
  saying "you are editing".

## Keeping this current

**Every time a UI defect is found on this class of device, add the rule that
would have caught it, to this file, in the same change that fixes it.** The
value here is entirely in the specificity -- a general note about "check your
layout" would not have prevented a single failure listed above.
