"""
kapso.py - Adaptador del canal WhatsApp vía Kapso.

Aísla TODO lo específico de Kapso: parseo del webhook entrante, verificación de
firma, y envío de mensajes salientes. El resto del sistema (agent, main) solo
habla en términos de (user_id, texto), así que cambiar de canal = otro adaptador.

Formatos según la documentación de Kapso:
  - Entrante (whatsapp.message.received):
      body = { "event": "...", "data": { "message": {...}, "conversation": {...},
               "phone_number_id": "..." } }
    Campos: data.message.from, data.message.text.body, data.message.id,
            data.phone_number_id
  - Saliente:
      POST {base}/meta/whatsapp/{version}/{phone_number_id}/messages
      header X-API-Key; body Cloud-API estándar (type=text).
  - Firma: HMAC-SHA256 del cuerpo crudo, header X-Webhook-Signature.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import httpx

from app.config import (
    KAPSO_API_KEY,
    KAPSO_API_VERSION,
    KAPSO_BASE_URL,
    KAPSO_PHONE_NUMBER_ID,
    KAPSO_WEBHOOK_SECRET,
)

INBOUND_EVENT = "whatsapp.message.received"


@dataclass
class IncomingMessage:
    user_id: str           # número del remitente (clave de memoria)
    text: str              # cuerpo del mensaje
    message_id: str        # wamid, para idempotencia
    phone_number_id: str   # número de negocio que recibió (para responder)


def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verifica el header X-Webhook-Signature (HMAC-SHA256). Si no hay secreto
    configurado, no se exige firma (útil en dev/sandbox)."""
    if not KAPSO_WEBHOOK_SECRET:
        return True
    if not signature:
        return False
    expected = hmac.new(
        KAPSO_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    # algunos emisores prefijan "sha256=" - toleramos ambas formas
    received = signature.split("=", 1)[-1].strip()
    return hmac.compare_digest(expected, received)


def parse_incoming(body: dict) -> IncomingMessage | None:
    """Extrae un mensaje de texto entrante; devuelve None si el evento no aplica
    (otro tipo de evento, mensaje sin texto, eco saliente, etc.)."""
    if body.get("event") and body.get("event") != INBOUND_EVENT:
        return None

    data = body.get("data", body)  # tolera payload con o sin envoltura "data"
    message = data.get("message") or {}

    # ignorar lo que no sea texto entrante
    if message.get("type") not in (None, "text"):
        return None
    if (message.get("kapso") or {}).get("direction") == "outbound":
        return None

    text = (message.get("text") or {}).get("body", "").strip()
    sender = message.get("from")
    if not text or not sender:
        return None

    phone_number_id = (
        data.get("phone_number_id")
        or (data.get("conversation") or {}).get("phone_number_id")
        or KAPSO_PHONE_NUMBER_ID
        or ""
    )
    return IncomingMessage(
        user_id=sender,
        text=text,
        message_id=message.get("id", ""),
        phone_number_id=phone_number_id,
    )


def send_text(to: str, text: str, phone_number_id: str | None = None) -> None:
    """Envía un mensaje de texto por la API de Kapso."""
    pnid = phone_number_id or KAPSO_PHONE_NUMBER_ID
    if not KAPSO_API_KEY or not pnid:
        print(f"[KAPSO] (simulado, sin credenciales) → {to}: {text}")
        return

    url = f"{KAPSO_BASE_URL}/meta/whatsapp/{KAPSO_API_VERSION}/{pnid}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={"X-API-Key": KAPSO_API_KEY, "Content-Type": "application/json"},
            timeout=15.0,
        )
        if resp.status_code >= 300:
            print(f"[KAPSO] error {resp.status_code}: {resp.text[:300]}")
    except Exception as exc:
        print(f"[KAPSO] fallo al enviar: {exc}")
