// audio.js — Voice notes: STT (transcripción) y TTS (síntesis).
// Vive en la capa de canal (igual que el resto de lo específico de WhatsApp), así
// el cerebro Python sigue siendo texto puro. Proveedor: OpenAI (Whisper + TTS),
// configurable por env. Salida en opus para mandarla como nota de voz (ptt).

import OpenAI, { toFile } from "openai";
import { config, audioEnabled } from "./config.js";

let _client = null;
function client() {
  if (!_client) _client = new OpenAI({ apiKey: config.openaiApiKey });
  return _client;
}

// Audio entrante (Buffer ogg/opus de WhatsApp) → texto.
export async function transcribe(buffer) {
  if (!audioEnabled) throw new Error("audio desabilitado (sem OPENAI_API_KEY)");
  const file = await toFile(buffer, "audio.ogg", { type: "audio/ogg" });
  const out = await client().audio.transcriptions.create({
    file,
    model: config.sttModel,
    language: "pt",
  });
  return (out.text || "").trim();
}

// Texto → Buffer de audio opus (para enviar como nota de voz).
export async function synthesize(text) {
  if (!audioEnabled) throw new Error("audio desabilitado (sem OPENAI_API_KEY)");
  const resp = await client().audio.speech.create({
    model: config.ttsModel,
    voice: config.ttsVoice,
    input: text,
    response_format: "opus",
  });
  return Buffer.from(await resp.arrayBuffer());
}
