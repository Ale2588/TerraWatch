"""
TerraWatch — Output writer
Fonde tutti i layer in un unico JSON per comune, ottimizzato per il sito.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def merge_and_write(comuni: list[dict], current_dir: Path, output_path: Path):
    """
    Legge i JSON di ogni layer e produce teri_full.json —
    un record per comune con tutti i dati disponibili.
    """

    # Carica layer disponibili
    layers = {}
    layer_files = {
        "hydro":    "hydro_risk.json",
        "air":      "air_quality.json",
        "temp":     "temperature.json",
        "sentinel": "sentinel.json",
    }

    for key, fname in layer_files.items():
        path = current_dir / fname
        if path.exists():
            with open(path, encoding="utf-8") as f:
                content = json.load(f)
                layers[key] = content.get("data", {})
            print(f"  ✓ {key}: {len(layers[key])} comuni")
        else:
            print(f"  ✗ {key}: non trovato (skip)")
            layers[key] = {}

    # Merge per comune
    merged = []
    for comune in comuni:
        istat = comune["istat"]

        hydro    = layers["hydro"].get(istat, {})
        air      = layers["air"].get(istat, {})
        temp     = layers["temp"].get(istat, {})
        sentinel = layers["sentinel"].get(istat, {})

        record = {
            # Anagrafica
            "istat": istat,
            "nome":  comune["nome"],
            "prov":  comune["prov"],
            "reg":   comune["reg"],
            "lat":   comune["lat"],
            "lon":   comune["lon"],

            # Layer idrogeologico
            "frana_pct":     hydro.get("frana_pct"),
            "alluvione_pct": hydro.get("alluvione_pct"),
            "risk_level":    hydro.get("risk_level"),
            "risk_score":    hydro.get("risk_score"),

            # Layer qualità aria
            "aqi":           air.get("aqi"),
            "aqi_label":     air.get("label"),
            "aqi_color":     air.get("color"),
            "pm25":          air.get("pm25"),
            "pm10":          air.get("pm10"),
            "air_station":   air.get("station"),
            "air_updated":   air.get("updated_at"),

            # Layer temperatura
            "temp_c":        temp.get("temp_c"),
            "temp_label":    temp.get("label"),
            "temp_updated":  temp.get("updated_at"),

            # Layer Sentinel-2
            "ndvi":          sentinel.get("ndvi"),
            "ndwi":          sentinel.get("ndwi"),
            "ndvi_label":    sentinel.get("ndvi_label"),
            "scene_date":    sentinel.get("scene_date"),
            "sentinel_updated": sentinel.get("updated_at"),
        }

        merged.append(record)

    # Scrivi output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_comuni": len(merged),
            "layers": list(layers.keys()),
            "data": merged,
        }, f, ensure_ascii=False)

    size_kb = output_path.stat().st_size / 1024
    print(f"\n📦  Output: {output_path}")
    print(f"    {len(merged)} comuni · {size_kb:.0f} KB")


def write_single_comune(istat: str, data: dict, timeseries_dir: Path, layer: str):
    """
    Aggiunge un punto alla serie storica di un comune per un layer specifico.
    Struttura: data/timeseries/{istat}/{layer}.json → [{date, value}, ...]
    """
    comune_dir = timeseries_dir / istat
    comune_dir.mkdir(parents=True, exist_ok=True)
    ts_path = comune_dir / f"{layer}.json"

    # Carica serie esistente
    series = []
    if ts_path.exists():
        with open(ts_path, encoding="utf-8") as f:
            series = json.load(f)

    # Aggiungi punto
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    series.append({"date": today, **data})

    # Mantieni ultimi 365 giorni
    series = series[-365:]

    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(series, f, ensure_ascii=False)
