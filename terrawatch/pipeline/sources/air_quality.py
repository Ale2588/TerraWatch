"""
Fonte: AQICN World Air Quality Index
Aggiornamento: ogni 6 ore
Granularità: stazione più vicina al centroide del comune
"""

import requests
import json
import os
from datetime import datetime, timezone
from pathlib import Path


AQICN_TOKEN = os.environ.get("AQICN_TOKEN", "")
BASE_URL = "https://api.waqi.info"


def get_aqi_by_coords(lat: float, lon: float) -> dict | None:
    """
    Interroga AQICN per la stazione più vicina a lat/lon.
    Restituisce dizionario con AQI e principali inquinanti.
    """
    url = f"{BASE_URL}/feed/geo:{lat};{lon}/?token={AQICN_TOKEN}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        if data.get("status") != "ok":
            return None

        d = data["data"]
        iaqi = d.get("iaqi", {})

        return {
            "aqi": d.get("aqi"),                          # indice composito 0-500
            "station": d.get("city", {}).get("name", ""), # nome stazione
            "pm25": iaqi.get("pm25", {}).get("v"),        # PM2.5 µg/m³
            "pm10": iaqi.get("pm10", {}).get("v"),        # PM10 µg/m³
            "o3":   iaqi.get("o3",   {}).get("v"),        # Ozono
            "no2":  iaqi.get("no2",  {}).get("v"),        # Biossido azoto
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        print(f"  ⚠️  AQICN error ({lat},{lon}): {e}")
        return None


def aqi_label(aqi: int | None) -> str:
    """Converte AQI numerico in etichetta leggibile."""
    if aqi is None:
        return "n/d"
    if aqi <= 50:   return "Buona"
    if aqi <= 100:  return "Moderata"
    if aqi <= 150:  return "Insalubre (gruppi sensibili)"
    if aqi <= 200:  return "Insalubre"
    if aqi <= 300:  return "Molto insalubre"
    return "Pericolosa"


def aqi_color(aqi: int | None) -> str:
    """Colore semantico per AQI."""
    if aqi is None: return "#6b7280"
    if aqi <= 50:   return "#3a8c6e"   # verde
    if aqi <= 100:  return "#d4a827"   # giallo
    if aqi <= 150:  return "#d97232"   # arancio
    if aqi <= 200:  return "#c94040"   # rosso
    return "#7e22ce"                   # viola


def fetch_air_quality_for_comuni(comuni: list[dict], output_path: Path) -> dict:
    """
    Scarica AQI per tutti i comuni nella lista.
    comuni: lista di {istat, nome, lat, lon, ...}
    Restituisce dizionario {istat: dati_aria}
    """
    results = {}
    total = len(comuni)

    print(f"🌬️  Fetching air quality per {total} comuni...")

    for i, comune in enumerate(comuni):
        istat = comune["istat"]
        lat = comune["lat"]
        lon = comune["lon"]

        if i % 100 == 0:
            print(f"  {i}/{total} ({comune['nome']})")

        data = get_aqi_by_coords(lat, lon)

        if data:
            results[istat] = {
                **data,
                "label": aqi_label(data["aqi"]),
                "color": aqi_color(data["aqi"]),
            }
        else:
            results[istat] = {
                "aqi": None,
                "label": "n/d",
                "color": "#6b7280",
                "station": "",
                "pm25": None,
                "pm10": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Salvataggio intermedio ogni 500 comuni (resilienza)
        if i > 0 and i % 500 == 0:
            _save(results, output_path)

    _save(results, output_path)
    print(f"✅  Air quality salvato: {output_path}")
    return results


def _save(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "AQICN World Air Quality Index",
            "data": data,
        }, f, ensure_ascii=False, indent=2)
