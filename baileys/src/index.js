// index.js - Sidecar del canal WhatsApp vía Baileys (alternativo a Kapso).
//
// Arquitectura (paralela a la de Kapso): este proceso solo hace de CANAL.
// Recibe mensajes de WhatsApp, los puentea al cerebro Python (POST /message) y
// responde. Para notas de voz: audio → STT → cerebro → TTS → nota de voz.
//
// El cerebro (grounding, tools, leads, memoria, evals) NO se duplica.
//
// Uso:
//   1) Levanta el core Python:  uvicorn app.main:app --port 8099
//   2) npm start  → escanea el QR con el número dedicado de WhatsApp.

import makeWASocket, {
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import pino from "pino";
import qrcode from "qrcode-terminal";

import { config, audioEnabled } from "./config.js";
import { askBrain } from "./bridge.js";
import { synthesize, transcribe } from "./audio.js";
import { typingDelayMs, recordingDelayMs, jitter } from "./humanize.js";

const logger = pino({ level: "silent" });

// Guard de re-entrada: evita que múltiples eventos 'close' lancen start() en
// paralelo y dejen varios sockets vivos (respuestas duplicadas + leak).
let starting = false;

// Desempaqueta envoltorios (ephemeral / viewOnce) para leer el contenido real.
function unwrap(message) {
  return (
    message?.ephemeralMessage?.message ||
    message?.viewOnceMessage?.message ||
    message?.viewOnceMessageV2?.message ||
    message
  );
}

function extractText(content) {
  return (
    content?.conversation ||
    content?.extendedTextMessage?.text ||
    content?.imageMessage?.caption ||
    ""
  ).trim();
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Envía texto "como humano": parte la resposta en mensajitos por párrafo (máx 3),
// con "digitando..." y una pausa que escala con el largo (ver humanize.js).
async function sendHumanText(sock, jid, text, incomingChars = 0) {
  const parts = text.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean);
  const chunks = (parts.length ? parts : [text]).slice(0, 3);
  for (let i = 0; i < chunks.length; i++) {
    const part = chunks[i];
    await sock.sendPresenceUpdate("composing", jid);
    // el tiempo de "leer" tu mensaje solo cuenta antes del primer trozo
    await sleep(jitter(typingDelayMs(i === 0 ? incomingChars : 0, part.length)));
    await sock.sendPresenceUpdate("paused", jid);
    await sock.sendMessage(jid, { text: part });
    if (i < chunks.length - 1) await sleep(jitter(450));
  }
}

// Envía la nota de voz con "gravando áudio..." y una pausa proporcional al largo
// del audio (ver humanize.js).
async function sendHumanVoice(sock, jid, audioBuffer) {
  await sock.sendPresenceUpdate("recording", jid);
  await sleep(jitter(recordingDelayMs(audioBuffer.length)));
  await sock.sendPresenceUpdate("paused", jid);
  await sock.sendMessage(jid, {
    audio: audioBuffer,
    ptt: true,
    mimetype: "audio/ogg; codecs=opus",
  });
}

async function handleMessage(sock, msg) {
  const jid = msg.key.remoteJid;
  // Ignorar: salidas propias, estados, y grupos (el agente es 1:1).
  if (!msg.message || msg.key.fromMe) return;
  if (jid === "status@broadcast" || jid.endsWith("@g.us")) return;

  // En WhatsApp moderno remoteJid puede venir como '@lid'; preferimos el teléfono
  // real (senderPn) para keyear memoria/leads igual que Kapso. Respondemos a `jid`.
  const phoneJid = msg.key.senderPn || (jid.endsWith("@lid") ? null : jid);
  const userId = (phoneJid || jid).split("@")[0];
  const content = unwrap(msg.message);
  const audio = content?.audioMessage;
  const text = extractText(content);

  // "Visto": marca el mensaje como leído antes de responder (toque humano).
  await sock.readMessages([msg.key]).catch(() => {});

  // --- Nota de voz entrante -------------------------------------------------
  if (audio) {
    if (!audioEnabled) {
      await sendHumanText(
        sock,
        jid,
        "Recebi seu áudio! 🙏 Mas agora consigo responder melhor por texto, pode me escrever?"
      );
      return;
    }
    const buffer = await downloadMediaMessage(
      msg,
      "buffer",
      {},
      { logger, reuploadRequest: sock.updateMediaMessage }
    );
    const transcript = await transcribe(buffer);
    if (!transcript) return;
    console.log(`🎙️  ${userId}: ${transcript}`);
    const reply = await askBrain(userId, transcript);
    const voice = await synthesize(reply);
    await sendHumanVoice(sock, jid, voice);
    return;
  }

  // --- Texto ----------------------------------------------------------------
  if (text) {
    console.log(`💬 ${userId}: ${text}`);
    const reply = await askBrain(userId, text);
    await sendHumanText(sock, jid, reply, text.length);
  }
}

async function start() {
  if (starting) return; // ya hay una conexión en curso
  starting = true;

  const { state, saveCreds } = await useMultiFileAuthState(config.authDir);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({ version, auth: state, logger });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      console.log("\n📱 Escaneie o QR com o WhatsApp do número dedicado:\n");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "open") {
      starting = false;
      console.log("✅ Conectado ao WhatsApp.");
      console.log(`   Cérebro: ${config.bridgeUrl}  ·  Áudio: ${audioEnabled ? "on" : "off (texto)"}`);
    }
    if (connection === "close") {
      starting = false;
      const code = new Boom(lastDisconnect?.error)?.output?.statusCode;
      const loggedOut = code === DisconnectReason.loggedOut;
      console.log(`⚠️  Conexão fechada (code ${code}).`, loggedOut ? "Sessão encerrada." : "Reconectando…");
      if (!loggedOut) start();
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const msg of messages) {
      try {
        await handleMessage(sock, msg);
      } catch (err) {
        console.error("Erro ao processar mensagem:", err?.message || err);
        const jid = msg?.key?.remoteJid;
        if (jid) {
          await sock
            .sendMessage(jid, { text: "Ops, tive um probleminha aqui 😅 pode repetir?" })
            .catch(() => {});
        }
      }
    }
  });
}

start().catch((err) => {
  console.error("Falha ao iniciar o sidecar Baileys:", err);
  process.exit(1);
});
