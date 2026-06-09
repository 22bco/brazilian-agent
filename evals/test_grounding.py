"""
test_grounding.py - Wrapper de pytest sobre el arnés de grounding.

Ejecuta cada caso adversarial como un test parametrizado. Se salta si no hay
API key configurada (los evals llaman al LLM real).

    pytest evals/test_grounding.py -v
"""

from __future__ import annotations

import pytest

from app.config import load_llm_config
from evals.cases import CASES
from evals.harness import run_case

_has_key = bool(load_llm_config().api_key)


@pytest.mark.skipif(not _has_key, reason="sem API key do LLM (.env)")
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_grounding(case: dict) -> None:
    result = run_case(case)
    assert result.passed, f"{case['id']}: {result.judge_reason}\n→ {result.response}"
