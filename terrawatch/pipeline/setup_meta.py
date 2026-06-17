"""
TerraWatch — Setup metadati comuni
Genera data/meta/comuni.json dalla fonte ISTAT via openpolis/geojson-italy.
Da eseguire una volta sola (o quando ISTAT aggiorna i confini).

Uso: python pipeline/setup_meta.py
"""

import json
import sys
import requests
from pathlib import Path

ROOT = Path(__file__).parent.parent
META = ROOT / "data" / "meta"
META.mkdir(parents=True, exist_ok=True)


def download_comuni():
    print("📥  Scaricando confini comunali ISTAT...")
    url = "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_municipalities.geojson"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.json()


def extract_centroids(geojson: dict) -> list[dict]:
    """
    Estrae lista comuni con centroide approssimato dal bounding box.
    Evita dipendenza da geopandas per il setup iniziale.
    """
    comuni = []

    alias = {
        "Valle d'Aosta/Vallée d'Aoste": "Valle d'Aosta",
        "Trentino-Alto Adige/Südtirol": "Trentino-Alto Adige",
    }

    for feature in geojson["features"]:
        props = feature["properties"]
        geom = feature["geometry"]

        # Centroide approssimato dal bounding box
        coords = _flatten_coords(geom["coordinates"], geom["type"])
        if not coords:
            continue

        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        lat = round((min(lats) + max(lats)) / 2, 4)
        lon = round((min(lons) + max(lons)) / 2, 4)

        reg = alias.get(props.get("reg_name", ""), props.get("reg_name", ""))

        comuni.append({
            "istat": props.get("com_istat_code", ""),
            "nome":  props.get("name", ""),
            "prov":  props.get("prov_acr", ""),
            "reg":   reg,
            "lat":   lat,
            "lon":   lon,
        })

    return comuni


def _flatten_coords(coords, geom_type: str) -> list:
    """Appiattisce coordinate GeoJSON in lista di [lon, lat]."""
    if geom_type == "Polygon":
        return coords[0]
    elif geom_type == "MultiPolygon":
        # Prendi il poligono più grande (primo anello esterno)
        all_rings = [ring[0] for poly in coords for ring in poly]
        return max(all_rings, key=len)
    return []


def main():
    try:
        geojson = download_comuni()
    except Exception as e:
        print(f"❌  Download fallito: {e}")
        sys.exit(1)

    print("⚙️   Elaborazione centroidi...")
    comuni = extract_centroids(geojson)
    print(f"   Estratti {len(comuni)} comuni")

    # Salva JSON leggero (senza geometrie)
    out = META / "comuni.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(comuni, f, ensure_ascii=False, indent=2)
    print(f"✅  Salvato: {out}")

    # Salva anche versione per il sito (identica per ora)
    site_out = ROOT / "site" / "data" / "comuni.json"
    site_out.parent.mkdir(parents=True, exist_ok=True)
    with open(site_out, "w", encoding="utf-8") as f:
        json.dump(comuni, f, ensure_ascii=False)
    print(f"✅  Salvato: {site_out}")

    # Stats
    regioni = len(set(c["reg"] for c in comuni))
    print(f"\n📊  Stats: {len(comuni)} comuni · {regioni} regioni")


if __name__ == "__main__":
    main()
