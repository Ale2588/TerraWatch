"""
Fonte: Sentinel-2 L2A — Copernicus Data Space Ecosystem
Aggiornamento: ogni 5 giorni (rivisita satellite)
Indici: NDVI (vegetazione), NDWI (acqua), NDBI (superficie costruita)
Accesso: OAuth2 token da dataspace.copernicus.eu
"""

import os
import json
import requests
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path


COPERNICUS_USER = os.environ.get("COPERNICUS_USER", "")
COPERNICUS_PASS = os.environ.get("COPERNICUS_PASS", "")

STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/collections/SENTINEL-2/items"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


def get_access_token() -> str | None:
    """Ottieni token OAuth2 da Copernicus Data Space."""
    try:
        r = requests.post(TOKEN_URL, data={
            "grant_type": "password",
            "username": COPERNICUS_USER,
            "password": COPERNICUS_PASS,
            "client_id": "cdse-public",
        }, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]
    except Exception as e:
        print(f"⚠️  Token Copernicus error: {e}")
        return None


def find_scenes(bbox: list[float], date_from: str, date_to: str,
                max_cloud: int = 20) -> list[dict]:
    """
    Query STAC per scene Sentinel-2 L2A nell'area e nel periodo.
    bbox: [lon_min, lat_min, lon_max, lat_max]
    """
    params = {
        "bbox": ",".join(map(str, bbox)),
        "datetime": f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
        "collections": "SENTINEL-2",
        "filter": f"s2:processing_level='L2A' AND eo:cloud_cover<{max_cloud}",
        "limit": 10,
        "sortby": "-datetime",
    }

    try:
        r = requests.get(STAC_URL, params=params, timeout=30)
        r.raise_for_status()
        features = r.json().get("features", [])
        print(f"  Scene trovate: {len(features)}")
        return features
    except Exception as e:
        print(f"  ⚠️  STAC query error: {e}")
        return []


def download_band(asset_url: str, token: str) -> np.ndarray | None:
    """
    Scarica una singola banda via HTTP range request.
    Restituisce array numpy in float32.
    """
    try:
        # Usa rasterio per leggere direttamente da URL (lazy load)
        import rasterio
        from rasterio.session import AWSSession

        headers = {"Authorization": f"Bearer {token}"}

        with rasterio.Env():
            with rasterio.open(
                asset_url,
                opener=lambda url, **kw: requests.get(
                    url, headers=headers, stream=True, **kw
                ).raw,
            ) as src:
                return src.read(1).astype(np.float32)

    except Exception as e:
        print(f"  ⚠️  Band download error: {e}")
        return None


def compute_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDVI = (NIR - RED) / (NIR + RED). Range [-1, 1]."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
        ndvi = np.where(np.isfinite(ndvi), ndvi, np.nan)
    return ndvi


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI = (GREEN - NIR) / (GREEN + NIR). Range [-1, 1]."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = (green - nir) / (green + nir)
        ndwi = np.where(np.isfinite(ndwi), ndwi, np.nan)
    return ndwi


def ndvi_label(val: float | None) -> str:
    if val is None:   return "n/d"
    if val > 0.6:     return "Vegetazione densa"
    if val > 0.4:     return "Vegetazione moderata"
    if val > 0.2:     return "Vegetazione rada"
    if val > 0.0:     return "Suolo nudo / urbano"
    return "Acqua / superfici impermeabili"


def fetch_sentinel_indices(comuni: list[dict], output_path: Path) -> dict:
    """
    Per ogni comune: trova la scena Sentinel-2 più recente (<20% nuvole),
    scarica le bande necessarie, calcola NDVI e NDWI medi.
    
    Strategia MVP: processa a livello regionale (bounding box regione)
    per minimizzare le chiamate API.
    """
    token = get_access_token()
    if not token:
        print("⚠️  Impossibile autenticarsi su Copernicus. Controlla credenziali.")
        return {}

    results = {}
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_from = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")

    # Raggruppa comuni per regione per ridurre le query
    from collections import defaultdict
    by_region = defaultdict(list)
    for c in comuni:
        by_region[c["reg"]].append(c)

    print(f"🛰️  Fetching Sentinel-2 per {len(by_region)} regioni...")

    for reg_name, reg_comuni in by_region.items():
        lats = [c["lat"] for c in reg_comuni]
        lons = [c["lon"] for c in reg_comuni]
        bbox = [min(lons)-0.1, min(lats)-0.1, max(lons)+0.1, max(lats)+0.1]

        print(f"  Regione: {reg_name} ({len(reg_comuni)} comuni)")
        scenes = find_scenes(bbox, date_from, date_to)

        if not scenes:
            print(f"  ⚠️  Nessuna scena per {reg_name}")
            for c in reg_comuni:
                results[c["istat"]] = _empty_result()
            continue

        # Prendi la scena più recente
        scene = scenes[0]
        scene_date = scene.get("properties", {}).get("datetime", "")[:10]
        assets = scene.get("assets", {})

        # Bande necessarie: B04=Red, B08=NIR, B03=Green
        band_urls = {
            "red":   assets.get("B04", {}).get("href"),
            "nir":   assets.get("B08", {}).get("href"),
            "green": assets.get("B03", {}).get("href"),
        }

        if not all(band_urls.values()):
            print(f"  ⚠️  Bande mancanti per {reg_name}")
            for c in reg_comuni:
                results[c["istat"]] = _empty_result()
            continue

        # Download bande (una volta per regione)
        print(f"  Downloading bande per {reg_name} (scena {scene_date})...")
        red   = download_band(band_urls["red"],   token)
        nir   = download_band(band_urls["nir"],   token)
        green = download_band(band_urls["green"], token)

        if red is None or nir is None:
            for c in reg_comuni:
                results[c["istat"]] = _empty_result()
            continue

        ndvi_arr = compute_ndvi(red, nir)
        ndwi_arr = compute_ndwi(green, nir)

        # Per MVP: assegna il valore medio regionale a tutti i comuni
        # (Fase 2: clip per geometria comunale)
        ndvi_mean = float(np.nanmean(ndvi_arr))
        ndwi_mean = float(np.nanmean(ndwi_arr))

        for c in reg_comuni:
            results[c["istat"]] = {
                "ndvi": round(ndvi_mean, 3),
                "ndwi": round(ndwi_mean, 3),
                "ndvi_label": ndvi_label(ndvi_mean),
                "scene_date": scene_date,
                "cloud_cover": scene.get("properties", {}).get("eo:cloud_cover"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    _save(results, output_path)
    print(f"✅  Sentinel-2 salvato: {output_path}")
    return results


def _empty_result() -> dict:
    return {
        "ndvi": None,
        "ndwi": None,
        "ndvi_label": "n/d",
        "scene_date": None,
        "cloud_cover": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _save(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Sentinel-2 L2A — Copernicus Data Space",
            "indices": ["NDVI", "NDWI"],
            "data": data,
        }, f, ensure_ascii=False, indent=2)
