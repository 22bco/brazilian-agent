// config.js — Carga el .env de la raíz del repo y expone la configuración del
// sidecar. Reutiliza el mismo .env donde viven las llaves del core Python.

import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// src está en baileys/src → la raíz del repo es dos niveles arriba.
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

export const config = {
  // Puente al cerebro Python (endpoint canal-neutral POST /message).
  bridgeUrl: process.env.PYTHON_BRIDGE_URL || "http://127.0.0.1:8099",
  bridgeToken: process.env.BRIDGE_TOKEN || "",

  // Audio (voice notes). Sin OPENAI_API_KEY, el canal sigue funcionando en texto.
  openaiApiKey: process.env.OPENAI_API_KEY || "",
  sttModel: process.env.STT_MODEL || "whisper-1",
  ttsModel: process.env.TTS_MODEL || "gpt-4o-mini-tts",
  ttsVoice: process.env.TTS_VOICE || "nova",

  authDir: path.resolve(__dirname, "../auth"),
};

export const audioEnabled = Boolean(config.openaiApiKey);
