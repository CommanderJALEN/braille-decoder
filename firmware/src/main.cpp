/*
 * ============================================================================
 * BrailleDecoder ESP32 Firmware  —  128x32 OLED + U8g2 library
 * ============================================================================
 *
 * Uses U8g2 library (same one that worked in Arduino IDE).
 *
 * Pin assignments:
 *   Dot 1 -> GPIO 13       OLED SDA -> GPIO 21
 *   Dot 2 -> GPIO 14       OLED SCK -> GPIO 22
 *   Dot 3 -> GPIO 27       OLED VCC -> 3.3V
 *   Dot 4 -> GPIO 26       OLED GND -> GND
 *   Dot 5 -> GPIO 25
 *   Dot 6 -> GPIO 33
 * ============================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <U8g2lib.h>

#include "secrets.h"

// ----------------------------------------------------------------------------
// OLED setup — 128x32 with U8g2 hardware I2C
// Constructor params: (rotation, reset_pin, scl_pin, sda_pin)
// ----------------------------------------------------------------------------
U8G2_SSD1306_128X32_UNIVISION_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE, 22, 21);

// ----------------------------------------------------------------------------
// LED pin map (index 0 = dot 1, ..., index 5 = dot 6)
// ----------------------------------------------------------------------------
const uint8_t LED_PINS[6] = {13, 14, 27, 26, 25, 33};

// How long each letter stays lit before clearing (ms)
const unsigned long LETTER_DISPLAY_MS = 4000;

// ----------------------------------------------------------------------------
// Globals
// ----------------------------------------------------------------------------
WiFiClientSecure wifiClient;
PubSubClient mqtt(wifiClient);

unsigned long letterShownAt = 0;
bool letterIsActive = false;
char currentLetter = ' ';

// ----------------------------------------------------------------------------
// Braille alphabet (6-bit masks: bit 0 = dot 1, ..., bit 5 = dot 6)
// ----------------------------------------------------------------------------
const uint8_t BRAILLE_TABLE[26] = {
  0b000001, 0b000011, 0b001001, 0b011001, 0b010001,  // A B C D E
  0b001011, 0b011011, 0b010011, 0b001010, 0b011010,  // F G H I J
  0b000101, 0b000111, 0b001101, 0b011101, 0b010101,  // K L M N O
  0b001111, 0b011111, 0b010111, 0b001110, 0b011110,  // P Q R S T
  0b100101, 0b100111, 0b111010, 0b101101, 0b111101,  // U V W X Y
  0b110101                                             // Z
};

// ----------------------------------------------------------------------------
// OLED helpers (U8g2 API)
// ----------------------------------------------------------------------------
void oledShowMessage(const char* line1, const char* line2 = nullptr) {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tf);
  u8g2.drawStr(0, 12, line1);
  if (line2) {
    u8g2.drawStr(0, 28, line2);
  }
  u8g2.sendBuffer();
}

void oledShowLetter(char letter) {
  u8g2.clearBuffer();

  // Small labels on the left
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(0, 12, "Braille");
  u8g2.drawStr(0, 28, "Letter:");

  // Big letter on the right
  u8g2.setFont(u8g2_font_logisoso28_tr);
  char buf[2] = {letter, '\0'};
  u8g2.drawStr(95, 30, buf);

  u8g2.sendBuffer();
}

void oledShowReady() {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_10x20_tf);
  u8g2.drawStr(0, 16, "Ready");
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(0, 30, "Say a letter...");
  u8g2.sendBuffer();
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
  for (int i = 0; i < 6; i++) {
    digitalWrite(LED_PINS[i], HIGH);
    delay(120);
    digitalWrite(LED_PINS[i], LOW);
  }
  for (int i = 0; i < 6; i++) digitalWrite(LED_PINS[i], HIGH);
  delay(300);
  clearAllLeds();
}

// ----------------------------------------------------------------------------
// Letter handling
// ----------------------------------------------------------------------------
void displayLetter(char letter) {
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

  Serial.printf("MQTT message on '%s' (%u bytes): ", topic, length);
  for (unsigned int i = 0; i < length; i++) Serial.print((char)payload[i]);
  Serial.println();

  char letter = (char)payload[0];
  displayLetter(letter);
}

void connectMqtt() {
  while (!mqtt.connected()) {
    Serial.print("Connecting to MQTT broker... ");
    oledShowMessage("Connecting", "MQTT broker...");
    if (mqtt.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS)) {
      Serial.println("connected");
      mqtt.subscribe(MQTT_TOPIC);
      Serial.printf("Subscribed to %s\n", MQTT_TOPIC);
      oledShowReady();
    } else {
      Serial.printf("failed, rc=%d. Retrying in 3s\n", mqtt.state());
      oledShowMessage("MQTT failed", "Retrying...");
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
    if (++dots > 60) {
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
  Serial.println("\n=== BrailleDecoder ESP32 starting (U8g2 build) ===");

  // LED pins
  for (int i = 0; i < 6; i++) {
    pinMode(LED_PINS[i], OUTPUT);
    digitalWrite(LED_PINS[i], LOW);
  }

  // OLED init via U8g2 (handles Wire.begin internally)
  Serial.println("Initializing OLED...");
  if (u8g2.begin()) {
    Serial.println("OLED OK");
  } else {
    Serial.println("OLED init returned false (might still work)");
  }

  // Show "Booting" so we can SEE that OLED is working
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_10x20_tf);
  u8g2.drawStr(0, 16, "Booting");
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(0, 30, "BrailleDecoder");
  u8g2.sendBuffer();
  delay(2000);  // 2 seconds so you can clearly see it

  // LED self-test
  startupBlink();

  // Network
  connectWifi();

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

  // Auto-clear LEDs and OLED after timeout
  if (letterIsActive && (millis() - letterShownAt) > LETTER_DISPLAY_MS) {
    clearAllLeds();
    oledShowReady();
    letterIsActive = false;
  }
}