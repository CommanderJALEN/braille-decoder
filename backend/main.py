"""
BrailleDecoder backend.

Receives a letter via webhook and publishes each character to an
MQTT broker (HiveMQ Cloud). The ESP32 subscribes to the same topic
and lights up the corresponding Braille dot pattern.

Also serves a voice-input web page at /voice that lets users speak
letters into their phone or laptop browser using browser speech AI.
"""

import os
import ssl
import time
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
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

LETTER_DELAY_SECONDS = float(os.getenv("LETTER_DELAY_SECONDS", "1.5"))


# ---------------------------------------------------------------------------
# MQTT client
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
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="braille-backend",
    )
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect

    if not MQTT_HOST:
        logger.warning("MQTT_HOST not set — MQTT disabled")
        return client

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        logger.info(f"MQTT loop started, target {MQTT_HOST}:{MQTT_PORT}")
    except Exception as exc:
        logger.error(f"Failed to connect to MQTT: {exc}")

    return client


# ---------------------------------------------------------------------------
# FastAPI app
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


class VoicePayload(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=200)


@app.get("/")
def root():
    return {
        "status": "BrailleDecoder backend is running",
        "voice_page": "/voice",
        "api_docs": "/docs",
    }


@app.get("/health")
def health():
    connected = bool(mqtt_client and mqtt_client.is_connected())
    return {"status": "ok", "mqtt_connected": connected}


def publish_letters_async(text: str) -> None:
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


@app.post("/voice/process")
def process_voice(payload: VoicePayload):
    """
    Receives a transcript from the voice page, extracts letters, and
    publishes them to MQTT. Used by the /voice web page — no secret
    required since it's a public-facing endpoint with simple input.
    """
    transcript = payload.transcript.strip().lower()

    # Heuristic: extract letters from the transcript.
    # Examples:
    #   "b"               -> "B"
    #   "letter b"        -> "B"
    #   "show me a b"     -> "B"
    #   "spell hello"     -> "HELLO"
    #   "hello"           -> "HELLO"

    spell_keywords = ["spell ", "write ", "type "]
    spell_mode = any(transcript.startswith(k) or f" {k}" in transcript for k in spell_keywords)

    # Strip common filler phrases
    fillers = [
        "show me the letter ", "show the letter ", "show me letter ",
        "show me a ", "show me ", "the letter ", "letter ", "show ",
        "spell the word ", "spell out ", "spell ",
        "write the word ", "write out ", "write ",
        "type the word ", "type out ", "type ",
        "display ", "please ", "what is ",
    ]
    cleaned = transcript
    for filler in sorted(fillers, key=len, reverse=True):
        if cleaned.startswith(filler):
            cleaned = cleaned[len(filler):]
            break

    # Keep only alphabetic chars (skip spaces, punctuation, digits)
    letters = "".join(ch for ch in cleaned if ch.isalpha()).upper()

    if not letters:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "no letters detected", "heard": transcript},
        )

    if len(letters) > 20:
        letters = letters[:20]

    logger.info(f"Voice transcript: '{transcript}' -> letters: {letters}")
    publish_letters_async(letters)

    # Build a friendly spoken response for the page to play back
    if len(letters) == 1:
        spoken_response = f"Showing the letter {letters}"
    else:
        spoken_response = f"Spelling {letters}"

    return {
        "ok": True,
        "heard": transcript,
        "letters": letters,
        "length": len(letters),
        "spoken_response": spoken_response,
    }


