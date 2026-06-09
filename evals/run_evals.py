"""
run_evals.py - Corre todos los casos de grounding y emite un reporte.

Uso:
    python3 -m evals.run_evals

Sale con código !=0 si algún caso falla (útil para CI).
"""

from __future__ import annotations

import sys

from evals.cases import CASES
from evals.harness import run_case


def main() -> int:
    print(f"Rodando {len(CASES)} casos de grounding...\n")
    results = [run_case(c) for c in CASES]

    passed = 0
    for r in results:
        mark = "✅ PASS" if r.passed else "❌ FAIL"
        if r.passed:
            passed += 1
        print(f"{mark}  {r.case_id}")
        print(f"      motivo: {r.judge_reason}")
        snippet = r.response.replace("\n", " ")[:140]
        print(f"      resposta: {snippet}…\n")

    total = len(results)
    print(f"── Resultado: {passed}/{total} passaram ──")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
