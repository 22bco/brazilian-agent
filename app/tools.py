"""
tools.py — Definición y despacho de las tools (function-calling) del agente.

Dos acciones de backend:
  - registrar_lead: captura nombre + contacto + interés del viajero.
  - solicitar_handoff: marca que la conversación debe pasar a un humano.

Para mantener el agente desacoplado del almacenamiento, ambas delegan en
`leads.record_lead` / `leads.record_handoff`. En el paso 2 ese sink escribe a un
JSONL local (testable sin cuentas externas); en el paso 3 el mismo sink pasa a
escribir en Google Sheets sin que el agente cambie.
"""

from __future__ import annotations

import json

from app import leads

# Esquemas en formato OpenAI/DeepSeek function-calling.
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "registrar_lead",
            "description": (
                "Registra um viajante interessado. Chame quando tiver nome e contato "
                "e a pessoa demonstrar intenção real (ex.: perguntou preço, quer "
                "avançar). Não invente dados: peça o que faltar antes de chamar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do viajante."},
                    "contato": {
                        "type": "string",
                        "description": "Email ou número de WhatsApp informado.",
                    },
                    "interesse": {
                        "type": "string",
                        "description": (
                            "Resumo curto: viagem de interesse, dias, perfil, época "
                            "se mencionada."
                        ),
                    },
                },
                "required": ["nome", "contato", "interesse"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "solicitar_handoff",
            "description": (
                "Passa a conversa para uma pessoa do time. Chame em pedido de preço/"
                "fechamento, datas reais, ou qualquer pedido fora do catálogo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "motivo": {
                        "type": "string",
                        "description": "Por que escalar (ex.: 'pedido de preço').",
                    },
                    "resumo": {
                        "type": "string",
                        "description": "Resumo do contexto para o humano assumir.",
                    },
                },
                "required": ["motivo", "resumo"],
            },
        },
    },
]


def handle_tool_call(name: str, arguments: str, user_id: str) -> str:
    """Ejecuta una tool y devuelve el resultado (texto) para el modelo."""
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return "ERRO: argumentos inválidos (não era JSON)."

    if name == "registrar_lead":
        lead = leads.record_lead(
            user_id=user_id,
            nome=args.get("nome", ""),
            contato=args.get("contato", ""),
            interesse=args.get("interesse", ""),
        )
        return (
            f"Lead registrado com sucesso (id {lead['id']}). "
            "Confirme ao viajante que uma pessoa do time vai chamar."
        )

    if name == "solicitar_handoff":
        leads.record_handoff(
            user_id=user_id,
            motivo=args.get("motivo", ""),
            resumo=args.get("resumo", ""),
        )
        return "Handoff acionado. Avise ao viajante que um humano vai assumir em breve."

    return f"ERRO: tool desconhecida '{name}'."
