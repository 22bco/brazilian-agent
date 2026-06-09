# Dip Your Trip — WhatsApp agent for Brazilian travelers

A conversational agent that meets Brazilian travelers on WhatsApp, in natural
Brazilian Portuguese, about DYT's 5 real trips. It answers **only** from the data
(never invents a price, hotel, place, or date), runs discovery with a few sharp
questions, and when the topic turns to price it captures the lead and hands off to
a human.

> The original challenge brief is in [`CHALLENGE.md`](CHALLENGE.md).
> Design decisions and tradeoffs are in [`DESIGN.md`](DESIGN.md).

## Architecture

```
WhatsApp ──► Kapso ──► POST /webhook (FastAPI)
                           │  acks 200 immediately; processes in background
                           ▼
                      agent.respond()
                       ├─ system prompt + catalog (grounding)
                       ├─ LLM (DeepSeek, OpenAI-compatible · swappable)
                       └─ tools: registrar_lead · solicitar_handoff
                           │
                           ├─► Google Sheets (leads, via Apps Script) ──► visible from outside
                           └─► kapso.send_text() ──► reply on WhatsApp
```

- **No RAG.** There are only 5 trips; the cleaned catalog fits entirely in the
  prompt — simpler and more reliable. `scripts/build_catalog.py` turns the messy
  CSV into `data/trips.clean.json`.
- **Isolated channel.** Everything Kapso-specific lives in `app/channels/kapso.py`;
  the agent only speaks `(user_id, text)`. Swapping channels = another adapter.
- **Swappable LLM provider** via env var (`LLM_PROVIDER`).

## Layout

```
app/
  main.py        FastAPI webhook (Kapso → agent → reply)
  agent.py       LLM loop + tool-calling
  prompt.py      pt-BR persona + grounding rules
  catalog.py     loads the clean catalog → text for the prompt
  tools.py       tool schemas and dispatch
  leads.py       lead/handoff sink (local JSONL + Google Sheets)
  memory.py      per-number memory (cross-session)
  config.py      env vars (LLM, Kapso, Sheets)
  channels/kapso.py   WhatsApp adapter (parse, signature, send)
scripts/
  build_catalog.py    messy CSV → trips.clean.json
  chat.py             local REPL to talk to the agent
  leads_webapp.gs     Apps Script that receives leads into the Google Sheet
evals/
  cases.py · harness.py · run_evals.py · test_grounding.py
data/
  trips.csv · trips.clean.json
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env          # edit .env with your keys
python -m scripts.build_catalog   # generates data/trips.clean.json
```

At minimum, fill in `.env`:

```
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
```

## Run

**Chat locally (no WhatsApp):**

```bash
python -m scripts.chat
```

**Webhook (to connect to WhatsApp):**

```bash
uvicorn app.main:app --reload --port 8099
```

Expose it with a tunnel and register the URL in Kapso (see below):

```bash
ngrok http 8099    # use the https URL + /webhook in the Kapso dashboard
```

## Connect WhatsApp (Kapso)

1. Create a free [Kapso](https://kapso.ai) account (the free plan includes a
   sandbox number, no Meta setup).
2. In the dashboard, edit the connected number and point the webhook to
   `https://YOUR-TUNNEL/webhook`.
3. Copy the API key (Project Settings → API Keys) into `KAPSO_API_KEY` in `.env`.
4. (Optional, recommended) set `KAPSO_WEBHOOK_SECRET` to validate the
   `X-Webhook-Signature` header.

## See leads from outside (Google Sheets)

1. Open your Google Sheet → Extensions → Apps Script.
2. Paste `scripts/leads_webapp.gs`, change `SECRET`, and deploy as a **web app**
   (access: "Anyone").
3. Put the `/exec` URL in `LEADS_WEBAPP_URL` and the same secret in
   `LEADS_WEBAPP_SECRET` in `.env`.

Without this configured, leads are still recorded locally in
`data/leads.local.jsonl` (fallback).

## Alternative channel: Baileys with voice notes

A second, independent WhatsApp channel lives in [`baileys/`](baileys/) — a
self-hosted Node sidecar built on Baileys that adds **native voice notes** (audio
in/out via STT/TTS). It reuses the same Python brain through the channel-neutral
`POST /message` endpoint, so nothing about the agent is duplicated. Kapso stays
the primary, lower-risk channel; Baileys is the "go deep on audio" bet. See
[`baileys/README.md`](baileys/README.md) for how to run it and the tradeoffs.

## Evals (proof it doesn't hallucinate)

```bash
python -m evals.run_evals      # report with PASS/FAIL per case
pytest evals/ -v               # as tests
```

The cases attack grounding along the brief's vectors: price (direct and
disguised), off-catalog country, specific date/availability, non-existent hotel,
invented detail, and the ambiguous Ski & Vinho duration.
