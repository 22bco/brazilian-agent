// audio.js - Voice notes: STT (transcripción) y TTS (síntesis).
// Vive en la capa de canal, así el cerebro Python sigue siendo texto puro.
//
//   STT: OpenAI Whisper (audio ogg/opus de WhatsApp -> texto).
//   TTS: ElevenLabs (voces pt-BR más naturais) u OpenAI, configurable por env.
//
// ElevenLabs devuelve mp3; lo transcodificamos a opus con ffmpeg para mandarlo
// como nota de voz (ptt) de WhatsApp. (ffmpeg debe estar instalado.)

import OpenAI, { toFile } from "openai";
import { spawn } from "node:child_process";
import { config, audioEnabled } from "./config.js";

let _client = null;
function openai() {
  if (!_client) _client = new OpenAI({ apiKey: config.openaiApiKey });
  return _client;
}

// Audio entrante (Buffer ogg/opus de WhatsApp) -> texto.
export async function transcribe(buffer) {
  if (!audioEnabled) throw new Error("audio desabilitado");
  const file = await toFile(buffer, "audio.ogg", { type: "audio/ogg" });
  const out = await openai().audio.transcriptions.create({
    file,
    model: config.sttModel,
    language: "pt",
  });
  return (out.text || "").trim();
}

// Texto -> Buffer de audio opus (nota de voz). Despacha según el proveedor.
export async function synthesize(text) {
  if (!audioEnabled) throw new Error("audio desabilitado");
  if (config.ttsProvider === "elevenlabs") return synthesizeElevenLabs(text);
  return synthesizeOpenAI(text);
}

async function synthesizeOpenAI(text) {
  const resp = await openai().audio.speech.create({
    model: config.ttsModel,
    voice: config.ttsVoice,
    input: text,
    response_format: "opus", // OpenAI entrega opus directo
  });
  return Buffer.from(await resp.arrayBuffer());
}

async function synthesizeElevenLabs(text) {
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${config.elevenLabsVoiceId}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "xi-api-key": config.elevenLabsApiKey,
      "Content-Type": "application/json",
      Accept: "audio/mpeg",
    },
    body: JSON.stringify({
      text,
      model_id: config.elevenLabsModel,
      voice_settings: { stability: 0.5, similarity_boost: 0.75 },
    }),
  });
  if (!resp.ok) {
    throw new Error(`ElevenLabs ${resp.status}: ${await resp.text()}`);
  }
  const mp3 = Buffer.from(await resp.arrayBuffer());
  return mp3ToOpus(mp3); // WhatsApp ptt quiere ogg/opus
}

// Transcodifica mp3 -> ogg/opus usando ffmpeg (vía stdin/stdout).
function mp3ToOpus(mp3) {
  return new Promise((resolve, reject) => {
    const ff = spawn("ffmpeg", [
      "-loglevel", "error",
      "-i", "pipe:0",
      "-c:a", "libopus", "-b:a", "32k",
      "-f", "ogg", "pipe:1",
    ]);
    const out = [];
    const err = [];
    ff.stdout.on("data", (c) => out.push(c));
    ff.stderr.on("data", (c) => err.push(c));
    ff.on("error", (e) =>
      reject(new Error(`ffmpeg não disponível? ${e.message}`))
    );
    ff.on("close", (code) =>
      code === 0
        ? resolve(Buffer.concat(out))
        : reject(new Error(`ffmpeg falhou: ${Buffer.concat(err)}`))
    );
    ff.stdin.on("error", () => {});
    ff.stdin.write(mp3);
    ff.stdin.end();
  });
}
