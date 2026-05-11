#pragma once

// ============================================================================
// SECRETS TEMPLATE
//
// Copy this file to `secrets.h` (in the same folder) and fill in your real
// values. The real secrets.h is gitignored so credentials never get pushed
// to GitHub.
// ============================================================================

// ----- Wi-Fi -----
#define WIFI_SSID       "YOUR_WIFI_NAME"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

// ----- HiveMQ Cloud MQTT broker -----
// Get these from your HiveMQ Cloud cluster page.
#define MQTT_HOST       "60bec8cfeab54dfe8a35e109dc2cb4f8.s1.eu.hivemq.cloud"
#define MQTT_PORT       8883
#define MQTT_USER       "braille-publisher"
#define MQTT_PASS       "YOUR_HIVEMQ_PASSWORD"

// ----- Topic the ESP32 subscribes to -----
#define MQTT_TOPIC      "braille/letter"

// ----- Unique client ID for this device on the broker -----
// Must be different from the backend's client ID ('braille-backend').
#define MQTT_CLIENT_ID  "braille-esp32-01"
