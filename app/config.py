"""
config.py — Configuración central leída de variables de entorno (.env).

Diseño: el proveedor de LLM es intercambiable por env var (DeepSeek por defecto,
OpenAI como alternativa) sin tocar el resto del código. Todo se resuelve a una
tripleta {api_key, base_url, model} que `agent.py` pasa al SDK de OpenAI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()  # carga .env si existe (no falla si no está)
except ImportError:  # python-dotenv aún no instalado: seguimos con os.environ
    pass

ROOT = Path(__file__).resolve().parent.parent

# Valores por defecto por proveedor. DeepSeek es OpenAI-compatible: mismo SDK,
# solo cambia base_url y la env var de la key.
_PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "base_url": None,  # default del SDK
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str | None
    model: str
    temperature: float


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def load_llm_config() -> LLMConfig:
    provider = (_env("LLM_PROVIDER", "deepseek") or "deepseek").lower()
    if provider not in _PROVIDER_DEFAULTS:
        raise ValueError(
            f"LLM_PROVIDER='{provider}' no soportado. "
            f"Usa uno de: {', '.join(_PROVIDER_DEFAULTS)}"
        )
    defaults = _PROVIDER_DEFAULTS[provider]

    # La key puede venir de la env var del proveedor o de un LLM_API_KEY genérico.
    api_key = _env(defaults["key_env"]) or _env("LLM_API_KEY")
    base_url = _env("LLM_BASE_URL", defaults["base_url"])
    model = _env("LLM_MODEL", defaults["model"])
    temperature = float(_env("LLM_TEMPERATURE", "0.6"))

    return LLMConfig(
        provider=provider,
        api_key=api_key or "",
        base_url=base_url,
        model=model,
        temperature=temperature,
    )


# --- Otros ajustes (leads, kapso, handoff) — usados en pasos posteriores ----

# Leads → Google Sheets vía Apps Script web app (POST). Si LEADS_WEBAPP_URL está
# vacío, leads.py cae al respaldo local JSONL sin romper nada.
LEADS_WEBAPP_URL = _env("LEADS_WEBAPP_URL")
LEADS_WEBAPP_SECRET = _env("LEADS_WEBAPP_SECRET", "")
KAPSO_API_KEY = _env("KAPSO_API_KEY")
KAPSO_WEBHOOK_SECRET = _env("KAPSO_WEBHOOK_SECRET")
KAPSO_BASE_URL = _env("KAPSO_BASE_URL", "https://api.kapso.ai")
KAPSO_API_VERSION = _env("KAPSO_API_VERSION", "v24.0")
KAPSO_PHONE_NUMBER_ID = _env("KAPSO_PHONE_NUMBER_ID")
HANDOFF_CONTACT = _env("HANDOFF_CONTACT", "(handoff no configurado)")

# Token opcional para autenticar el endpoint canal-neutral /message (usado por el
# sidecar Baileys). Si está vacío, no se exige (cómodo en dev local).
BRIDGE_TOKEN = _env("BRIDGE_TOKEN", "")

CATALOG_PATH = ROOT / "data" / "trips.clean.json"
SESSIONS_DIR = ROOT / "data" / "sessions"
