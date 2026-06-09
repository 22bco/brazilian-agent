"""
memory.py - Estado de conversación por número de WhatsApp.

Guarda el historial de mensajes (para discovery multi-turno) y persiste en disco
como JSON, de modo que la conversación sobreviva reinicios del proceso
(memoria cross-session, un plus que el reto valora).

Implementación deliberadamente simple (un archivo por número). Para producción se
cambiaría por Redis/Postgres, pero para el alcance del reto esto es legible y basta.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from app.config import SESSIONS_DIR

# Cuántos mensajes mandamos al LLM por turno. Con 5 viajes el catálogo ya domina
# el prompt; un historial acotado mantiene costo/latencia bajos.
MAX_HISTORY = 40
# Cota de mensajes persistidos en disco (evita crecimiento sin límite).
MAX_STORED = 200


def _safe_id(user_id: str) -> str:
    """Convierte un id (número) en nombre de archivo seguro."""
    return re.sub(r"[^0-9A-Za-z_-]", "_", user_id)


def _safe_window(messages: list[dict], limit: int) -> list[dict]:
    """Últimos `limit` mensajes, pero empezando en un mensaje 'user' para no
    cortar una secuencia assistant(tool_calls)→tool por la mitad (el API exige
    que cada 'tool' siga a su 'assistant' con tool_calls)."""
    window = messages[-limit:]
    for i, msg in enumerate(window):
        if msg.get("role") == "user":
            return window[i:]
    return window  # fallback: no hay 'user' en la ventana (no debería ocurrir)


class Conversation:
    def __init__(self, user_id: str, messages: list[dict] | None = None):
        self.user_id = user_id
        self.messages: list[dict] = messages or []

    def add(self, role: str, content, **extra) -> None:
        msg = {"role": role, "content": content}
        msg.update(extra)  # p.ej. tool_calls, tool_call_id
        self.messages.append(msg)

    def for_llm(self) -> list[dict]:
        """Historial acotado, sin romper secuencias de tools."""
        return _safe_window(self.messages, MAX_HISTORY)


class MemoryStore:
    def __init__(self, directory: Path = SESSIONS_DIR):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        # Locks por user_id: serializan los turnos del MISMO número (FastAPI corre
        # los BackgroundTasks en hilos, así que dos mensajes seguidos del mismo
        # usuario podrían pisarse en el read-modify-write). Distintos usuarios no
        # se bloquean entre sí.
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def lock(self, user_id: str) -> threading.Lock:
        with self._locks_guard:
            lk = self._locks.get(user_id)
            if lk is None:
                lk = threading.Lock()
                self._locks[user_id] = lk
            return lk

    def _path(self, user_id: str) -> Path:
        return self.dir / f"{_safe_id(user_id)}.json"

    def load(self, user_id: str) -> Conversation:
        path = self._path(user_id)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return Conversation(user_id, data.get("messages", []))
        return Conversation(user_id)

    def save(self, conv: Conversation) -> None:
        path = self._path(conv.user_id)
        # Persistimos una ventana acotada (sin romper secuencias de tools) para
        # que el archivo no crezca indefinidamente.
        messages = _safe_window(conv.messages, MAX_STORED)
        path.write_text(
            json.dumps({"user_id": conv.user_id, "messages": messages},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
