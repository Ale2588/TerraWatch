"""
Fonte: ISPRA — Rapporto sul Dissesto Idrogeologico in Italia
Aggiornamento: annuale (pubblicazione ISPRA)
Granularità: regionale (MVP) → comunale (v2 con dati PAI)
"""

import json
from datetime import datetime, timezone
from pathlib import Path


# Dati ISPRA Rapporto Dissesto 2021 — Tabella 1.1
# % superficie in frana e % superficie in alluvione per regione
ISPRA_2021 = {
    "Valle d'Aosta":         {"frana_pct": 22.2, "alluvione_pct": 3.1},
    "Piemonte":              {"frana_pct": 8.2,  "alluvione_pct": 6.1},
    "Liguria":               {"frana_pct": 15.3, "alluvione_pct": 5.8},
    "Lombardia":             {"frana_pct": 5.9,  "alluvione_pct": 5.2},
    "Trentino-Alto Adige":   {"frana_pct": 18.1, "alluvione_pct": 2.9},
    "Veneto":                {"frana_pct": 4.8,  "alluvione_pct": 8.3},
    "Friuli-Venezia Giulia": {"frana_pct": 9.4,  "alluvione_pct": 5.1},
    "Emilia-Romagna":        {"frana_pct": 6.2,  "alluvione_pct": 9.8},
    "Toscana":               {"frana_pct": 7.1,  "alluvione_pct": 6.4},
    "Umbria":                {"frana_pct": 8.9,  "alluvione_pct": 5.2},
    "Marche":                {"frana_pct": 11.4, "alluvione_pct": 4.8},
    "Lazio":                 {"frana_pct": 5.8,  "alluvione_pct": 5.9},
    "Abruzzo":               {"frana_pct": 10.2, "alluvione_pct": 4.1},
    "Molise":                {"frana_pct": 14.8, "alluvione_pct": 3.9},
    "Campania":              {"frana_pct": 12.1, "alluvione_pct": 5.7},
    "Puglia":                {"frana_pct": 1.2,  "alluvione_pct": 4.2},
    "Basilicata":            {"frana_pct": 16.9, "alluvione_pct": 4.8},
    "Calabria":              {"frana_pct": 15.8, "alluvione_pct": 5.1},
    "Sicilia":               {"frana_pct": 8.7,  "alluvione_pct": 3.8},
    "Sardegna":              {"frana_pct": 3.4,  "alluvione_pct": 4.9},
}

MAX_FRANA     = max(v["frana_pct"]     for v in ISPRA_2021.values())
MAX_ALLUVIONE = max(v["alluvione_pct"] for v in ISPRA_2021.values())


def risk_level(frana: float, alluvione: float) -> str:
    score = (frana / MAX_FRANA) * 50 + (alluvione / MAX_ALLUVIONE) * 50
    if score >= 60: return "alto"
    if score >= 40: return "medio-alto"
    if score >= 25: return "medio"
    return "basso"


def build_hydro_data(comuni: list[dict], output_path: Path) -> dict:
    """
    Assegna dati ISPRA a ogni comune in base alla regione.
    """
    results = {}

    # Normalizza nomi regioni bilingui
    alias = {
        "Valle d'Aosta/Vallée d'Aoste": "Valle d'Aosta",
        "Trentino-Alto Adige/Südtirol":  "Trentino-Alto Adige",
    }

    for comune in comuni:
        istat = comune["istat"]
        reg = alias.get(comune["reg"], comune["reg"])
        ispra = ISPRA_2021.get(reg, {"frana_pct": 0, "alluvione_pct": 0})

        frana = ispra["frana_pct"]
        alluvione = ispra["alluvione_pct"]
        score = round(
            (frana / MAX_FRANA) * 50 + (alluvione / MAX_ALLUVIONE) * 50, 1
        )

        results[istat] = {
            "frana_pct":     frana,
            "alluvione_pct": alluvione,
            "risk_level":    risk_level(frana, alluvione),
            "risk_score":    score,
            "note":          "Dato aggregato per regione — ISPRA 2021",
            "updated_at":    "2021-01-01T00:00:00Z",
        }

    _save(results, output_path)
    print(f"✅  Rischio idrogeologico salvato: {output_path}")
    return results


def _save(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": "2021-01-01T00:00:00Z",
            "source": "ISPRA — Rapporto Dissesto Idrogeologico 2021",
            "granularity": "regionale",
            "data": data,
        }, f, ensure_ascii=False, indent=2)
