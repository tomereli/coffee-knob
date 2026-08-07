# Task Brief: get grind data out of the Mahlkönig grinder

**For:** Faibel
**From:** the Coffee Knob POC (Opus) — this is a hand-off, not a request for help on my task
**Owner:** Tomer

---

## 1. Why this exists

There is a working ESP32-S3 knob display (`coffee-knob`, ESPHome → Home Assistant) that already shows La Marzocco Micra state, toggles the machine, and runs a live shot timer. Machine-side data is solved.

**Grinder-side data is not.** To log a shot properly you need dose, grind setting and grind time, and right now the only way to get them is for a human to type them into `input_number` helpers. Tomer has explicitly refused to hand-type shot data — reasonably. So either the grinder gives up its data, or shot logging stays a toy.

**Your job: find out whether the Mahlkönig grinder can be made to emit per-grind data, and if so, build the path.**

---

## 2. Objective

Get, per grind event, as many of these as exist:

- dose weight (g) — the important one
- grind setting / micron value
- grind duration
- timestamp
- grinder model / firmware / serial

Landing zone: Home Assistant entities. Local protocol strongly preferred over cloud.

**A clean, evidenced "this is not possible on this model" is a perfectly acceptable outcome.** Do not fake a result.

---

## 3. Prior art — start here, do not rediscover

| Thing | Why it matters |
|---|---|
| [`kevinschweikert/ha-mahlkoenig`](https://github.com/kevinschweikert/ha-mahlkoenig) | An existing Home Assistant integration for the **Mahlkönig X54**. This is the single highest-value lead. Read the source first and find out what transport it uses (it appears to talk to the grinder over the local network). If Tomer's grinder is an X54 or shares firmware, this may be most of the answer. |
| [Mahlkönig Home iOS app](https://apps.apple.com/us/app/mahlk%C3%B6nig-home/id1641868454) | The official app. Whatever it can see is, by definition, extractable. |
| [The Sync System](https://www.mahlkoenig.com/products/the-sync-system) / [Sync Scale](https://www.mahlkoenig.com/products/mahlkonig-sync-scale) | Mahlkönig's connected grinding ecosystem. **The Sync Scale is very likely the actual source of dose weight** — the grinder itself may not weigh anything. Establish early whether dose data can exist at all without this scale. |
| [Grind-by-Sync quick start (PDF)](https://downloads.mahlkoenig.de/Service/Quick_Start_Guide_Mahlkoenig_Grind_by_Sync_Espresso_Grinder.pdf) | Vendor doc describing the grinder↔scale pairing. Good for understanding the protocol's shape. |

Also relevant as a model to copy: the **La Marzocco** HA integration already working in this system was itself built by reverse-engineering a vendor app. Same class of problem, known-good outcome.

---

## 4. Approach, cheapest first

Do not skip to step 5. Steps 1–4 are hours; step 5–6 are days.

1. **Identify the hardware.** Exact model, firmware version, what radios it has. Half the models in this range have no connectivity at all — establish this before anything else.
2. **Try the existing integration.** If `ha-mahlkoenig` installs and talks, you may be done.
3. **Network recon.** Is the grinder on the LAN? mDNS/SSDP browse, ARP scan, then port scan it. Look for HTTP/WebSocket. Many of these devices run a small local web API.
4. **BLE recon.** Scan with `bleak`/nRF Connect, enumerate GATT services and characteristics, subscribe to notifications and grind a dose. The Sync ecosystem is Bluetooth, so this is where dose weight most likely lives.
5. **App traffic inspection** — see §5 for the correct method.
6. **Static analysis.** Pull the Android APK, decompile with `jadx`, grep for endpoints, UUIDs, protocol constants. Often faster than dynamic analysis once you know what you're looking for.

---

## 5. Correcting one assumption before you waste time on it

Tomer suggested "simulating my iPhone on the PC". **That is not a viable route** — iOS apps cannot be run on a PC, and the iOS Simulator does not run App Store builds. The two things that actually work:

- **(a) Proxy the real iPhone.** Run `mitmproxy` on the PC, point the iPhone's Wi-Fi proxy at it, install and trust the mitm CA on the phone. Works immediately *unless* the app pins certificates. Check for pinning first — it's a 10-minute test.
- **(b) Android emulator + the Android build of the app.** Slower to set up, but far more tractable: if the app pins certs, you can bypass it with Frida on an emulator, which you cannot easily do on a stock iPhone.

**(b) is the recommended path if (a) hits pinning.** Ask Tomer whether an Android device or Google account is available before committing.

Note also: if the transport turns out to be **BLE, not HTTP**, proxying is the wrong tool entirely — use BLE sniffing (nRF52840 dongle) or Android's HCI snoop log, which is free and often enough.

---

## 6. Scope and constraints

This is **interoperability work on hardware Tomer owns, using his own account** — the same thing every vendor-app-derived Home Assistant integration is built on. Keep it there:

- Tomer's own grinder, own app login, own network. He can give you his app credentials.
- **Do not** touch other users' accounts or data, and do not attack Mahlkönig's infrastructure — no credential stuffing, no enumeration of other users' devices, no load beyond what the app itself generates.
- **Do not** commit credentials, tokens or captured session data into any repo or document. Redact them in findings.
- Prefer a **local** transport. A cloud-polling integration that depends on Mahlkönig's servers is a fragile last resort — say so if that's all that's available.

---

## 7. Deliverables

1. **Findings document** — what the transport is, what fields are actually available, what is *not* available, and how you proved each claim. Negative results stated as plainly as positive ones.
2. **A minimal working proof** — a script that connects and prints one real grind event. This is the acceptance test.
3. **An integration path** — whichever fits: custom HA component, MQTT bridge, or an ESPHome BLE client (note: the coffee-knob is an ESP32-S3 with BLE already sitting next to the machine, so `esp32_ble_tracker` / `ble_client` on that device is a legitimate option worth considering).
4. **A blunt verdict** if it can't be done, with the evidence that closes the question.

---

## 8. Open questions for Tomer — ask before starting

1. **Which grinder, exactly?** (Model + rough age. This determines everything.)
2. Is it currently paired to the Mahlkönig Home app, and does the app show you dose/grind history today? If the app can't see it, neither can we.
3. Do you own the **Sync Scale**, or any Bluetooth coffee scale (Acaia, Bookoo, Timemore)?
4. Is there an **Android** phone/tablet available, or is it iPhone only?
5. Is the grinder on Wi-Fi at all, or Bluetooth only?

---

## 9. Where to hand back

The consumer is the `coffee-knob` ESPHome device and Home Assistant. Existing helpers already created and currently unused:

```
input_select.coffee_current_beans
input_number.coffee_dose
input_number.coffee_yield
input_number.coffee_grind_setting
input_number.coffee_shot_rating
input_datetime.coffee_roast_date
input_text.coffee_shot_notes
```

If you produce real grinder entities, those `input_number` helpers become redundant for dose and grind setting — which is the entire point of this task.
