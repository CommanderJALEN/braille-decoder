# BrailleDecoder — Hardware Bill of Materials

Updated for: perfboard build, 330Ω resistors already on hand.

## Core Components (Required)

| # | Component | Qty | Purpose | Approx. Price (PHP) |
|---|-----------|-----|---------|---------------------|
| 1 | ESP32 Dev Board (ESP32-WROOM-32, 38-pin) | 1 | Main microcontroller — handles WiFi, MQTT, drives LEDs and OLED | ₱250–400 |
| 2 | SSD1306 0.96" OLED Display (I2C, 128×64) — **with pre-soldered headers** | 1 | Displays the decoded letter | ₱150–250 |
| 3 | LEDs (3mm or 5mm, 3V forward voltage) | 6 | The 6 Braille dots | ₱30–60 total |
| 4 | ~~220Ω Resistors~~ → **330Ω Resistors** | 6 | LED current limiting | ✅ Already on hand |
| 5 | Perfboard / Stripboard (5×7 cm or 7×9 cm) | 2 | Permanent build surface (buy 2 — first one may have mistakes) | ₱60–160 total |
| 6 | Female header pins (40-pin strip, 2.54mm) | 1 strip | Sockets for ESP32 and OLED so they're removable | ₱30–50 |
| 7 | Solid-core hookup wire (22 AWG, multiple colors) | small spool / assorted pack | Point-to-point wiring on the back of the perfboard | ₱100–200 |
| 8 | Solder (60/40 rosin core, 0.8mm) | small roll | Holds the connections | ₱100–200 |
| 9 | Soldering iron (25–40W with stand) | 1 | For all soldering work | ₱400–800 (skip if already owned) |
| 10 | USB Cable (Micro-USB or USB-C — match your ESP32 board) | 1 | Power + flashing firmware | ₱50–150 (skip if already owned) |

## Strongly Recommended Add-Ons

| Component | Why | Approx. Price (PHP) |
|-----------|-----|---------------------|
| Small breadboard (400 tie-points) + M-M jumper wires (40pcs) | **Prototype the wiring before soldering.** Saves hours of fixing soldered mistakes. | ₱150–300 |
| Solder sucker / desoldering pump | Undo mistakes when (not if) they happen | ₱100–200 |
| Multimeter | Continuity check before powering up — catches shorts | ₱200–500 |

## Optional (Helpful but Skippable)

| Component | Why |
|-----------|-----|
| Helping hands / PCB holder | Holds perfboard while you solder |
| Flux paste | Makes solder flow cleaner |
| Power bank or 5V USB adapter | Run untethered during demos |

## What You DON'T Need

- ❌ No buttons or switches — voice handles input
- ❌ No microphone module — Google Assistant on phone handles voice input
- ❌ No speaker / amplifier — Google Assistant talks back through phone
- ❌ No SD card module — Braille mapping is hardcoded
- ❌ No external power supply — USB power is enough for 6 LEDs + OLED
- ❌ No 220Ω resistors — your 330Ω resistors work fine

## Notes

**On 330Ω resistors:** ESP32 GPIO outputs ~3.3V. With a 330Ω resistor, red/yellow LEDs draw ~4mA, blue/white/green draw ~1mA. All safe and visible. No code changes needed.

**On the OLED:** Always look for "pre-soldered headers" in the listing. Otherwise you'll need to solder header pins to the OLED yourself before it can plug into anything.

**On ESP32 variant:** Get an "ESP32 DEVKIT V1" or "NodeMCU-32S" — 38-pin breakout boards. Avoid ESP32-CAM (camera not needed) and ESP32-C3 mini (harder to wire).

## Where to Buy (Philippines)

**Online (easiest for Calamba):**
- **Lazada / Shopee** — search "ESP32 DEVKIT V1 38 pin", "0.96 OLED I2C 128x64", "perfboard", etc.
- Look for sellers with high ratings; consolidate orders to save shipping
- Search "ESP32 starter kit" — bundles often save money

**Physical stores (if traveling to Manila/QC):**
- Makerlab Electronics
- e-Gizmo
- Alexan

## Budget Summary

| Scenario | Estimated Cost |
|----------|----------------|
| Have iron, solder, USB cable already | ₱700–1,000 |
| Buying everything fresh including soldering iron | ₱1,500–2,200 |
| Comfortable build with breadboard + multimeter + extras | ₱2,500–3,500 |

## Recommended Build Order

1. Wire everything on breadboard first — prove firmware and connections work
2. Plan perfboard layout on paper (Braille cell spacing: ~6mm horizontal, ~10mm vertical between dots)
3. Solder female headers first (ESP32 + OLED sockets)
4. Solder LEDs in 2×3 Braille grid
5. Solder 330Ω resistors between LEDs and ground rail
6. Run hookup wires on the back to ESP32 GPIO pins
7. Continuity-test with multimeter
8. Plug in ESP32 → power up → demo
