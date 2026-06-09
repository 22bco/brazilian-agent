"""
leads.py — Sink de leads y handoffs.

Abstracción única que usan las tools. En el paso 2 escribe a un JSONL local
(data/leads.local.jsonl), de modo que el flujo completo se pueda probar por CLI
sin cuentas externas. En el paso 3 se añade el backend de Google Sheets detrás de
esta misma interfaz, sin que `tools.py` ni `agent.py` cambien.

Para "ver el lead aparecer desde afuera" (requisito del reto), el backend de
Sheets será la vista observable; el JSONL local es el respaldo/registro.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import httpx

from app.config import LEADS_WEBAPP_SECRET, LEADS_WEBAPP_URL, ROOT

LEADS_FILE = ROOT / "data" / "leads.local.jsonl"

# Serializa id+append: sin esto, dos BackgroundTasks concurrentes calculan el
# mismo id y escriben leads colisionados.
_WRITE_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_id() -> int:
    """Id incremental simple basado en líneas existentes."""
    if not LEADS_FILE.exists():
        return 1
    with LEADS_FILE.open(encoding="utf-8") as fh:
        return sum(1 for _ in fh) + 1


def _append(record: dict) -> None:
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LEADS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _persist(record: dict) -> dict:
    """Asigna id y persiste de forma atómica (id+append bajo lock)."""
    with _WRITE_LOCK:
        record["id"] = _next_id()
        _append(record)
    _post_to_sheet(record)  # red fuera del lock
    return record


def _post_to_sheet(record: dict) -> None:
    """Envía el record al Apps Script web app. Resiliente: nunca lanza."""
    if not LEADS_WEBAPP_URL:
        return  # no configurado: solo respaldo local
    try:
        resp = httpx.post(
            LEADS_WEBAPP_URL,
            json={**record, "secret": LEADS_WEBAPP_SECRET},
            timeout=8.0,
            follow_redirects=True,  # Apps Script /exec redirige a googleusercontent
        )
        data = resp.json()
        if not data.get("ok"):
            print(f"[SHEETS] aviso: respuesta no-ok: {data}")
    except Exception as exc:  # red caída, timeout, etc. — no rompemos la conversa
        print(f"[SHEETS] error al enviar (queda en respaldo local): {exc}")


def record_lead(user_id: str, nome: str, contato: str, interesse: str) -> dict:
    record = _persist({
        "type": "lead",
        "timestamp": _now_iso(),
        "user_id": user_id,
        "nome": nome,
        "contato": contato,
        "interesse": interesse,
    })
    print(f"[LEAD] #{record['id']} {nome} | {contato} | {interesse}")
    return record


def record_handoff(user_id: str, motivo: str, resumo: str) -> dict:
    record = _persist({
        "type": "handoff",
        "timestamp": _now_iso(),
        "user_id": user_id,
        "motivo": motivo,
        "resumo": resumo,
    })
    print(f"[HANDOFF] {motivo} | {resumo}")
    return record
