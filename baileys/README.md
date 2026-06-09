# Baileys channel — alternative WhatsApp adapter with voice notes

This is a **second, independent WhatsApp channel** for the same agent, built on
[Baileys](https://github.com/WhiskeySockets/Baileys) instead of Kapso. It exists
to go deep on the one thing the brief highlights as how Brazilians really use
WhatsApp: **voice notes (audio in and out).**

It reuses the **entire Python brain** (grounding, tools, leads, memory, evals) —
nothing is duplicated. This process is *only* a channel.

```
WhatsApp (dedicated number)
   │  Web multi-device (QR pairing)
   ▼
Baileys sidecar (Node)
   ├─ text  ─────────────► POST /message {user_id, text} ──► reply ──► send text
   └─ voice note ─► STT ─► POST /message {user_id, text} ──► reply ─► TTS ─► send voice note
                                   (same Python brain, unchanged)
```

## Why it's separate from Kapso (note for reviewers)

We ship **two channels side by side**, on purpose:

- **Kapso** (`app/channels/kapso.py` + `/webhook`) is the primary channel — it's
  what the brief recommends, has zero ban risk, and matches how you test (adding
  your tester number to our sandbox).
- **Baileys** (this folder) is the creative bet: a self-hosted channel with
  **native voice notes**. It talks to the same brain through the channel-neutral
  `POST /message` endpoint.

Honest tradeoffs of the Baileys route:

- ⚠️ **Unofficial** (reverse-engineered WhatsApp Web) → against WhatsApp ToS,
  with real **ban risk** for an automated new number.
- ⚠️ Needs a **dedicated phone number** (QR pairing) and a Node process.
- ⚠️ You'd message **our number directly** (no sandbox tester-number flow).
- ✅ Free, self-hosted, full control, and **audio that feels native** on WhatsApp.

Because of the ban risk, we treat Kapso as the deliverable channel and Baileys as
the "if we had another week, here's the delight" demo.

## Run

Prereq: the Python brain must be running.

```bash
# 1) in the repo root — start the brain
uvicorn app.main:app --port 8099

# 2) here — install and start the sidecar
cd baileys
npm install
npm start          # shows a QR; scan it with the dedicated WhatsApp number
```

Auth state is persisted in `baileys/auth/` (gitignored). After the first pairing
you won't need the QR again.

## Voice notes

Set `OPENAI_API_KEY` in the repo-root `.env` to enable audio (STT via Whisper,
TTS as opus). Without it, the channel still works in **text only** and politely
asks audio senders to type.

Relevant env (all in the root `.env`):

```
PYTHON_BRIDGE_URL=http://127.0.0.1:8099
BRIDGE_TOKEN=                 # optional shared secret with the Python /message
OPENAI_API_KEY=              # enables voice notes
# STT_MODEL=whisper-1
# TTS_MODEL=gpt-4o-mini-tts
# TTS_VOICE=nova
```

## Files

```
src/index.js    Baileys connection, QR, reconnection, message handler
src/bridge.js   HTTP bridge to the Python brain (POST /message)
src/audio.js    STT (transcribe) + TTS (synthesize), OpenAI
src/config.js   loads the root .env and exposes config
```
