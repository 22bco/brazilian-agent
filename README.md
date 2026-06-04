# Dip Your Trip — Growth Engineer Challenge
### Build a WhatsApp travel agent for Brazilian travelers

**Time:** one week from when you receive this.

---

## Why this challenge

Dip Your Trip is an AI-native adventure travel agency in South America. Many of our travelers reach us on WhatsApp, in Portuguese, often not yet knowing exactly what they want. We want to see how you'd build the first version of an agent that meets one of those travelers and actually helps — grounded in our real trips, speaking natural Brazilian Portuguese, and knowing when to bring a human in.

This is deliberately open. We care less about checking boxes and more about how you think: how you ground an LLM in real data, how you design a conversation someone would enjoy on WhatsApp, and what tradeoffs you make under ambiguity.

## The mission

Build an agent, reachable on a real WhatsApp number, that holds a natural Portuguese conversation about our 5 trips: it answers questions, figures out what the traveler is looking for, recommends, and hands off to a human at the right moment. Everything it says about the trips must come from the data we give you. It must never invent a detail, a price, or a trip that doesn't exist.

## The data

In `data/trips.csv` you'll find 5 real DYT itineraries — Atacama, a Chile + Argentina wine route, a Patagonia trek, a Lake District / Chiloé / Cochamó trip, and a ski + wine trip. It's in long format: one row per itinerary item (accommodation, transport, activity, flight, meal, insurance, gear…), with columns `trip_id, start_day, end_day, n_days, start_hour, end_hour, place, item, detail`.

A few honest things about it:

- It's real operational data, so it's a little messy. The `detail` text mixes Spanish and English and has typos, `place` values are slugs (`torres-del-paine`), some hours are blank, and trip length lives on a single lead row rather than every row.
- Days are **relative** (Day 1, Day 2…), not calendar dates. Treat each trip as a **season-agnostic template**, not a bookable date. If season matters to the traveler, use what you know about the region.
- There are **no prices**. That's intentional — see below.

Turning that into clean, warm pt-BR is part of the job.

## What must work (the baseline)

- **Natural Brazilian Portuguese.** Not translated-sounding.
- **Strictly grounded answers** about the 5 trips: itinerary by day, what's included, where you sleep, transfers and flights, how intense it is, who it suits, how long it lasts.
- **Discovery.** You will *not* be told who's messaging or what they want. The agent has to find that out through conversation — ideally a few sharp questions, not a ten-question form.
- **Graceful limits.** Asked about something not in the data (another country, a specific date, a hotel that isn't listed), it says so instead of inventing.
- **Price → human.** We don't publish prices. When someone asks *"quanto custa?"*, that's the cue to capture the lead (name + contact + what they want) and offer to connect them with a person. Inventing a price is an automatic fail.

## Where you get to be creative

The *how* is entirely yours — model, framework, retrieval, personality. Go **deep on one idea** rather than wide on five half-built ones. Some directions (not a checklist):

- Voice notes in and out — audio is how Brazilians actually use WhatsApp.
- A real personality / brand voice.
- Sending a map or photos inline.
- A genuinely good *"não sei o que quero ainda"* discovery flow.
- Clean human handoff and lead qualification.
- Cross-session memory.
- Cost / latency engineering, with real numbers.
- Your own eval harness proving the agent doesn't hallucinate.

If there's something you think would delight a Brazilian traveler that we didn't list — build that instead, and tell us why.

## Tech & setup

- **WhatsApp via Kapso.** Create your own free Kapso account; the free plan includes a sandbox number you can test on with no Meta setup. To let us talk to your agent, you'll register our tester number in your sandbox session (we'll send you a number to add).
- **An LLM of your choice** (OpenAI or Anthropic). Keep total spend under **US$5** — easily enough. With only 5 trips, the whole catalog fits in context cheaply, so the cap is a generous sanity bound; spend your thinking on the conversation, not premature optimization.
- **A webhook** that receives messages and replies. Host it wherever you like — Cloud Run, Cloudflare Workers, Render, Kapso functions — your call.
- **Human handoff:** during development, route any escalation to *your own* email/number — never a real DYT contact. A real contact only gets wired in at the final stage.

## What to deliver

1. **A working WhatsApp number** we can message in Portuguese (sandbox is fine).
2. **The repo**, with a README clear enough to run it.
3. **A way to see your leads from the outside** — a shared sheet, Airtable, a tiny page, anything — so we can chat, leave fake contact details, and watch the lead appear. Same for handoff: show us how we'd see it fire (a live takeover in your Kapso inbox works).
4. **A short `DESIGN.md`:** the decisions you made and why, the tradeoffs, the one thing you're proudest of, the one thing currently faked or broken, and what you'd do with another week.

Rule of thumb: **if you built something that lives in a backend** (leads, tags, memory, handoff), **give us a way to see it work without reading your code.**

## How we'll evaluate

We score two things separately, so going deep in one direction never hurts you:

- **Craft & correctness** — grounding (zero hallucination), pt-BR quality, discovery, and knowing its limits.
- **Product & creativity** — the idea you chose to chase and how well you pulled it off.

Plus basic engineering hygiene: can we run it, is the repo legible, did you make the invisible observable.

Heads up — we'll actively try to break the grounding: places we don't go, trips in the wrong season, prices, details that aren't in the data. An agent that holds the line and bridges to a human scores far higher than one that improvises.

## The bar (example exchange)

> **Viajante:** oi! to pensando em viajar pro chile em janeiro mas to meio perdido 😅
>
> **Agente:** Oi! Janeiro é uma época linda pra isso 🙌 Pra eu te indicar a viagem certa: você curte mais natureza e trilha, ou prefere um ritmo mais tranquilo — paisagem, comida, vinho?
>
> **Viajante:** trilha eu curto mas não sou nenhum atleta kkk
>
> **Agente:** Saquei, então te poupo das mais punk. Tenho uma pelo sul — Puerto Varas, Chiloé e o vale de Cochamó — com trilha de verdade mas em doses civilizadas, vulcão, ilha e muita natureza. Quantos dias mais ou menos você tem?
>
> **Viajante:** uns 8, 9 dias. e quanto fica?
>
> **Agente:** 8–9 dias encaixa certinho — essa é de 8 dias. Sobre valor, a gente monta o orçamento sob medida, então prefiro te passar pra uma pessoa do time que fecha tudo contigo. Me manda seu nome e um contato (email ou WhatsApp)? Já te chamo com os detalhes.

That's the tone, the discovery, the intensity-by-inference, and the price-to-human bridge — in one short exchange.
