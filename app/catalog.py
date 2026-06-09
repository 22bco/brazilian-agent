"""
catalog.py - Carga data/trips.clean.json y lo renderiza a texto compacto en
pt-BR para inyectarlo en el system prompt.

Por qué texto y no JSON crudo: el modelo lo lee mejor, gasta menos tokens y
deja explícita la jerarquía (viaje → dias → itens). El texto sigue siendo la
fuente de verdad: el agente solo puede afirmar lo que aparece aquí.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.config import CATALOG_PATH


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _diarias(n: int) -> str:
    return f"{n} diária" if n == 1 else f"{n} diárias"


def _fmt_time(item: dict) -> str:
    if "start" in item and "end" in item:
        return f"{item['start']}–{item['end']} "
    if "start" in item:
        return f"{item['start']} "
    if "time_raw" in item:
        return f"(~{item['time_raw']}) "
    return ""


def _fmt_duration(trip: dict) -> str:
    d = trip["duration"]
    if d["confident"]:
        return f"{d['advertised_days']} dias ({_diarias(d['nights_booked'])})"
    # Caso ambiguo (Ski): no afirmamos número fijo.
    return (
        f"duração a confirmar - programa com hospedagem/atividades até o dia "
        f"{d['content_last_day']} ({_diarias(d['nights_booked'])}). "
        f"[ATENÇÃO: não afirmar um número fixo de dias]"
    )


def render_trip(trip: dict) -> str:
    """Renderiza un viaje a texto pt-BR para el prompt."""
    lines: list[str] = []
    lines.append(f"### {trip['name']}  (id: {trip['id']})")
    lines.append(f"- Duração: {_fmt_duration(trip)}")
    lines.append(f"- Lugares: {', '.join(trip['places'])}")

    if trip["accommodations"]:
        lines.append("- Hospedagem:")
        for a in trip["accommodations"]:
            rng = (
                f"dia {a['from_day']}"
                if a["from_day"] == a["to_day"]
                else f"dias {a['from_day']}–{a['to_day']}"
            )
            lines.append(f"    · {a['name']} em {a['place']} ({rng}, {_diarias(a['nights'])})")

    if trip["included"]:
        inc = "; ".join(f"{c['category_pt']}: {c['detail']}" for c in trip["included"])
        lines.append(f"- Incluído (cobertura/kit): {inc}")

    if trip["flights"]:
        lines.append("- Voos:")
        for f in trip["flights"]:
            lines.append(f"    · dia {f['day']}: {_fmt_time(f)}{f['detail']}")

    lines.append("- Itinerário por dia:")
    for day in trip["itinerary"]:
        lines.append(f"    Dia {day['day']}:")
        for it in day["items"]:
            lines.append(
                f"      - [{it['category_pt']}] {_fmt_time(it)}"
                f"{it['detail']} ({it['place']})"
            )
    return "\n".join(lines)


def render_catalog() -> str:
    """Renderiza el catálogo completo (los 5 viajes) para el system prompt."""
    catalog = load_catalog()
    blocks = [render_trip(t) for t in catalog["trips"]]
    return "\n\n".join(blocks)


def trip_index() -> str:
    """Índice corto de viajes (para referencias rápidas)."""
    catalog = load_catalog()
    return "\n".join(f"- {t['name']} (id: {t['id']})" for t in catalog["trips"])


if __name__ == "__main__":
    print(render_catalog())
