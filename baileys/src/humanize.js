// humanize.js - Modela los tiempos "humanos" en función del largo del contenido.
// Idea: la demora no es fija, escala con cuánto hay que leer, teclear o grabar,
// usando velocidades humanas aproximadas. Funciones puras (fáciles de testear).

// --- Texto ----------------------------------------------------------------
// Lectura del mensaje entrante (el humano "lee" lo que le mandaste).
const READ_MS_PER_CHAR = 6; // ~lectura ágil en celular
// Tecleo percibido en móvil: ~22 chars/seg (la "digitando..." que ves antes de
// que llegue un mensaje, no el tecleo literal letra-a-letra).
const TYPE_CHARS_PER_SEC = 22;
const TYPE_MIN_MS = 800;
const TYPE_MAX_MS = 5500;

// --- Audio ----------------------------------------------------------------
// Tamaño del opus como proxy de duración (~32 kbps -> ~4 KB/seg).
const AUDIO_BYTES_PER_SEC = 4000;
// Un humano tarda ~la duración del audio en grabarlo; acotamos por UX a una
// fracción (no hacemos esperar el minuto completo) pero sin ser instantáneo.
const RECORD_FRACTION = 0.5;
const RECORD_MIN_MS = 1500;
const RECORD_MAX_MS = 10000;

const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

// Demora de "digitando..." antes de un trozo de respuesta.
//   incomingChars: largo del mensaje del viajante (lo que el agente "lee").
//   replyChars:    largo de este trozo de respuesta (lo que "teclea").
export function typingDelayMs(incomingChars, replyChars) {
  const read = incomingChars * READ_MS_PER_CHAR;
  const type = (replyChars / TYPE_CHARS_PER_SEC) * 1000;
  return clamp(read + type, TYPE_MIN_MS, TYPE_MAX_MS);
}

// Demora de "gravando áudio..." según el tamaño del audio (proxy de duración).
export function recordingDelayMs(audioBytes) {
  const durSec = audioBytes / AUDIO_BYTES_PER_SEC;
  return clamp(durSec * 1000 * RECORD_FRACTION, RECORD_MIN_MS, RECORD_MAX_MS);
}

// ±15% de variación para que los tiempos no sean mecánicos.
export function jitter(ms) {
  return Math.round(ms * (0.85 + Math.random() * 0.3));
}
