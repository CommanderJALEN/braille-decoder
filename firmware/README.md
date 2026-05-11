# BrailleDecoder Firmware

ESP32 C++ firmware that subscribes to the HiveMQ MQTT broker and lights up
the 6 Braille LEDs + OLED whenever a letter arrives from the cloud backend.

## What This Does

1. Connects to Wi-Fi
2. Connects to HiveMQ Cloud over TLS (port 8883)
3. Subscribes to topic `braille/letter`
4. When a letter arrives, looks up its 6-bit Braille pattern, lights up
   matching LEDs, and shows the letter big on the OLED
5. After 4 seconds, clears LEDs and shows "Ready" again

## Hardware

See **../HARDWARE.md** for the full bill of materials, wiring diagram,
and build notes.

### Pin Map

All LED pins below are **non-strapping, output-safe** ESP32 pins.

| ESP32 Pin | Component        | Notes                   |
|-----------|------------------|-------------------------|
| GPIO 13   | Dot 1 (top-left) | LED → 330 Ω → GND       |
| GPIO 14   | Dot 2 (mid-left) | LED → 330 Ω → GND       |
| GPIO 27   | Dot 3 (bot-left) | LED → 330 Ω → GND       |
| GPIO 26   | Dot 4 (top-right)| LED → 330 Ω → GND       |
| GPIO 25   | Dot 5 (mid-right)| LED → 330 Ω → GND       |
| GPIO 33   | Dot 6 (bot-right)| LED → 330 Ω → GND       |
| GPIO 21   | OLED SDA         | I2C data (default)      |
| GPIO 22   | OLED SCL         | I2C clock (default)     |
| 3.3V      | OLED VCC         |                         |
| GND       | OLED GND + LED ground rail |               |

## Build & Upload

You need **PlatformIO**. Easiest setup: install the
[PlatformIO IDE extension for VS Code](https://platformio.org/install/ide?install=vscode).

### One-Time Setup

1. Copy `src/secrets.example.h` to `src/secrets.h`
2. Edit `src/secrets.h` and fill in:
   - Your Wi-Fi SSID and password
   - Your HiveMQ password (the `MQTT_HOST` and `MQTT_USER` are already set)
3. `secrets.h` is gitignored — your credentials will never be pushed

### Build & Flash

With the ESP32 plugged in via USB:

```bash
cd firmware
pio run                       # compile
pio run --target upload       # flash to ESP32
pio device monitor            # watch serial output (115200 baud)
```

Or from the PlatformIO toolbar in VS Code: click the **→ (Upload)** button,
then the **🔌 (Serial Monitor)** button.

### What You Should See on Boot

1. LEDs sweep one at a time, then all flash briefly (self-test)
2. OLED: "Connecting WiFi..."
3. OLED: "Connecting to MQTT broker..."
4. OLED: "Ready" — device is online and listening
5. Serial monitor prints the device's IP and "Subscribed to braille/letter"

Then speak a letter on the voice page — within a second the matching
LEDs should light up and the letter should appear on the OLED.

## Troubleshooting

**LEDs don't light up at all during the startup self-test**
- Check that each LED's long leg (anode) is on the GPIO side, short leg (cathode) is on the ground side
- Verify 330 Ω resistors are in series with each LED
- Confirm the GPIO numbers match the pin map above

**OLED stays dark**
- Verify SDA=21, SCL=22 (these are the ESP32's default I2C pins)
- Some OLED modules use address 0x3D instead of 0x3C — change `OLED_ADDRESS` in `main.cpp` if needed
- Check 3.3V (NOT 5V) and GND are connected

**"Wi-Fi timeout, restarting..."**
- Wrong SSID or password in `secrets.h`
- 5 GHz network — ESP32 only supports 2.4 GHz

**"MQTT failed, rc=-2" or rc=4**
- Wrong HiveMQ password
- Wrong cluster URL
- Make sure your `MQTT_CLIENT_ID` is unique (the backend uses `braille-backend`,
  so the ESP32 must be something different like `braille-esp32-01`)

**Wrong letter lights up / wrong pattern**
- Check the physical placement of LEDs against the dot layout in `main.cpp`:
  ```
   Dot 1 (GPIO 13)    Dot 4 (GPIO 26)
   Dot 2 (GPIO 14)    Dot 5 (GPIO 25)
   Dot 3 (GPIO 27)    Dot 6 (GPIO 33)
  ```

## How to Test Without Voice

If you want to test the firmware without speaking, use the HiveMQ Web Client
to publish a letter directly:

1. Open your HiveMQ cluster → **Web Client** tab → connect
2. Publish to topic `braille/letter` with payload `A` (or any letter)
3. The ESP32 should light up the matching pattern within a second
