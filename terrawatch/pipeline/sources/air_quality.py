"""
Fonte: AQICN World Air Quality Index
Aggiornamento: ogni 6 ore
Strategia: fetch per capoluoghi di provincia, propaga ai comuni della stessa provincia
"""

import requests
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


AQICN_TOKEN = os.environ.get("AQICN_TOKEN", "")
BASE_URL = "https://api.waqi.info"

# Capoluoghi di provincia con coordinate
CAPOLUOGHI = [
    {"prov": "AG", "lat": 37.311, "lon": 13.576}, {"prov": "AL", "lat": 44.913, "lon": 8.615},
    {"prov": "AN", "lat": 43.616, "lon": 13.516}, {"prov": "AO", "lat": 45.737, "lon": 7.315},
    {"prov": "AR", "lat": 43.463, "lon": 11.880}, {"prov": "AP", "lat": 42.851, "lon": 13.574},
    {"prov": "AT", "lat": 44.900, "lon": 8.207}, {"prov": "AV", "lat": 40.914, "lon": 14.790},
    {"prov": "BA", "lat": 41.125, "lon": 16.866}, {"prov": "BT", "lat": 41.228, "lon": 16.295},
    {"prov": "BL", "lat": 46.137, "lon": 12.217}, {"prov": "BN", "lat": 41.130, "lon": 14.783},
    {"prov": "BG", "lat": 45.698, "lon": 9.677}, {"prov": "BI", "lat": 45.563, "lon": 8.058},
    {"prov": "BO", "lat": 44.494, "lon": 11.342}, {"prov": "BZ", "lat": 46.498, "lon": 11.354},
    {"prov": "BS", "lat": 45.541, "lon": 10.220}, {"prov": "BR", "lat": 40.632, "lon": 17.941},
    {"prov": "CA", "lat": 39.223, "lon": 9.121}, {"prov": "CL", "lat": 37.490, "lon": 13.990},
    {"prov": "CB", "lat": 41.563, "lon": 14.668}, {"prov": "CI", "lat": 39.054, "lon": 9.017},
    {"prov": "CE", "lat": 41.070, "lon": 14.332}, {"prov": "CT", "lat": 37.503, "lon": 15.087},
    {"prov": "CZ", "lat": 38.910, "lon": 16.587}, {"prov": "CH", "lat": 42.351, "lon": 14.168},
    {"prov": "CO", "lat": 45.808, "lon": 9.085}, {"prov": "CS", "lat": 39.298, "lon": 16.254},
    {"prov": "CR", "lat": 45.133, "lon": 9.895}, {"prov": "KR", "lat": 39.090, "lon": 17.125},
    {"prov": "CN", "lat": 44.397, "lon": 7.547}, {"prov": "EN", "lat": 37.566, "lon": 14.279},
    {"prov": "FM", "lat": 43.160, "lon": 13.717}, {"prov": "FE", "lat": 44.836, "lon": 11.620},
    {"prov": "FI", "lat": 43.769, "lon": 11.256}, {"prov": "FG", "lat": 41.461, "lon": 15.548},
    {"prov": "FC", "lat": 44.222, "lon": 12.041}, {"prov": "FR", "lat": 41.638, "lon": 13.342},
    {"prov": "GE", "lat": 44.407, "lon": 8.934}, {"prov": "GO", "lat": 45.942, "lon": 13.622},
    {"prov": "GR", "lat": 42.764, "lon": 11.113}, {"prov": "IM", "lat": 43.888, "lon": 8.028},
    {"prov": "IS", "lat": 41.593, "lon": 14.233}, {"prov": "SP", "lat": 44.103, "lon": 9.824},
    {"prov": "AQ", "lat": 42.351, "lon": 13.400}, {"prov": "LT", "lat": 41.467, "lon": 12.903},
    {"prov": "LE", "lat": 40.352, "lon": 18.175}, {"prov": "LC", "lat": 45.856, "lon": 9.397},
    {"prov": "LI", "lat": 43.548, "lon": 10.316}, {"prov": "LO", "lat": 45.314, "lon": 9.503},
    {"prov": "LU", "lat": 43.843, "lon": 10.508}, {"prov": "MC", "lat": 43.300, "lon": 13.453},
    {"prov": "MN", "lat": 45.156, "lon": 10.791}, {"prov": "MS", "lat": 44.035, "lon": 10.143},
    {"prov": "MT", "lat": 40.666, "lon": 16.604}, {"prov": "VS", "lat": 39.748, "lon": 8.556},
    {"prov": "ME", "lat": 38.193, "lon": 15.554}, {"prov": "MI", "lat": 45.465, "lon": 9.188},
    {"prov": "MO", "lat": 44.646, "lon": 10.926}, {"prov": "MB", "lat": 45.584, "lon": 9.274},
    {"prov": "NA", "lat": 40.853, "lon": 14.268}, {"prov": "NO", "lat": 45.446, "lon": 8.622},
    {"prov": "NU", "lat": 40.321, "lon": 9.330}, {"prov": "OG", "lat": 39.897, "lon": 9.501},
    {"prov": "OT", "lat": 40.727, "lon": 8.560}, {"prov": "OR", "lat": 39.904, "lon": 8.591},
    {"prov": "PD", "lat": 45.407, "lon": 11.876}, {"prov": "PA", "lat": 38.115, "lon": 13.361},
    {"prov": "PR", "lat": 44.801, "lon": 10.328}, {"prov": "PV", "lat": 45.185, "lon": 9.155},
    {"prov": "PG", "lat": 43.110, "lon": 12.389}, {"prov": "PU", "lat": 43.628, "lon": 12.636},
    {"prov": "PE", "lat": 42.459, "lon": 14.216}, {"prov": "PC", "lat": 44.836, "lon": 9.796},
    {"prov": "PI", "lat": 43.723, "lon": 10.402}, {"prov": "PT", "lat": 43.933, "lon": 10.917},
    {"prov": "PN", "lat": 45.959, "lon": 12.662}, {"prov": "PZ", "lat": 40.638, "lon": 15.799},
    {"prov": "PO", "lat": 43.881, "lon": 11.097}, {"prov": "RG", "lat": 36.928, "lon": 14.731},
    {"prov": "RA", "lat": 44.418, "lon": 12.203}, {"prov": "RC", "lat": 38.111, "lon": 15.661},
    {"prov": "RE", "lat": 44.698, "lon": 10.630}, {"prov": "RI", "lat": 42.404, "lon": 12.856},
    {"prov": "RN", "lat": 44.060, "lon": 12.567}, {"prov": "RM", "lat": 41.894, "lon": 12.483},
    {"prov": "RO", "lat": 45.070, "lon": 11.790}, {"prov": "SA", "lat": 40.676, "lon": 14.768},
    {"prov": "SS", "lat": 40.727, "lon": 8.560}, {"prov": "SV", "lat": 44.308, "lon": 8.480},
    {"prov": "SI", "lat": 43.319, "lon": 11.331}, {"prov": "SR", "lat": 37.075, "lon": 15.287},
    {"prov": "SO", "lat": 46.170, "lon": 9.870}, {"prov": "TA", "lat": 40.476, "lon": 17.229},
    {"prov": "TE", "lat": 42.659, "lon": 13.704}, {"prov": "TR", "lat": 42.564, "lon": 12.643},
    {"prov": "TO", "lat": 45.070, "lon": 7.687}, {"prov": "TP", "lat": 37.869, "lon": 12.582},
    {"prov": "TN", "lat": 46.074, "lon": 11.122}, {"prov": "TV", "lat": 45.667, "lon": 12.242},
    {"prov": "TS", "lat": 45.649, "lon": 13.777}, {"prov": "UD", "lat": 46.063, "lon": 13.235},
    {"prov": "VA", "lat": 45.818, "lon": 8.826}, {"prov": "VE", "lat": 45.438, "lon": 12.327},
    {"prov": "VB", "lat": 45.929, "lon": 8.552}, {"prov": "VC", "lat": 45.329, "lon": 8.424},
    {"prov": "VR", "lat": 45.438, "lon": 10.992}, {"prov": "VV", "lat": 38.676, "lon": 16.101},
    {"prov": "VI", "lat": 45.547, "lon": 11.535}, {"prov": "VT", "lat": 42.418, "lon": 12.105},
]


