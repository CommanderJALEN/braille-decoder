"""
BrailleDecoder backend.
Receives a letter via webhook (from IFTTT/Google Assistant)
and will eventually forward it to the ESP32 over MQTT.

For now, this is the minimal version: just receives + logs.
We'll add MQTT in the next step once Railway is confirmed working.
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("braille-decoder")

app = FastAPI(title="BrailleDecoder Backend")

# Read secret from environment variable (set in Railway dashboard).
# If the env var isn't set, fall back to a dev value so local testing works.
IFTTT_SECRET = os.getenv("IFTTT_SECRET", "dev-secret-change-me")


class LetterPayload(BaseModel):
    letter: str = Field(..., min_length=1, max_length=20)


@app.get("/")
def root():
    return {"status": "BrailleDecoder backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook/letter")
def receive_letter(
    payload: LetterPayload,
    x_ifttt_secret: str | None = Header(default=None),
):
    # Reject anyone who doesn't know the secret.
    if x_ifttt_secret != IFTTT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    # Normalise: uppercase, strip whitespace.
    text = payload.letter.strip().upper()

    if not text.isalpha():
        raise HTTPException(
            status_code=400,
            detail="Letter must contain only alphabetic characters",
        )

    logger.info(f"Received letter(s): {text}")

    # TODO (next step): publish each character to MQTT topic 'braille/letter'
    # so the ESP32 can light up the corresponding dots.

    return {"received": text, "length": len(text)}
