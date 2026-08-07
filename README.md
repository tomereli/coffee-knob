# coffee-knob

An ESPHome config that turns a **Waveshare ESP32-S3-Knob-Touch-LCD-1.8** (a.k.a. Guition **JC3636K518C-I-YR1**) into a controller and shot display for a **La Marzocco Micra**, with shot data from a **Mahlkönig E64 WS + Sync scale**.

Everything runs through Home Assistant. Nothing depends on a cloud service at runtime — fonts and the logo are baked into the firmware at compile time.

![board](https://www.waveshare.com/esp32-s3-knob-touch-lcd-1.8.htm)

---

## Screens

| Screen | When | Shows |
|---|---|---|
| **Main** | idle | La Marzocco mark, `OFF` / `HEATING` / `READY`, last shot ratio + time, power and menu buttons |
| **Control** | tap the gear | steam boiler, steam level, coffee temperature, backflush — knob to move, tap to act |
| **Shot** | `brewing_active` turns on | live seconds counter and a filling arc round the bezel |
| **Result** | when the Sync bundle lands | brew ratio, dose → yield, shot time, quality, and the grind-setting correction |
| **Steaming** | inferred (see below) | steam indicator |

---

## Hardware notes

This is the **K518 / K-series** board — the one with the rotating knob *around* the screen. Its pinout differs from both the **W518** and the **K718**. Do not reuse pins across them.

```
Display QSPI (ST77916):  CLK 13   CS 14   D0-D3 15/16/17/18   RST 21
Touch CST816 (I²C):      SDA 11   SCL 12  INT 9   RST 10        (chip answers at 0x15)
Haptics DRV2605:         same I²C bus, 0x5A, EN strapped to 3V3, TRIG to GND
Knob EC1:                A GPIO8   B GPIO7
Backlight:               GPIO47 (PWM)
```

Pin values are taken verbatim from [KrX3D/WaveShare-Knob-Esp32S3](https://github.com/KrX3D/WaveShare-Knob-Esp32S3) and cross-checked against the board schematic in that repo. The unmodified upstream files are kept in [`reference/`](reference/) so you can diff them.

**16 MB flash means the first flash must be over USB.** A partition table change can't be applied over the air. Flash once via [web.esphome.io](https://web.esphome.io) with a **USB-A → USB-C** cable, then everything after that is OTA.

> On this board the cable *orientation* selects which of the two chips you talk to. With a C→C cable it's a coin flip which one you get.

---

## Things that cost me time

Collected so nobody else has to rediscover them.

### The knob is two encoders, not one

The board has **two** rotary encoders, `SW1` and `SW2` (both SSCM110100), wired one per MCU:

- `EC1_A`→**GPIO8**, `EC1_B`→**GPIO7** — on the ESP32-**S3**
- `EC2_A`→**IO19**, `EC2_B`→**IO22** — on the second, plain ESP32

So the S3 has a complete A/B pair of its own and reads both directions unaided. You never need to flash the second MCU. Note it is **not** a quadrature encoder in the PCNT sense — one clean pulse per detent, direction encoded by *which* channel fires — so ESPHome's stock `rotary_encoder` reads zero. This config uses `rotary_encoder_custom` from KrX3D.

The knob has **no push contact**. `SW2` is a 4-pin part: two commons to ground, A and B out. There is no press to detect.

### DRV2605 acknowledges its address but NAKs register reads

The bus scan finds `0x5A` and writes work fine — but reads don't. [RAR/esphome-drv2605](https://github.com/RAR/esphome-drv2605) reads the status register first thing in `setup()`, so it bails out **before** setting LRA mode and selecting library 6, then marks itself `FAILED`. Effects still fire (because writes work), so you get a buzz — just the wrong one, running on ERM defaults with an LRA motor.

This config drops the component and writes the six registers directly over I²C instead:

```
0x01 MODE     = 0x00   out of standby, internal trigger
0x1A FEEDBACK = 0x80   LRA
0x03 LIBRARY  = 0x06   LRA library
0x04/0x05/0x0C         waveform, terminator, GO
```

### LVGL text lambdas must return `const char*`

On ESPHome **2026.7+**, a single-expression lambda gets inlined, skipping the `std::string` conversion, and `.c_str()` is then called on the result. Anything that returns `std::string` from a one-liner fails to compile. Use a **multi-statement** lambda:

```yaml
text: !lambda |-
  static char b[28];
  snprintf(b, sizeof(b), "1 : %.1f", id(last_ratio));
  return b;
```

### Getting an image into the ESPHome add-on

The add-on's config directory only accepts **text** files, so you can't upload a PNG. But ESPHome detects SVG by sniffing for `<svg` in the first bytes and rasterises it with cairosvg at compile time — so an SVG works, and an SVG can carry a raster inline as a base64 `data:` URI if you don't have a vector source.

### Display rotation belongs on `lvgl:`, not `display:`

LVGL rejects a rotated display and rotates touch input itself via `rotate_coordinates()`. Put `rotation: 180` on the `lvgl:` block.

---

## Home Assistant notes

### Enable service calls or the knob can't control anything

When you adopt an ESPHome device, **`allow_service_calls` defaults to off**. Every `homeassistant.action` silently does nothing, with no error anywhere. Settings → Devices & Services → ESPHome → Configure.

### The La Marzocco power state bounces

Calling `switch.toggle` on the machine produces this, and it does it from the HA UI too — the knob isn't involved:

```
17:17:04.733  on
17:17:04.737  off    ← 4 ms later
17:17:06.762  on     ← 2 s later, settles
```

The integration sets the state optimistically, its **Bluetooth** call to the machine fails (`components/lamarzocco/switch.py`, out of BLE connection slots), it rolls back, then the cloud confirms. The config masks this by holding its own intent for 6 seconds after a press. The real fix is a Bluetooth proxy near the machine.

### `brewing_active` is polled once a second

Every interval between on and off is an exact whole number of seconds (`15:59:43.332 → 15:59:47.333`). The on-screen timer therefore starts up to a second after you move the lever. The authoritative figure is `shot_time` from the Sync scale, which is what the result card shows.

### Mahlkönig Sync sends one bundle, it does not stream

All the shot sensors change within ~5 ms of each other and `yield_weight` records exactly one state change per shot. **Live grams during extraction are not possible.** The config triggers on the `grind_event_uuid` attribute — unique per grind, so repeat shots with identical numbers still fire exactly once — and waits 800 ms for the whole bundle to land before reading.

`grind_setting` is **disc distance in microns** and Grind-by-Sync rewrites it after every shot from the scale's duration and yield, so the interesting number is the *delta*. `grind_setting_target` is the from-scratch starting point, not a target being chased.

---

## Install

1. Copy `coffee-knob.yaml`, `lamarzocco.svg` and a filled-in `secrets.yaml` into your ESPHome config directory.
2. Edit the `substitutions:` block to match your entity IDs.
3. Build, download the **factory** binary, flash once over USB via [web.esphome.io](https://web.esphome.io).
4. Adopt in Home Assistant and **turn on `allow_service_calls`**.

Everything after the first flash is over the air.

---

## Credits

- [KrX3D/WaveShare-Knob-Esp32S3](https://github.com/KrX3D/WaveShare-Knob-Esp32S3) — the bring-up this is built on, the `rotary_encoder_custom` component, and the board schematic
- [nkinnan/Waveshare-ESP32-S3-Knob-Touch-LCD-1.8…](https://github.com/nkinnan/Waveshare-ESP32-S3-Knob-Touch-LCD-1.8_and_Guition-K5-Knob-Series-JC3636K518) — hardware documentation, including the cable-orientation quirk
- [MichalZaniewicz/esphome-guition-jc3636k718c-va](https://github.com/MichalZaniewicz/esphome-guition-jc3636k718c-va) — the K718 sibling; different pinout, but its notes on LVGL buffer sizing and the non-quadrature knob saved real time
- [RAR/esphome-drv2605](https://github.com/RAR/esphome-drv2605) — haptics component
- [ESPHome discussion #3253](https://github.com/orgs/esphome/discussions/3253) — the community thread on this board

The La Marzocco name and mark are trademarks of La Marzocco S.r.l., used here only to identify the machine this controls. Not affiliated with or endorsed by La Marzocco or Mahlkönig.

## License

MIT — see [LICENSE](LICENSE).
