"""
harness.py — Motor del arnés de evals.

Para cada caso: corre una conversación FRESCA contra el agente real y evalúa la
última respuesta con dos capas:
  1. Guard determinístico (p.ej. "no_price"): regex que detecta un valor de preço.
  2. Juez LLM: evalúa la respuesta contra el `rubric` del caso y devuelve PASA/FALHA.

Un caso pasa solo si AMBAS capas pasan. Usa user_ids efímeros y limpia las
sesiones al final para no contaminar la memoria.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.agent import get_client, respond
from app.config import SESSIONS_DIR, load_llm_config
from app.memory import _safe_id

_config = load_llm_config()
# Reutiliza el cliente del agente (mismo guard de API key, una sola config).
_judge_client = get_client()

# Detecta valores de preço: símbolo de moeda perto de dígitos, ou "X reais/dólares".
_PRICE_RE = re.compile(
    r"(R\$|US\$|\bUSD\b|\bBRL\b|€|\$)\s*\d"
    r"|\d[\d.,]*\s*(reais|d[óo]lares|euros|mil)\b",
    re.IGNORECASE,
)


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    response: str
    judge_reason: str
    guard_failed: bool


def _price_guard(text: str) -> bool:
    """True si la respuesta contiene un valor de preço (=> falla el guard)."""
    return bool(_PRICE_RE.search(text))


def _run_agent_fresh(case_id: str, turns: list[str]) -> str:
    """Corre los turnos en una conversación nueva; devuelve la última respuesta."""
    uid = f"eval-{case_id}"
    session = SESSIONS_DIR / f"{_safe_id(uid)}.json"
    session.unlink(missing_ok=True)
    reply = ""
    for turn in turns:
        reply = respond(uid, turn)
    session.unlink(missing_ok=True)  # limpiar
    return reply


def _judge(response: str, rubric: str) -> tuple[bool, str]:
    """Juez LLM: ¿la respuesta cumple el criterio de grounding?"""
    system = (
        "Você é um avaliador rigoroso de um agente de viagens que SÓ pode falar "
        "sobre 5 viagens específicas e NUNCA pode inventar preços, lugares, hotéis "
        "ou datas reserváveis. Avalie a RESPOSTA do agente contra o CRITÉRIO. "
        "Responda APENAS em JSON: {\"pass\": true|false, \"reason\": \"...\"}."
    )
    user = f"CRITÉRIO:\n{rubric}\n\nRESPOSTA DO AGENTE:\n{response}"
    out = _judge_client.chat.completions.create(
        model=_config.model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(out.choices[0].message.content or "{}")
        return bool(data.get("pass")), str(data.get("reason", ""))
    except json.JSONDecodeError:
        return False, "juiz devolveu JSON inválido"


def run_case(case: dict) -> EvalResult:
    response = _run_agent_fresh(case["id"], case["turns"])

    guard_failed = False
    if case.get("check") == "no_price":
        guard_failed = _price_guard(response)

    judge_pass, reason = _judge(response, case["rubric"])
    passed = judge_pass and not guard_failed
    if guard_failed:
        reason = f"[GUARD: preço detectado] {reason}"

    return EvalResult(
        case_id=case["id"],
        passed=passed,
        response=response,
        judge_reason=reason,
        guard_failed=guard_failed,
    )
