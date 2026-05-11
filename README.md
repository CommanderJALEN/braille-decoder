# BrailleDecoder

An IoT Braille teaching device that responds to **voice commands** using AI speech recognition.
Speak a letter (or whole word) into your phone, and the device lights up the corresponding
Braille dot pattern on a 6-LED grid while displaying the letter on a mini OLED screen.

## Live Demo

- **Voice Web App**: https://braille-decoder-production.up.railway.app/voice
- **API Docs**: https://braille-decoder-production.up.railway.app/docs

Open the voice app on any modern phone or desktop browser, tap the mic, and speak.

## How It Works

```
   User speaks into phone
            │
            ▼
   Browser Speech AI (Google / Apple)
            │  transcript
            ▼
   Voice Web Page  ──HTTP──▶  Railway Backend (FastAPI)
                                       │
                                       │ MQTT publish
                                       ▼
                              HiveMQ Cloud Broker
                                       │
                                       │ MQTT subscribe
                                       ▼
                                 ESP32 (Wi-Fi)
                                       │
                                       ▼
                          LEDs + OLED light up
                                       │
                                       ▼
                     Voice page speaks confirmation back
```

The user never types — they speak, the AI transcribes, the cloud routes the letter, and the
device responds physically and verbally.

## Tech Stack

| Layer        | Technology                                           |
|--------------|------------------------------------------------------|
| Voice Input  | Browser Web Speech API (Google / Apple speech AI)    |
| Voice Output | Browser SpeechSynthesis (Text-to-Speech)             |
| Frontend     | Vanilla HTML + CSS + JS (served from FastAPI)        |
| Backend      | Python 3 + FastAPI, deployed on Railway              |
| Messaging    | MQTT over TLS via HiveMQ Cloud                       |
| Firmware     | C++ on PlatformIO (Arduino framework) — *in progress*|
| Hardware     | ESP32, 6× LEDs, SSD1306 OLED, perfboard             |
| Version Ctrl | GitHub (auto-deploy to Railway on push)              |

## Features

- 🎙️ **Voice-first interface** — no typing, no buttons
- 🧠 **AI speech recognition** via the browser's built-in neural speech engine
- 🗣️ **Speaks back** confirmation ("Showing the letter B", "Spelling HELLO")
- 📱 **Mobile-ready** — works on Chrome Android, Safari iOS, and desktop browsers
- ☁️ **Cloud-hosted** — accessible from anywhere with internet
- ⚡ **Real-time** — letter appears on the device within ~1 second of speaking
- 🔤 **Smart parsing** — handles "B", "letter C", "spell hello", "show me an A"
- 🔒 **Authenticated API** — webhook protected with secret header

## Repository Structure

```
braille-decoder/
├── backend/                  # FastAPI app deployed on Railway
│   ├── main.py               # API + voice page + MQTT publisher
│   ├── requirements.txt      # Python dependencies
│   └── Procfile              # Railway start command
├── firmware/                 # ESP32 C++ firmware (coming soon)
├── HARDWARE.md               # Bill of materials and wiring notes
├── README.md
└── .gitignore
```

## Backend API

| Method | Endpoint           | Description                                   |
|--------|--------------------|-----------------------------------------------|
| GET    | `/`                | Service status                                |
| GET    | `/health`          | Health check + MQTT connection status         |
| GET    | `/voice`           | Voice control web app (HTML)                  |
| POST   | `/voice/process`   | Receives a voice transcript, extracts letters |
| POST   | `/webhook/letter`  | Direct letter webhook (secret-protected)      |

### Example: speak "spell hello"
```
POST /voice/process
{ "transcript": "spell hello" }
```
Response:
```json
{
  "ok": true,
  "heard": "spell hello",
  "letters": "HELLO",
  "length": 5,
  "spoken_response": "Spelling HELLO"
}
```

The backend publishes each letter to MQTT topic `braille/letter` with a 1.5s delay
between letters, so the ESP32 has time to display each one before the next.

## Project Status

- [x] FastAPI backend built and tested locally
- [x] GitHub repo with version control
- [x] Backend deployed to Railway with public URL
- [x] Webhook authentication working
- [x] MQTT integration with HiveMQ Cloud
- [x] Letter-by-letter publishing for whole words
- [x] Voice control web app at `/voice`
- [x] Browser AI speech recognition
- [x] Spoken response via TTS
- [x] Mobile-friendly UI
- [ ] ESP32 firmware (LED + OLED control)
- [ ] Hardware wiring and soldering
- [ ] End-to-end integration test
- [ ] Final enclosure / assembly

## Local Development

```bash
cd backend
py -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

Then visit:
- http://127.0.0.1:8000/docs — API docs
- http://127.0.0.1:8000/voice — voice control page

Speech recognition requires **HTTPS in production**, but `127.0.0.1` is treated as
secure by browsers, so local testing works.

## Environment Variables

These are set in Railway's dashboard, never committed to the repo.

| Variable        | Description                                |
|-----------------|--------------------------------------------|
| `IFTTT_SECRET`  | Shared secret for the `/webhook/letter` endpoint |
| `MQTT_HOST`     | HiveMQ Cloud cluster URL                   |
| `MQTT_PORT`     | `8883` (TLS)                               |
| `MQTT_USER`     | HiveMQ username                            |
| `MQTT_PASS`     | HiveMQ password                            |
| `MQTT_TOPIC`    | Default: `braille/letter`                  |

## Team

Built by Group [6] for [BSCpE 4-1].

| Member                   | Role                  |
|--------------------------|-----------------------|
| Roan Andrei Uson         | Project Manager       |
| Andrei Capili            | Website manager       |
| Angel Matthew Marcos     | Software              |
| Adrian Paul Peralta      | Hardware              |
| John Allen Peralta       | Software              |
| Frankin Evan Villacampa  | (role)                |