"""
BrailleDecoder backend.

Receives a letter via webhook (from IFTTT/Google Assistant) and
publishes each character to an MQTT broker (HiveMQ Cloud).
The ESP32 subscribes to the same topic and lights up the
corresponding Braille dot pattern on its 6 LEDs.
"""

import os
import ssl
import time
import logging
import threading
from contextlib import asynccontextmanager

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("braille-decoder")

# ---------------------------------------------------------------------------
# Configuration (loaded from Railway environment variables)
# ---------------------------------------------------------------------------
IFTTT_SECRET = os.getenv("IFTTT_SECRET", "dev-secret-change-me")

MQTT_HOST = os.getenv("MQTT_HOST", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "braille/letter")

# Delay between letters when a whole word comes in (seconds)
LETTER_DELAY_SECONDS = float(os.getenv("LETTER_DELAY_SECONDS", "1.5"))


# ---------------------------------------------------------------------------
# MQTT client (single shared connection, kept alive in background)
# ---------------------------------------------------------------------------
mqtt_client: mqtt.Client | None = None


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to MQTT broker")
    else:
        logger.error(f"MQTT connection failed with code {rc}")


def on_mqtt_disconnect(client, userdata, rc, properties=None, reason_code=None):
    logger.warning(f"Disconnected from MQTT broker (rc={rc})")


def init_mqtt() -> mqtt.Client:
    """Create, configure, and start the MQTT client."""
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="braille-backend",
    )
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    # HiveMQ Cloud requires TLS on port 8883
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect

    if not MQTT_HOST:
        logger.warning("MQTT_HOST not set — MQTT disabled")
        return client

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()  # background thread keeps connection alive
        logger.info(f"MQTT loop started, target {MQTT_HOST}:{MQTT_PORT}")
    except Exception as exc:
        logger.error(f"Failed to connect to MQTT: {exc}")

    return client


# ---------------------------------------------------------------------------
# FastAPI app with lifespan to manage the MQTT connection
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global mqtt_client
    mqtt_client = init_mqtt()
    yield
    if mqtt_client is not None:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


app = FastAPI(title="BrailleDecoder Backend", lifespan=lifespan)


class LetterPayload(BaseModel):
    letter: str = Field(..., min_length=1, max_length=20)


@app.get("/")
def root():
    return {"status": "BrailleDecoder backend is running"}


@app.get("/health")
def health():
    connected = bool(mqtt_client and mqtt_client.is_connected())
    return {"status": "ok", "mqtt_connected": connected}


def publish_letters_async(text: str) -> None:
    """Publish letters one at a time on a background thread, with a delay
    between each so the ESP32 has time to display them before the next one."""

    def _worker():
        for char in text:
            if mqtt_client and mqtt_client.is_connected():
                result = mqtt_client.publish(MQTT_TOPIC, char, qos=1)
                logger.info(f"Published '{char}' to {MQTT_TOPIC} (mid={result.mid})")
            else:
                logger.error(f"MQTT not connected — could not publish '{char}'")
            if len(text) > 1:
                time.sleep(LETTER_DELAY_SECONDS)

    threading.Thread(target=_worker, daemon=True).start()


@app.post("/webhook/letter")
def receive_letter(
    payload: LetterPayload,
    x_ifttt_secret: str | None = Header(default=None),
):
    if x_ifttt_secret != IFTTT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    text = payload.letter.strip().upper()

    if not text.isalpha():
        raise HTTPException(
            status_code=400,
            detail="Letter must contain only alphabetic characters",
        )

    logger.info(f"Received letter(s): {text}")
    publish_letters_async(text)

    return {
        "received": text,
        "length": len(text),
        "published_to": MQTT_TOPIC,
    }
