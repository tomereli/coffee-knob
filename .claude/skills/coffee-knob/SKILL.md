---
name: coffee-knob
description: >
  Working on the coffee-knob device: a Waveshare ESP32-S3-Knob-Touch-LCD-1.8
  controlling a La Marzocco Linea Micra, with shot data from a Mahlkonig E64
  WS. Use for any change to coffee-knob.yaml, any flash, any Home Assistant
  entity this device reads or writes, and before proposing espresso features.

  TRIGGER WHEN: editing coffee-knob.yaml, flashing the knob, adding a
  settings item or card, touching the rating flow, or answering "what should
  the knob show".

  SYMPTOMS THIS PREVENTS: a flash that cannot be undone over the air, a
  glyph that renders blank, a second control loop fighting the grinder,
  logged shot times that are quietly wrong.
---

# coffee-knob

Read `round-lcd-ui` first for anything touching a screen. This file is what
is true about *this* machine, this grinder and this config.

## The hardware chain

- **Knob**: Waveshare ESP32-S3-Knob-Touch-LCD-1.8 (Guition JC3636K518C).
  360x360 round ST77916 over QSPI, CST816 touch, DRV2605 haptics on the same
  I2C bus, one rotary encoder on GPIO8/7. **The knob has no push contact** --
  turn, tap and hold are the entire input vocabulary.
- **Machine**: La Marzocco Linea Micra, **plumbed in**. The water-tank sensor
  can never say anything but "ok"; do not put it on a screen.
- **Grinder**: Mahlkonig E64 WS with Grind-by-Sync.

Every value on screen is a Home Assistant entity and every action is a
service call back to HA. If HA is unreachable the knob is lit but inert.

## Two things that will cost you a rebuild

**The file must contain zero backslashes.** Content written through the
ESPHome dashboard API gets its backslashes doubled in transit; a glyph
written as an escape arrives as a literal ten-character string and ESPHome
rejects the font. All MDI glyphs are stored as literal characters.

**`mdi_40` has an explicit glyph list.** An icon used but not listed renders
blank, silently. Add it to `glyphs:` and expect a full rebuild.

## Flashing

The add-on now builds from git (`packages:` pointing at the repo), so the
repo is the source of truth and the add-on cannot go stale.

To flash from this machine with the ESPHome CLI:

    $env:ESPHOME_ESP_IDF_PREFIX = "C:\ei"
    esphome run coffee-knob.yaml --device coffee-knob.local --no-logs

- **Run it from PowerShell, not Git Bash.** ESP-IDF refuses to build under
  MSys and says so only deep in a traceback.
- **`ESPHOME_ESP_IDF_PREFIX` must be short.** The toolchain nests ~245
  characters deep; from a normal path that blows past Windows' 260 limit and
  surfaces as `bits/c++config.h: No such file or directory`, which looks
  like a compiler bug and is not.
- **`esphome upload` does not recompile.** It ships whatever binary is in
  the build directory. Using it after changing secrets flashed a firmware
  containing the *old* keys, which broke HA's API connection and locked OTA
  behind a password no longer written down anywhere. Use `run`.
- **Clear `.esphome/storage/*.yaml.json` after changing secrets.** ESPHome
  caches the validated config and will not re-read them.

## Secrets

`coffee_knob_api_key`, `coffee_knob_ota_password`, `coffee_knob_ap_password`
and the wifi pair exist in three copies that must agree: the add-on's
`/config/esphome/secrets.yaml`, the local gitignored `secrets.yaml`, and what
is baked into the running firmware. **Never generate a new value for an
already-flashed device** -- `secrets.yaml.example` suggests `openssl rand`,
which is right for a first flash and wrong for every one after it. A fresh
API key means HA cannot decrypt and every entity goes unavailable; a fresh
OTA password means the next flash must be over USB.

## Espresso judgement

- **Grind-by-Sync is already an integral controller on grind setting**, with
  a full shot of dead time. Telling the user to also go finer or coarser puts
  two loops on one plant and they hunt. Report what the grinder did; do not
  instruct a duplicate correction.
- **The grinder's recipe target can only be changed at the grinder.** An
  override on the knob is legitimate, but while it disagrees with
  `brew_time_target` the two are aiming at different numbers and the screen
  should say so rather than pretend.
- **There is no live weight during extraction.** The Sync bundle arrives as
  one atomic message *after* the shot; every sensor changes within ~5ms.
  Live grams and a live ratio are impossible. This is hardware, not a gap.
- **`brewing_active` is polled about once a second**, so the knob's stopwatch
  is good to about a second at each edge. Do not display or log tenths as if
  they were measured.
- **Time the stopwatch from `millis()`, never by counting interval ticks.**
  The 100ms interval coalesces whenever the panel is being flushed, so a tick
  counter reads low -- and that number was being logged to HA as the shot
  time, biasing the whole history short.

## The rating flow, and what it is for

The user rates shots: serve (espresso/milk), taste (-2 sour .. +2 bitter),
score 1-5, written to HA and appended to a shot log.

**Today nothing reads any of it back.** The ring is coloured against a target
ratio typed by hand. The obvious payoff is to judge a shot against the band
the user's own 4- and 5-star shots occupy, segmented by bean and by serve --
turning "did you hit the number you guessed" into "was this like the cups you
liked". Not built yet; it is the highest-value idea on the list.

## The preview pipeline

    python tools/knob_lint.py coffee-knob.yaml          # geometry, fails loudly
    python tools/knob_export.py coffee-knob.yaml > tools/layout.json
    python tools/build_sim.py tools/layout.json knob-sim.html
    python tools/knob_shots.py knob-sim.html shots/     # drives Chromium, shoots every screen

`knob_shots.py` walks 22 screens, reports any label that overflows and any
console error, and writes a PNG of each. Look at the PNGs. Two defects
reached the user's hands because this step did not exist: a settings menu
whose rim labels were cut mid-word, and an icon font blocked by the artifact
CSP so every glyph drew as an empty square.

Artifacts load fonts from Google Fonts and **nothing else** -- a CDN
stylesheet is silently blocked. The simulator therefore draws Material
Symbols chosen to mean the same thing as each MDI glyph. Artwork differs from
the device; position and size, which is what a layout is judged on, do not.

## Verify before you act on a review

Findings from a review -- human or agent -- get checked against the code
before anything is changed. In one pass of five reviewers, several severe
claims held up exactly (`rate_mode` leaking between shots, a power toggle
that inverted its own intent, a stopwatch that under-counted) and others did
not survive contact with the file. Quote the line, then act.

## Keeping this current

**When a defect is found here, add the rule that would have prevented it to
this file in the same change that fixes it.** Everything above is here
because it went wrong once.
