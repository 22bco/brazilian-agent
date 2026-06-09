// bridge.js — Puente HTTP al cerebro Python.
// El agente (grounding, tools, leads, memoria) NO se duplica: este canal solo
// habla (user_id, texto) con el endpoint canal-neutral POST /message.

import { config } from "./config.js";

export async function askBrain(userId, text) {
  const headers = { "Content-Type": "application/json" };
  if (config.bridgeToken) headers["X-Bridge-Token"] = config.bridgeToken;

  const resp = await fetch(`${config.bridgeUrl}/message`, {
    method: "POST",
    headers,
    body: JSON.stringify({ user_id: userId, text }),
  });

  if (!resp.ok) {
    throw new Error(`bridge ${resp.status}: ${await resp.text()}`);
  }
  const data = await resp.json();
  if (typeof data?.reply !== "string" || !data.reply.trim()) {
    throw new Error("bridge devolveu reply vazio/ausente");
  }
  return data.reply;
}