# ---------------------------------------------------------------------------
# Voice page (HTML served directly)
# ---------------------------------------------------------------------------
VOICE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>BrailleDecoder Voice</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; width: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(180deg, #0a0e27 0%, #1a1f3a 100%);
    color: #e8eaf2;
    overflow: hidden;
  }
  .page {
    min-height: 100vh;
    min-height: 100dvh;
    display: grid;
    grid-template-rows: auto 1fr auto;
    padding: 32px 20px 20px;
    gap: 16px;
  }
  header {
    text-align: center;
  }
  h1 {
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(90deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 6px;
    line-height: 1.2;
  }
  .subtitle {
    font-size: 14px;
    color: #9ca3af;
  }
  main {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 24px;
    text-align: center;
    width: 100%;
    max-width: 360px;
    margin: 0 auto;
  }
  .mic-button {
    width: 180px;
    height: 180px;
    border-radius: 50%;
    border: none;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 10px 40px rgba(59, 130, 246, 0.4);
    transition: transform 0.15s ease, box-shadow 0.3s ease;
    -webkit-tap-highlight-color: transparent;
    flex-shrink: 0;
  }
  .mic-button:active { transform: scale(0.95); }
  .mic-button.listening {
    background: linear-gradient(135deg, #ef4444, #f97316);
    animation: pulse 1.4s infinite;
  }
  @keyframes pulse {
    0%, 100% { box-shadow: 0 10px 40px rgba(239, 68, 68, 0.5); }
    50% { box-shadow: 0 10px 60px rgba(239, 68, 68, 0.9), 0 0 0 20px rgba(239, 68, 68, 0.15); }
  }
  .mic-icon {
    width: 64px;
    height: 64px;
    fill: white;
  }
  .feedback {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    width: 100%;
    min-height: 80px;
  }
  .status {
    font-size: 16px;
    color: #9ca3af;
    min-height: 24px;
    transition: color 0.3s;
  }
  .status.active { color: #60a5fa; }
  .status.success { color: #34d399; }
  .status.error { color: #f87171; }
  .transcript {
    font-size: 22px;
    font-weight: 600;
    color: #f3f4f6;
    min-height: 30px;
    letter-spacing: 0.5px;
    word-break: break-word;
  }
  .hint {
    font-size: 13px;
    color: #6b7280;
    max-width: 320px;
    line-height: 1.5;
  }
  footer {
    text-align: center;
    font-size: 12px;
    color: #4b5563;
    padding-top: 8px;
  }
  footer a { color: #6b7280; text-decoration: none; }
  .unsupported {
    background: #7f1d1d;
    color: #fecaca;
    padding: 16px 24px;
    border-radius: 12px;
    max-width: 320px;
    text-align: center;
    font-size: 14px;
    line-height: 1.5;
  }
</style>
</head>
<body>
  <div class="page">
    <header>
      <h1>BrailleDecoder</h1>
      <div class="subtitle">Speak a letter or word</div>
    </header>

    <main id="app">
      <button id="micBtn" class="mic-button" aria-label="Start listening">
        <svg class="mic-icon" viewBox="0 0 24 24">
          <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3z"/>
          <path d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.92V21a1 1 0 1 0 2 0v-3.08A7 7 0 0 0 19 11z"/>
        </svg>
      </button>

      <div class="feedback">
        <div id="status" class="status">Tap the mic to speak</div>
        <div id="transcript" class="transcript"></div>
      </div>

      <div class="hint">
        Try: "B", "letter C", "spell hello", or "show me an A"
      </div>
    </main>

    <footer>
      BrailleDecoder · <a href="/docs">API Docs</a>
    </footer>
  </div>

<script>
  const micBtn = document.getElementById('micBtn');
  const statusEl = document.getElementById('status');
  const transcriptEl = document.getElementById('transcript');
  const appEl = document.getElementById('app');

  // Check browser support
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    appEl.innerHTML = `
      <div class="unsupported">
        Your browser doesn't support speech recognition. <br><br>
        Please use Chrome on Android, Safari on iPhone, or Chrome/Edge on desktop.
      </div>`;
  } else {
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    let isListening = false;
    let finalTranscript = '';

    function setStatus(text, type = '') {
      statusEl.textContent = text;
      statusEl.className = 'status' + (type ? ' ' + type : '');
    }

    function speak(text) {
      try {
        // Cancel anything currently speaking
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        utter.lang = 'en-US';
        utter.rate = 1.0;
        utter.pitch = 1.0;
        window.speechSynthesis.speak(utter);
      } catch (e) {
        console.warn('TTS not available', e);
      }
    }

    function startListening() {
      finalTranscript = '';
      transcriptEl.textContent = '';
      try {
        recognition.start();
      } catch (e) {
        console.warn('Already started', e);
      }
    }

    function stopListening() {
      try { recognition.stop(); } catch (e) {}
    }

    recognition.onstart = () => {
      isListening = true;
      micBtn.classList.add('listening');
      setStatus('Listening...', 'active');
    };

    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += t;
        } else {
          interim += t;
        }
      }
      transcriptEl.textContent = (finalTranscript + interim).trim();
    };

    recognition.onerror = (event) => {
      console.error('Speech error:', event.error);
      micBtn.classList.remove('listening');
      isListening = false;
      if (event.error === 'no-speech') {
        setStatus('I didn\\'t hear anything. Try again.', 'error');
      } else if (event.error === 'not-allowed') {
        setStatus('Microphone permission denied. Enable it in browser settings.', 'error');
      } else {
        setStatus('Error: ' + event.error, 'error');
      }
    };

    recognition.onend = async () => {
      micBtn.classList.remove('listening');
      isListening = false;
      const transcript = finalTranscript.trim();
      if (!transcript) {
        if (statusEl.classList.contains('active')) {
          setStatus('No speech detected. Tap to try again.');
        }
        return;
      }

      setStatus('Sending...', 'active');

      try {
        const res = await fetch('/voice/process', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ transcript }),
        });
        const data = await res.json();

        if (data.ok) {
          setStatus(`✓ Sent: ${data.letters}`, 'success');
          speak(data.spoken_response);
        } else {
          setStatus('Could not detect letters. Try again.', 'error');
          speak("Sorry, I didn't catch any letters.");
        }
      } catch (err) {
        console.error(err);
        setStatus('Network error. Check connection.', 'error');
      }
    };

    micBtn.addEventListener('click', () => {
      if (isListening) {
        stopListening();
      } else {
        startListening();
      }
    });
  }
</script>
</body>
</html>
"""


@app.get("/voice", response_class=HTMLResponse)
def voice_page():
    return HTMLResponse(content=VOICE_HTML)
