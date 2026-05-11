/*
 * ============================================================================
 * BrailleDecoder ESP32 Firmware
 * ============================================================================
 *
 * Subscribes to an MQTT topic on HiveMQ Cloud. Whenever a letter arrives,
 * lights up the corresponding Braille dot pattern on 6 LEDs and displays
 * the letter on the SSD1306 OLED.
 *
 * Standard Braille dot positions (viewed from the front of the cell):
 *
 *      Dot 1  ●   ●  Dot 4
 *      Dot 2  ●   ●  Dot 5
 *      Dot 3  ●   ●  Dot 6
 *
 * Bits in the letter map: bit 0 = dot 1, bit 1 = dot 2, ..., bit 5 = dot 6.
 *
 * Pin assignments (see HARDWARE.md for full wiring).
 * All LED pins are non-strapping, non-input-only, safe for output.
 *   Dot 1 -> GPIO 13       OLED SDA -> GPIO 21
 *   Dot 2 -> GPIO 14       OLED SCL -> GPIO 22
 *   Dot 3 -> GPIO 27       OLED VCC -> 3.3V
 *   Dot 4 -> GPIO 26       OLED GND -> GND
 *   Dot 5 -> GPIO 25
 *   Dot 6 -> GPIO 33
 *
 * Build with PlatformIO. Before uploading, copy `secrets.example.h` to
 * `secrets.h` and fill in your Wi-Fi and HiveMQ credentials.
 * ============================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "secrets.h"

// ----------------------------------------------------------------------------
// Pin map
// ----------------------------------------------------------------------------
// Index 0 = dot 1, index 1 = dot 2, ..., index 5 = dot 6
// All chosen pins are non-strapping and safe for output.
const uint8_t LED_PINS[6] = {13, 14, 27, 26, 25, 33};

// OLED config (SSD1306 128x64 over I2C, default address 0x3C)
#define OLED_WIDTH    128
#define OLED_HEIGHT   64
#define OLED_RESET    -1
#define OLED_ADDRESS  0x3C

// How long each letter stays lit before clearing (ms)
const unsigned long LETTER_DISPLAY_MS = 4000;

// ----------------------------------------------------------------------------
// Globals
// ----------------------------------------------------------------------------
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);
WiFiClientSecure wifiClient;
PubSubClient mqtt(wifiClient);

unsigned long letterShownAt = 0;     // when the current letter was lit
bool letterIsActive = false;          // are LEDs currently showing a letter?
char currentLetter = ' ';             // letter currently displayed

// ----------------------------------------------------------------------------
// Braille alphabet
// Each entry is a 6-bit mask: bit 0 = dot 1, bit 1 = dot 2, ..., bit 5 = dot 6
// ----------------------------------------------------------------------------
const uint8_t BRAILLE_TABLE[26] = {
  0b000001,  // A = dot 1
  0b000011,  // B = dots 1,2
  0b001001,  // C = dots 1,4
  0b011001,  // D = dots 1,4,5
  0b010001,  // E = dots 1,5
  0b001011,  // F = dots 1,2,4
  0b011011,  // G = dots 1,2,4,5
  0b010011,  // H = dots 1,2,5
  0b001010,  // I = dots 2,4
  0b011010,  // J = dots 2,4,5
  0b000101,  // K = dots 1,3
  0b000111,  // L = dots 1,2,3
  0b001101,  // M = dots 1,3,4
  0b011101,  // N = dots 1,3,4,5
  0b010101,  // O = dots 1,3,5
  0b001111,  // P = dots 1,2,3,4
  0b011111,  // Q = dots 1,2,3,4,5
  0b010111,  // R = dots 1,2,3,5
  0b001110,  // S = dots 2,3,4
  0b011110,  // T = dots 2,3,4,5
  0b100101,  // U = dots 1,3,6
  0b100111,  // V = dots 1,2,3,6
  0b111010,  // W = dots 2,4,5,6
  0b101101,  // X = dots 1,3,4,6
  0b111101,  // Y = dots 1,3,4,5,6
  0b110101   // Z = dots 1,3,5,6
};

// ----------------------------------------------------------------------------
// OLED helpers
// ----------------------------------------------------------------------------
void oledShowMessage(const char* line1, const char* line2 = nullptr) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(line1);
  if (line2) {
    display.setCursor(0, 16);
    display.println(line2);
  }
  display.display();
}

void oledShowLetter(char letter) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Small label up top
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("BrailleDecoder");

  // Large letter centered
  display.setTextSize(6);
  // Each text-size-1 char is 6x8 px; size 6 makes it 36x48 px
  int16_t x = (OLED_WIDTH - 36) / 2;
  int16_t y = (OLED_HEIGHT - 48) / 2 + 4;
  display.setCursor(x, y);
  display.print(letter);

  display.display();
}

void oledShowReady() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(20, 12);
  display.println("Ready");
  display.setTextSize(1);
  display.setCursor(10, 44);
  display.println("Say a letter on");
  display.setCursor(20, 54);
  display.println("the voice page");
  display.display();
}

// ----------------------------------------------------------------------------
// LED helpers
// ----------------------------------------------------------------------------
void clearAllLeds() {
  for (int i = 0; i < 6; i++) {
    digitalWrite(LED_PINS[i], LOW);
  }
}

void showBraillePattern(uint8_t pattern) {
  for (int i = 0; i < 6; i++) {
    bool on = (pattern >> i) & 0x01;
    digitalWrite(LED_PINS[i], on ? HIGH : LOW);
  }
}

void startupBlink() {
  // Sweep through each LED once so you can verify wiring
  for (int i = 0; i < 6; i++) {
    digitalWrite(LED_PINS[i], HIGH);
    delay(120);
    digitalWrite(LED_PINS[i], LOW);
  }
  // All on briefly, then all off
  for (int i = 0; i < 6; i++) digitalWrite(LED_PINS[i], HIGH);
  delay(300);
  clearAllLeds();
}

// ----------------------------------------------------------------------------
// Letter handling
// ----------------------------------------------------------------------------
void displayLetter(char letter) {
  // Normalise to uppercase A-Z
  if (letter >= 'a' && letter <= 'z') letter = letter - 'a' + 'A';
  if (letter < 'A' || letter > 'Z') {
    Serial.printf("Ignoring non-letter: '%c'\n", letter);
    return;
  }

  uint8_t pattern = BRAILLE_TABLE[letter - 'A'];
  Serial.printf("Letter '%c' -> pattern 0b%c%c%c%c%c%c\n",
                letter,
                (pattern & 0x20) ? '1' : '0',
                (pattern & 0x10) ? '1' : '0',
                (pattern & 0x08) ? '1' : '0',
                (pattern & 0x04) ? '1' : '0',
                (pattern & 0x02) ? '1' : '0',
                (pattern & 0x01) ? '1' : '0');

  showBraillePattern(pattern);
  oledShowLetter(letter);
  currentLetter = letter;
  letterShownAt = millis();
  letterIsActive = true;
}

// ----------------------------------------------------------------------------
// MQTT
// ----------------------------------------------------------------------------
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  if (length == 0) return;

  // Print full payload for debugging
  Serial.printf("MQTT message on '%s' (%u bytes): ", topic, length);
  for (unsigned int i = 0; i < length; i++) Serial.print((char)payload[i]);
  Serial.println();

  // We only care about the first character of the payload
  // (the backend publishes one letter at a time)
  char letter = (char)payload[0];
  displayLetter(letter);
}

void connectMqtt() {
  while (!mqtt.connected()) {
    Serial.print("Connecting to MQTT broker... ");
    oledShowMessage("Connecting to", "MQTT broker...");
    if (mqtt.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS)) {
      Serial.println("connected");
      mqtt.subscribe(MQTT_TOPIC);
      Serial.printf("Subscribed to %s\n", MQTT_TOPIC);
      oledShowReady();
    } else {
      Serial.printf("failed, rc=%d. Retrying in 3s\n", mqtt.state());
      delay(3000);
    }
  }
}

// ----------------------------------------------------------------------------
// Wi-Fi
// ----------------------------------------------------------------------------
void connectWifi() {
  Serial.printf("Connecting to Wi-Fi '%s'...\n", WIFI_SSID);
  oledShowMessage("Connecting WiFi", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (++dots > 60) {  // 30 s timeout, then reboot to retry
      Serial.println("\nWi-Fi timeout, restarting...");
      ESP.restart();
    }
  }
  Serial.printf("\nConnected. IP: %s\n", WiFi.localIP().toString().c_str());
}

// ----------------------------------------------------------------------------
// Setup & loop
// ----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== BrailleDecoder ESP32 starting ===");

  // LED pins
  for (int i = 0; i < 6; i++) {
    pinMode(LED_PINS[i], OUTPUT);
    digitalWrite(LED_PINS[i], LOW);
  }

  // OLED
  Wire.begin(21, 22);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("OLED init failed — check wiring at SDA=21, SCL=22");
    // Don't halt; keep going so LEDs still work
  } else {
    display.clearDisplay();
    display.display();
  }

  // Startup self-test: blink each LED
  startupBlink();

  // Network
  connectWifi();

  // For HiveMQ Cloud (TLS on 8883). setInsecure() skips cert verification —
  // acceptable for this project. For production-grade security you'd load
  // the HiveMQ root CA into wifiClient.setCACert(...) instead.
  wifiClient.setInsecure();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(256);

  connectMqtt();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }
  if (!mqtt.connected()) {
    connectMqtt();
  }
  mqtt.loop();

  // Auto-clear LEDs and OLED after the display timeout so the device
  // returns to a 'Ready' state between letters.
  if (letterIsActive && (millis() - letterShownAt) > LETTER_DISPLAY_MS) {
    clearAllLeds();
    oledShowReady();
    letterIsActive = false;
  }
}
