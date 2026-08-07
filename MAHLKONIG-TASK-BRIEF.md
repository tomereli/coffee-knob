# Build a Home Assistant integration for the Mahlkönig grinder

**For:** Faibel
**From:** the Coffee Knob project (Opus)
**Owner:** Tomer

---

## 1. What this is

Tomer owns a Mahlkönig grinder and a Mahlkönig account. The official app already shows him his own grind data. He wants that same data in his own Home Assistant instance instead of only in the app.

This is ordinary home-automation integration work — the same category as the **La Marzocco** integration already running in this system, and as the hundreds of community Home Assistant integrations for consumer appliances. His hardware, his account, his data, his LAN.

**Nothing here involves other people's accounts or data.**

---

## 2. Why it matters

A working ESP32-S3 knob display (`coffee-knob`, ESPHome → Home Assistant) already shows La Marzocco Micra state, controls the machine, and runs a live shot timer. The machine side is solved.

The grinder side is not. To log a shot properly you want dose, grind setting and grind time. Today the only way to record those is to type them into `input_number` helpers by hand, which Tomer has ruled out — fairly. So either the grinder can publish its data, or shot logging stays a toy.

---

## 3. Goal

Per grind event, whichever of these actually exist:

- dose weight (g) — the valuable one
- grind setting / micron value
- grind duration
- timestamp
- model / firmware / serial

Landing zone: Home Assistant entities. **A local connection is strongly preferred over a cloud one.**

A well-evidenced *"this model does not expose that data"* is a perfectly good result. Don't invent one.

---

## 4. Start here — existing work, don't redo it

| Resource | Why |
|---|---|
| [`kevinschweikert/ha-mahlkoenig`](https://github.com/kevinschweikert/ha-mahlkoenig) | An existing open-source Home Assistant integration for the **Mahlkönig X54**. Highest-value lead by far. Read the source and see what transport it uses — it appears to talk to the grinder over the local network. If Tomer's grinder is an X54 or shares firmware, this may already be the answer. |
| [Mahlkönig Home app](https://apps.apple.com/us/app/mahlk%C3%B6nig-home/id1641868454) | The official app. Whatever it can display is data the account has access to. |
| [The Sync System](https://www.mahlkoenig.com/products/the-sync-system) / [Sync Scale](https://www.mahlkoenig.com/products/mahlkonig-sync-scale) | Mahlkönig's connected grinding ecosystem, Bluetooth-based. **The Sync Scale is probably the actual source of dose weight** — many grinders don't weigh anything themselves. Settle early whether dose data can exist at all without this scale, because it changes the whole plan. |
| [Grind-by-Sync quick start (PDF)](https://downloads.mahlkoenig.de/Service/Quick_Start_Guide_Mahlkoenig_Grind_by_Sync_Espresso_Grinder.pdf) | Vendor documentation of the grinder↔scale pairing. Good for understanding how the pieces talk. |

---

## 5. Routes, in the order worth trying

### Route 0 — Identify the hardware (do this first)
Exact model, firmware version, and what radios it has. A good share of grinders in this range have no connectivity at all. Establish this before spending time on anything else.

### Route 1 — Local network or Bluetooth (best outcome)
Many connected appliances expose a small local HTTP or WebSocket service, or a Bluetooth GATT service, that the app talks to directly when you're on the same network.

- Is the grinder on the LAN? Browse mDNS/SSDP, then look at what ports it answers on.
- Bluetooth: scan with `bleak` or nRF Connect, list the GATT services and characteristics, subscribe to notifications and grind a dose to see what changes.

If this works you get a clean, offline, dependency-free integration. Best possible result.

### Route 2 — The existing X54 integration
If the model matches, install it and see what it reports. Possibly the whole job.

### Route 3 — The account API the app already uses
If the grinder only talks to Mahlkönig's cloud, then the integration reads Tomer's own account through the same API the app uses, with his own credentials — the standard pattern for cloud-connected appliance integrations in Home Assistant.

To learn the API shape, observe the app's own requests on a network Tomer controls (e.g. `mitmproxy` on the Windows PC, phone pointed at it). If the app pins its certificates, this route is closed — note that and move on rather than trying to defeat it; Routes 1 and 4 are better uses of the time anyway.

Keep any cloud polling to roughly what the app itself does. No aggressive request rates.

### Route 4 — Run the official Android app on the Windows PC (Tomer's suggestion)
Run the Android build of the Mahlkönig app in an emulator (Android Studio's AVD, Waydroid, BlueStacks) on the Windows machine, signed in as Tomer, and bridge what it receives into Home Assistant via MQTT or the HA REST API.

Worth noting honestly: **this is the most brittle option.** It needs a machine powered on permanently, it breaks on app updates, and getting data *out* of a running app is awkward. Treat it as the fallback if Routes 1–3 fail — but it is a legitimate option and Tomer specifically wants it considered.

One correction to save time: **an iPhone app cannot be run on a PC.** The iOS Simulator doesn't run App Store builds. If this route is taken it has to be the Android app.

### Route 5 — Read the app's own code
Public app packages can be inspected to find the endpoints and identifiers they use. Standard practice when documenting an undocumented consumer API, and often faster than watching traffic once you know what to look for.

---

## 6. Ground rules

- Tomer's own grinder, his own account, his own network. He can supply his app login.
- Only his own data. Nothing that touches other users' accounts or devices.
- Keep credentials and tokens out of the repo and out of the findings document — redact them.
- Prefer local. A cloud-polling integration is a fragile last resort; say so plainly if it's all that's available.

---

## 7. Deliverables

1. **Findings document** — the transport, which fields are genuinely available, which are not, and the evidence for each claim. Negative results stated as clearly as positive ones.
2. **A minimal working proof** — a script that connects and prints one real grind event. This is the acceptance test.
3. **An integration path** — custom HA component, MQTT bridge, or an ESPHome BLE client. Note: the coffee-knob is an ESP32-S3 with Bluetooth already sitting next to the machine, so `ble_client` on that device is a genuinely good option if the grinder or scale is Bluetooth.
4. **A clear verdict** if it can't be done, with the evidence that closes the question.

---

## 8. Questions for Tomer before starting

1. **Which grinder, exactly?** Model and rough age. This determines everything.
2. Is it paired to the Mahlkönig Home app now, and does the app show dose/grind history today? If the app can't see it, nothing downstream can.
3. Do you own the **Sync Scale**, or any Bluetooth coffee scale (Acaia, Bookoo, Timemore)?
4. Is an **Android** device or emulator available, or iPhone only?
5. Is the grinder on Wi-Fi, Bluetooth, or neither?

---

## 9. Where this plugs in

The consumer is the `coffee-knob` ESPHome device and Home Assistant. These helpers already exist and are currently filled in by hand:

```
input_select.coffee_current_beans
input_number.coffee_dose
input_number.coffee_yield
input_number.coffee_grind_setting
input_number.coffee_shot_rating
input_datetime.coffee_roast_date
input_text.coffee_shot_notes
```

Real grinder entities would make the dose and grind-setting helpers unnecessary — which is the entire point of this task.
