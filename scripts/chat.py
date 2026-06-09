"""
chat.py — REPL local para conversar con el agente sin WhatsApp.

Uso:
    python3 -m scripts.chat            # número de prueba por defecto
    python3 -m scripts.chat +5511999   # simula un número específico

Comandos dentro del REPL:
    /reset   borra la memoria del número actual
    /sair    sale
"""

from __future__ import annotations

import sys

from app.agent import respond
from app.config import SESSIONS_DIR
from app.memory import _safe_id


def main() -> None:
    user_id = sys.argv[1] if len(sys.argv) > 1 else "+5511000000000"
    print(f"💬 Conversa com o agente DYT (número simulado: {user_id})")
    print("   /reset para limpar a memória · /sair para sair\n")

    while True:
        try:
            text = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text == "/sair":
            break
        if text == "/reset":
            path = SESSIONS_DIR / f"{_safe_id(user_id)}.json"
            path.unlink(missing_ok=True)
            print("(memória apagada)\n")
            continue

        reply = respond(user_id, text)
        print(f"agente> {reply}\n")


if __name__ == "__main__":
    main()
