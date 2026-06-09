"""
main.py - Webhook FastAPI que conecta Kapso (WhatsApp) con el agente.

Flujo:
  POST /webhook  → verifica firma → parsea mensaje entrante → ACK 200 inmediato
                   → en background: agent.respond() → kapso.send_text()
  POST /message  → endpoint canal-neutral síncrono {user_id, text} → {reply}.
                   Lo usa el sidecar Baileys (canal alternativo); como Baileys no
                   tiene el límite de 5s de Kapso, aquí responde síncrono.
  GET  /health   → healthcheck

Por qué background (en /webhook): Kapso espera un 2xx en <5s, pero la llamada al
LLM puede tardar más. Respondemos rápido y enviamos la respuesta por la API de
Kapso cuando el agente termina (de todos modos respondemos por API, no por el body).

Idempotencia: descartamos message_id ya vistos (Kapso puede reintentar).
"""

from __future__ import annotations

from collections import OrderedDict

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel

from app.agent import respond
from app.channels import kapso
from app.config import BRIDGE_TOKEN

app = FastAPI(title="Dip Your Trip - Brazilian WhatsApp Agent")

# message_ids procesados (evita doble respuesta en reintentos de Kapso, que son
# frecuentes porque la llamada al LLM suele superar los 5s de su webhook).
# LRU: al llegar al tope descartamos el MÁS VIEJO, no todo el set (si lo
# vaciáramos, un reintento inmediato volvería a procesarse).
# Para producción/multi-worker se usaría un store con TTL compartido.
_seen_messages: "OrderedDict[str, bool]" = OrderedDict()
_SEEN_MAX = 5000


def _already_processed(message_id: str) -> bool:
    if not message_id:
        return False
    if message_id in _seen_messages:
        _seen_messages.move_to_end(message_id)
        return True
    _seen_messages[message_id] = True
    if len(_seen_messages) > _SEEN_MAX:
        _seen_messages.popitem(last=False)  # descarta el más antiguo
    return False


def _process(msg: kapso.IncomingMessage) -> None:
    """Trabajo pesado fuera del ciclo del webhook."""
    reply = respond(msg.user_id, msg.text)
    kapso.send_text(msg.user_id, reply, msg.phone_number_id)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "dyt-brazilian-agent"}


class MessageIn(BaseModel):
    user_id: str
    text: str


@app.post("/message")
def message(
    payload: MessageIn,
    x_bridge_token: str | None = Header(default=None),
) -> dict:
    """Endpoint canal-neutral síncrono. El cerebro es el mismo `respond`; cualquier
    canal que hable (user_id, text) puede usarlo (p.ej. el sidecar Baileys)."""
    if BRIDGE_TOKEN and x_bridge_token != BRIDGE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid bridge token")
    reply = respond(payload.user_id, payload.text)
    return {"reply": reply}


@app.post("/webhook")
async def webhook(
    request: Request,
    background: BackgroundTasks,
    x_webhook_signature: str | None = Header(default=None),
) -> Response:
    raw = await request.body()

    if not kapso.verify_signature(raw, x_webhook_signature):
        return Response(status_code=401, content="invalid signature")

    body = await request.json()
    msg = kapso.parse_incoming(body)

    # Eventos que no son texto entrante (status, ecos, etc.): ACK silencioso.
    if msg is None:
        return Response(status_code=200, content="ignored")

    if _already_processed(msg.message_id):
        return Response(status_code=200, content="duplicate")

    background.add_task(_process, msg)
    return Response(status_code=200, content="ok")
