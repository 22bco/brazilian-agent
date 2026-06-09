"""
agent.py — Loop del agente: LLM (DeepSeek vía SDK OpenAI-compatible) + tool-calling.

Punto de entrada principal: `respond(user_id, user_text) -> str`.
- Carga la conversación del usuario (memoria por número, cross-session).
- Arma [system prompt + historial + nuevo mensaje] y llama al LLM.
- Si el LLM pide tools, las ejecuta, devuelve resultados y vuelve a llamar.
- Persiste la conversación y devuelve la respuesta en pt-BR.

El canal (WhatsApp/CLI) es indiferente: solo entrega texto y un user_id.
"""

from __future__ import annotations

from openai import OpenAI

from app.config import load_llm_config
from app.memory import Conversation, MemoryStore
from app.prompt import build_system_prompt
from app.tools import TOOLS_SCHEMA, handle_tool_call

# Tope de iteraciones de tool-calling por turno (evita loops infinitos).
MAX_TOOL_ROUNDS = 5

_config = load_llm_config()
_store = MemoryStore()
_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Cliente LLM compartido, con guard de API key. Reutilizado por los evals."""
    global _client
    if _client is None:
        if not _config.api_key:
            raise RuntimeError(
                "Falta la API key del LLM. Pon DEEPSEEK_API_KEY en tu archivo .env "
                "(copia env.example a .env)."
            )
        _client = OpenAI(api_key=_config.api_key, base_url=_config.base_url)
    return _client


def _system_message() -> dict:
    # build_system_prompt está cacheado (contenido estático).
    return {"role": "system", "content": build_system_prompt()}


def _complete(messages: list[dict], use_tools: bool = True):
    kwargs = {
        "model": _config.model,
        "temperature": _config.temperature,
        "messages": messages,
    }
    if use_tools:
        kwargs["tools"] = TOOLS_SCHEMA
    return get_client().chat.completions.create(**kwargs)


def respond(user_id: str, user_text: str) -> str:
    """Procesa un mensaje entrante y devuelve la respuesta del agente.

    El lock por user_id serializa turnos del mismo número (load→…→save atómico).
    En la última ronda llamamos sin tools, lo que fuerza una respuesta en lenguaje
    natural y cierra el loop sin un camino de fallback duplicado.
    """
    with _store.lock(user_id):
        conv: Conversation = _store.load(user_id)
        conv.add("user", user_text)
        system = _system_message()  # una vez por turno

        for round_i in range(MAX_TOOL_ROUNDS):
            last_round = round_i == MAX_TOOL_ROUNDS - 1
            messages = [system] + conv.for_llm()
            msg = _complete(messages, use_tools=not last_round).choices[0].message

            if not msg.tool_calls:
                reply = (msg.content or "").strip()
                conv.add("assistant", reply)
                _store.save(conv)
                return reply

            # El modelo pidió tools: registrar la intención y ejecutarlas.
            conv.add(
                "assistant",
                msg.content or "",
                tool_calls=[
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            )
            for tc in msg.tool_calls:
                # Un fallo de una tool no debe crashear el turno: devolvemos el
                # error como resultado para que el modelo lo maneje y responda.
                try:
                    result = handle_tool_call(
                        tc.function.name, tc.function.arguments, user_id
                    )
                except Exception as exc:  # noqa: BLE001 — robustez deliberada
                    result = f"ERRO ao executar a ação '{tc.function.name}': {exc}"
                conv.add("tool", result, tool_call_id=tc.id)

        # Inalcanzable: la última ronda (use_tools=False) siempre retorna arriba.
        raise RuntimeError("loop de tools no convergió")