def get_aqi_by_coords(lat, lon):
    url = f"{BASE_URL}/feed/geo:{lat};{lon}/?token={AQICN_TOKEN}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("status") != "ok":
            return None
        d = data["data"]
        iaqi = d.get("iaqi", {})
        return {
            "aqi":     d.get("aqi"),
            "station": d.get("city", {}).get("name", ""),
            "pm25":    iaqi.get("pm25", {}).get("v"),
            "pm10":    iaqi.get("pm10", {}).get("v"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        print(f"  ⚠️  AQICN error ({lat},{lon}): {e}")
        return None


def aqi_label(aqi):
    if aqi is None:  return "n/d"
    if aqi <= 50:    return "Buona"
    if aqi <= 100:   return "Moderata"
    if aqi <= 150:   return "Insalubre (gruppi sensibili)"
    if aqi <= 200:   return "Insalubre"
    return "Molto insalubre"


def aqi_color(aqi):
    if aqi is None: return "#6b7280"
    if aqi <= 50:   return "#3a8c6e"
    if aqi <= 100:  return "#d4a827"
    if aqi <= 150:  return "#d97232"
    if aqi <= 200:  return "#c94040"
    return "#7e22ce"


def fetch_air_quality_for_comuni(comuni, output_path):
    """
    Fetch AQI per capoluogo di provincia, propaga a tutti i comuni della provincia.
    107 chiamate invece di 7.899.
    """
    print(f"🌬️  Fetching AQI per {len(CAPOLUOGHI)} province...")

    # Fetch per provincia
    prov_data = {}
    for i, cap in enumerate(CAPOLUOGHI):
        prov = cap["prov"]
        print(f"  {i+1}/{len(CAPOLUOGHI)} {prov}")
        data = get_aqi_by_coords(cap["lat"], cap["lon"])
        if data:
            prov_data[prov] = {
                **data,
                "label": aqi_label(data["aqi"]),
                "color": aqi_color(data["aqi"]),
            }
        time.sleep(0.3)  # rate limiting

    print(f"  Province con dati: {len(prov_data)}/{len(CAPOLUOGHI)}")

    # Propaga a tutti i comuni
    results = {}
    empty = {
        "aqi": None, "label": "n/d", "color": "#6b7280",
        "station": "", "pm25": None, "pm10": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    for comune in comuni:
        prov = comune.get("prov", "")
        results[comune["istat"]] = prov_data.get(prov, empty)

    _save(results, output_path)
    print(f"✅  Air quality salvato: {output_path}")
    return results


def _save(data, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "AQICN — dati per capoluogo di provincia",
            "data": data,
        }, f, ensure_ascii=False)
