"""
build_catalog.py - Limpia data/trips.csv (operacional, "sucio") y produce
data/trips.clean.json, el catálogo estructurado que el agente usa para grounding.

Qué resuelve de la suciedad del CSV (documentada en el README del reto):
  - `place` viene como slug ("torres-del-paine") -> nombre legible con acentos.
  - las horas mezclan formatos ("14:00", "8:00", "14:40:00", "11:10:00 AM - 12.54",
    "1.15") -> se normalizan a HH:MM 24h cuando es inequívoco; si es ambiguo se
    conserva el texto crudo y NO se inventa.
  - la duración del viaje vive solo en la *lead row* (primera fila de cada viaje):
    su `n_days` es la duración que el operador anuncia (coincide con el ejemplo del
    README, donde Puerto Varas/Chiloé/Cochamó = "8 dias").
  - filas que abarcan un rango (hospedaje, seguro, gear) se separan del itinerario
    día-a-día; los eventos puntuales (actividad, traslado, vuelo) se agrupan por día.

Principio: este script NO traduce ni reescribe el campo `detail` (fuente de verdad).
El agente lo reformula a pt-BR cálido en tiempo de conversación, siempre anclado aquí.

Uso:  python3 scripts/build_catalog.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "trips.csv"
OUT_PATH = ROOT / "data" / "trips.clean.json"

# --- Mapeos de presentación (derivados de los datos, no inventados) ----------

# slug de `place` -> nombre legible con ortografía/acentos correctos.
PLACE_NAMES = {
    "san-pedro-de-atacama": "San Pedro de Atacama",
    "santiago": "Santiago",
    "casa-blanca": "Valle de Casablanca",
    "casablanca": "Valle de Casablanca",
    "colchagua": "Valle de Colchagua",
    "santa-cruz": "Santa Cruz",
    "mendoza": "Mendoza",
    "puerto-natales": "Puerto Natales",
    "torres-del-paine": "Torres del Paine",
    "puerto-varas": "Puerto Varas",
    "chiloe": "Chiloé",
    "cochamo": "Cochamó",
    "valle-nevado": "Valle Nevado",
    "farellones": "Farellones",
}

# trip_id -> nombre amistoso para la conversación (derivado del tema/lugares).
TRIP_NAMES = {
    "Atacama_Trip_Web": "Atacama",
    "Chile_Argentina_Wine_Valleys_Web": "Vales do Vinho - Chile & Argentina",
    "Patagonian_Chile_Trek_Web": "Trekking na Patagônia chilena",
    "PuertoVaras_Chiloe_Cochamo": "Puerto Varas, Chiloé & Cochamó",
    "Ski_Vinho": "Ski & Vinho",
}

# categoría cruda de `item` -> etiqueta pt-BR (conveniencia para el agente).
CATEGORY_PT = {
    "accommodation": "hospedagem",
    "transport": "transporte",
    "activity": "atividade",
    "flight": "voo",
    "culinary_experience": "experiência gastronômica",
    "meal": "refeição",
    "insurance": "seguro",
    "gear": "equipamento",
    "merch": "kit DipYourTrip",
}

# categorías que representan cobertura/equipo a lo largo de todo el viaje,
# no segmentos de hospedaje reales (se listan aparte, en "incluído").
COVERAGE_CATEGORIES = {"insurance", "merch", "gear"}


def slug_to_name(slug: str) -> str:
    """Convierte un slug de lugar a nombre legible; con fallback title-case."""
    if not slug:
        return ""
    if slug in PLACE_NAMES:
        return PLACE_NAMES[slug]
    return slug.replace("-", " ").title()


def parse_hour(raw: str | None):
    """
    Normaliza una hora a 'HH:MM' (24h) cuando es inequívoco.

    Devuelve (hora_normalizada_o_None, texto_crudo_o_None).
    - Si el valor es ambiguo (p.ej. "1.15" sin AM/PM), devuelve (None, raw)
      para no inventar un horario.
    - Si la celda trae dos horas ("11:10:00 AM - 12.54"), parsea solo la primera
      como inicio; la segunda la maneja el llamador si la necesita.
    """
    if raw is None:
        return None, None
    raw = raw.strip()
    if not raw:
        return None, None

    # Caso celda combinada "inicio - fin": tomamos el primer tramo como inicio.
    first = raw.split(" - ")[0].strip() if " - " in raw else raw

    norm = _normalize_single(first)
    if norm is None:
        return None, raw  # ambiguo: conservamos el crudo, no inventamos
    return norm, raw if raw != norm else None


def parse_end_from_combined(raw: str | None):
    """Si una celda start_hour trae 'inicio - fin', extrae el fin normalizado."""
    if not raw or " - " not in raw:
        return None
    tail = raw.split(" - ", 1)[1].strip()
    return _normalize_single(tail)


def _normalize_single(token: str):
    """Normaliza un único token horario a 'HH:MM' 24h, o None si es ambiguo."""
    if not token:
        return None
    t = token.strip().upper()

    # AM/PM: detectamos y removemos SOLO lo que matcheó (incluso pegado a dígito,
    # ej. "7PM"). Antes un .replace ciego corrompía esos casos.
    ampm = None
    m = re.search(r"([AP])M", t)
    if m:
        ampm = m.group(1) + "M"
        t = (t[: m.start()] + t[m.end():]).strip()

    # separadores: ':' o '.' -> normalizamos a ':'
    t = t.replace(".", ":")
    parts = [p for p in t.split(":") if p != ""]
    if not parts or not parts[0].isdigit():
        return None

    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0

    # Sin AM/PM y hora < 6: realmente ambiguo (ej. "1.15" -> ¿01:15 o 13:15?).
    # Un "06:30"/"6:30" en un dataset 24h sí es inequívoco (tour de madrugada).
    if ampm is None and hour < 6:
        return None

    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def to_int(value: str | None):
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def build():
    with CSV_PATH.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    # Agrupar preservando el orden de aparición de cada viaje.
    trips: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in rows:
        tid = r["trip_id"]
        if tid not in trips:
            trips[tid] = []
            order.append(tid)
        trips[tid].append(r)

    catalog = {"trips": []}

    for tid in order:
        block = trips[tid]
        lead = block[0]  # la lead row: su n_days = duración anunciada
        duration_days = to_int(lead["n_days"])

        places_seen: list[str] = []
        accommodations = []
        coverage = []  # seguro / gear / merch
        by_day: dict[int, list[dict]] = {}
        flights = []
        max_content_day = 0  # último día con contenido real (sin cobertura)
        nights_booked = 0    # suma de noches de hospedaje

        for r in block:
            category = r["item"].strip()
            start_day = to_int(r["start_day"]) or 0
            end_day = to_int(r["end_day"]) or start_day
            n_days = to_int(r["n_days"]) or 0
            place_slug = r["place"].strip()
            place = slug_to_name(place_slug)
            detail = r["detail"].strip()
            if category not in COVERAGE_CATEGORIES:
                max_content_day = max(max_content_day, end_day)

            if place and place not in places_seen:
                places_seen.append(place)

            start_h, start_raw = parse_hour(r["start_hour"])
            end_h, _ = parse_hour(r["end_hour"])
            # algunas celdas meten el fin dentro de start_hour ("inicio - fin")
            combined_end = parse_end_from_combined(r["start_hour"])
            if combined_end and not end_h:
                end_h = combined_end

            entry = {
                "place": place,
                "place_slug": place_slug,
                "category": category,
                "category_pt": CATEGORY_PT.get(category, category),
                "detail": detail,
            }
            if start_h:
                entry["start"] = start_h
            if end_h:
                entry["end"] = end_h
            if start_raw and not start_h:
                entry["time_raw"] = start_raw  # horario crudo no normalizable

            if category in COVERAGE_CATEGORIES:
                coverage.append({
                    "category": category,
                    "category_pt": CATEGORY_PT.get(category, category),
                    "detail": detail,
                })
                continue

            if category == "accommodation":
                nights_booked += n_days
                accommodations.append({
                    "place": place,
                    "name": detail,
                    "from_day": start_day,
                    "to_day": end_day,
                    "nights": n_days,
                })
                continue

            if category == "flight":
                flights.append({**entry, "day": start_day})

            # eventos puntuales y multi-día no-hospedaje van al día de inicio
            by_day.setdefault(start_day, []).append(entry)

        # ordenar eventos de cada día por hora (los sin hora, al final)
        for day in by_day:
            by_day[day].sort(key=lambda e: e.get("start", "99:99"))

        itinerary = [
            {"day": day, "items": by_day[day]}
            for day in sorted(by_day)
        ]

        # Duración: confiamos en el n_days de la lead row SOLO si concuerda con las
        # noches realmente reservadas. Si no (caso Ski: 7 vs 4), la marcamos como
        # ambigua y el agente describe por itinerario en vez de afirmar un número.
        confident = (duration_days is not None and duration_days == nights_booked)
        duration = {
            "advertised_days": duration_days,
            "nights_booked": nights_booked,
            "content_last_day": max_content_day,
            "confident": confident,
        }
        if not confident:
            duration["note"] = (
                f"Dado inconsistente na fonte: a 'lead row' indica {duration_days} dias, "
                f"mas o programa só tem hospedagem e atividades até o dia {max_content_day} "
                f"({nights_booked} diárias). NÃO afirmar um número fixo de dias; "
                f"descrever pelo itinerário e, se preciso, confirmar com um humano."
            )

        catalog["trips"].append({
            "id": tid,
            "name": TRIP_NAMES.get(tid, tid),
            "duration": duration,
            "places": places_seen,
            "accommodations": accommodations,
            "included": coverage,
            "flights": flights,
            "itinerary": itinerary,
        })

    OUT_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Resumen por consola para validación rápida.
    print(f"OK -> {OUT_PATH.relative_to(ROOT)}")
    for t in catalog["trips"]:
        d = t["duration"]
        flag = "OK " if d["confident"] else "AMB"
        print(
            f"  • {t['name']:<38} "
            f"[{flag}] anunc={d['advertised_days']}d  noites={d['nights_booked']}  "
            f"último={d['content_last_day']}d  "
            f"lugares={len(t['places'])}  hosp={len(t['accommodations'])}  "
            f"voos={len(t['flights'])}"
        )


if __name__ == "__main__":
    build()
