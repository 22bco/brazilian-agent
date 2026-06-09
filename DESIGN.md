# DESIGN.md

Notes on how this agent is built, what I chose and why, what's faked, and where
I'd take it next.

## The core bet: grounding by construction, not by retrieval

There are only 5 trips. The whole catalog fits in the prompt for a fraction of a
cent, so **I deliberately skipped RAG / vector search**. A retrieval layer here
would add moving parts, failure modes, and latency to solve a problem I don't
have. Instead, grounding comes from two things:

1. A **deterministic cleaning pipeline** (`scripts/build_catalog.py`) that turns
   the messy operational CSV into a structured `trips.clean.json` — the single
   source of truth.
2. A **strict system prompt** that says, in pt-BR, "you may only assert what's in
   the catalog; never invent price, hotel, place, or date; when in doubt, bridge
   to a human."

The payoff is observable: `evals/` runs 8 adversarial cases (price, off-catalog
country, specific date, non-existent hotel, invented activity, disguised price
pressure) and the agent holds the line on all of them.

## Decisions & tradeoffs

| Decision | Why | Tradeoff I accepted |
|---|---|---|
| **Python + FastAPI** | Async webhook, clean LLM SDK integration, legible repo | — |
| **DeepSeek (OpenAI-compatible)** | Cheap (well under the US$5 cap), good tool-use | pt-BR is slightly less polished than Claude/GPT — so I made the provider swappable via `LLM_PROVIDER`; switching is one env var |
| **No RAG; full catalog in prompt** | 5 trips, fits cheaply, far more reliable | Wouldn't scale to hundreds of trips without chunking/retrieval |
| **Channel-agnostic core** | Agent speaks only `(user_id, text)`; Kapso is one adapter | A tiny bit more indirection up front |
| **Kapso** | Recommended by the brief; sandbox number, no Meta setup; it's how they'll test | Tied to their tester flow — documented |
| **Leads → Google Sheets via Apps Script** | Reviewers watch leads appear live, no service-account dance | Manual one-time deploy; public web-app URL guarded by a shared secret |
| **Fast-ack + background processing** | Kapso wants 2xx in <5s; the LLM can take longer | Reply arrives via the send API a moment later, not in the webhook response |
| **Tools for lead/handoff** | The model decides *when* to capture/escalate; backend stays observable | Relies on the model calling tools at the right moment (covered by evals + prompt flow) |
| **Per-number memory on disk** | Multi-turn discovery + cross-session continuity | File-per-number; fine for the challenge, not for scale |

## The data was messy on purpose — how I handled it

- **Hours** mix formats (`14:00`, `8:00`, `14:40:00`, `11:10:00 AM - 12.54`,
  `1.15`). I normalize what's unambiguous to `HH:MM`, and for genuinely ambiguous
  values (`1.15`, no AM/PM) I **keep the raw string and do not guess** a time.
- **Slugs** (`torres-del-paine`) → readable names with correct accents.
- **`detail`** mixes Spanish/English with typos. I keep it verbatim as the source
  of truth and let the LLM phrase it in warm pt-BR at conversation time — cleaning
  it offline risked changing facts.
- **Duration** lives only on a "lead row". I trust it **only when it agrees with
  the actual booked nights**; this is computed generically, not hardcoded.

## The thing I'm proudest of: the Ski & Vinho ambiguity

The `Ski_Vinho` lead row claims 7 days, but the program only has lodging and
activities through day 5 (4 nights) — a real inconsistency in the source. The easy
move is to pick a number and move on. Instead the pipeline **detects the conflict
generically** (lead-row `n_days` ≠ booked nights), flags that trip's duration as
not-confident, and the prompt instructs the agent to **not state a fixed number**
and describe it by itinerary / confirm with a human.

That's the whole spirit of the challenge in one feature: when the data is
untrustworthy, the agent stays honest instead of confidently wrong. The
`duracao_ski_ambigua` eval proves it behaves this way.

## Two channels, on purpose

The channel-agnostic core pays off concretely: there are **two WhatsApp channels**
sharing one brain.

- **Kapso** (`app/channels/kapso.py` + `/webhook`) — primary. Recommended by the
  brief, no ban risk, matches the sandbox tester-number flow. Async fast-ack.
- **Baileys** (`baileys/`, a Node sidecar) — the creative bet: self-hosted, with
  **native voice notes** (audio in → STT → brain → TTS → audio out). It talks to
  the brain via the channel-neutral `POST /message`, so the agent is untouched.

Baileys is unofficial (ban risk, dedicated number, you'd message our number
directly), so Kapso is the deliverable channel and Baileys is the "delight" demo.
Details and tradeoffs in `baileys/README.md`.

## What's currently faked or not wired

- **Live WhatsApp & Sheets are deferred to one-time manual setup.** The code paths
  are complete and tested locally (simulated Kapso payload through the real webhook;
  leads through the same sink). What's missing is *my* ability to create the user's
  Kapso account and deploy the Apps Script — both live in their accounts. Until
  `LEADS_WEBAPP_URL` is set, leads fall back to `data/leads.local.jsonl`.
- **Voice notes** exist in the Baileys channel (audio in/out via STT/TTS), but
  the code path is complete-but-not-live-tested: it needs a paired number and an
  `OPENAI_API_KEY`. The Kapso channel is still text-only.
- **Idempotency is in-memory** (`_seen_messages` set). A restart forgets seen
  message IDs; a persistent store would be needed in production.
- **Season awareness is shallow** — the agent can comment on a region's season
  from general knowledge but doesn't reason deeply about it.

## With another week

1. **Harden voice notes.** The Baileys channel already does audio in/out; with
   another week I'd live-test it end to end, tune the pt-BR TTS voice, and handle
   long replies / chunking gracefully.
2. **Inline media** — a map or a couple of photos per trip.
3. **Lead dedup & richer CRM fields** in Sheets (status, last-contact, source).
4. **Persistent store** (Redis/Postgres) for memory + idempotency.
5. **Cost/latency instrumentation** with real numbers per conversation.
6. **Expand the eval set + CI** — more attack vectors, run on every push.
