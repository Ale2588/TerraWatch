"""
Fonte: Sentinel-2 L2A — Copernicus Data Space Ecosystem
Aggiornamento: ogni 5 giorni (rivisita satellite)
Indici: NDVI (vegetazione), NDWI (acqua)
Accesso: OAuth2 token da dataspace.copernicus.eu

FIX 2026-06: download_band riscritto — rasterio opener non supportato,
sostituito con download HTTP → tempfile → rasterio.open locale.
"""

import os
import json
import tempfile
import requests
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict


COPERNICUS_USER = os.environ.get("COPERNICUS_USER", "")
COPERNICUS_PASS = os.environ.get("COPERNICUS_PASS", "")

STAC_URL = "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a/items"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

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
        token = r.json().get("access_token")
        if token:
            print("✅  Token Copernicus ottenuto")
        return token
    except Exception as e:
        print(f"⚠️  Token Copernicus error: {e}")
        return None


# ---------------------------------------------------------------------------
# STAC query
# ---------------------------------------------------------------------------

def find_scenes(bbox: list[float], date_from: str, date_to: str,
                max_cloud: int = 20) -> list[dict]:
    """
    Query STAC v1 per scene Sentinel-2 L2A.
    bbox: [lon_min, lat_min, lon_max, lat_max]
    La collection è già nell'URL — niente parametro filter o collections.
    Cloud cover filtrato lato client.
    """
    params = {
        "bbox": ",".join(map(str, bbox)),
        "datetime": f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
        "limit": 20,
    }

    try:
        r = requests.get(STAC_URL, params=params, timeout=30)
        r.raise_for_status()
        features = r.json().get("features", [])

        # Filtra cloud cover lato client
        features = [
            f for f in features
            if (f.get("properties", {}).get("eo:cloud_cover") or 100) < max_cloud
        ]

        # Ordina per data decrescente (più recente prima)
        features.sort(
            key=lambda f: f.get("properties", {}).get("datetime", ""),
            reverse=True,
        )

        print(f"    Scene trovate (cloud<{max_cloud}%): {len(features)}")
        return features
    except Exception as e:
        print(f"    ⚠️  STAC query error: {e}")
        return []


# ---------------------------------------------------------------------------
# Download banda — FIX: scarica in tempfile, poi legge con rasterio
# ---------------------------------------------------------------------------

def download_band(asset_url: str, token: str) -> np.ndarray | None:
    """
    Scarica una banda Sentinel-2 (GeoTIFF) via HTTP con Bearer token,
    la salva in un file temporaneo e la legge con rasterio.
    Restituisce array numpy float32 o None in caso di errore.
    """
    try:
        import rasterio

        headers = {"Authorization": f"Bearer {token}"}

        # Alcuni URL del Copernicus Data Space richiedono redirect S3
        # Seguiamo i redirect mantenendo l'header Authorization
        session = requests.Session()
        session.headers.update(headers)

        print(f"    Downloading: {asset_url[:80]}...")
        resp = session.get(asset_url, stream=True, timeout=120)

        if resp.status_code == 401:
            print(f"    ⚠️  401 Unauthorized — token scaduto o URL non accessibile")
            return None

        resp.raise_for_status()

        # Scrivi in file temporaneo
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                tmp.write(chunk)

        # Leggi con rasterio dal file locale
        with rasterio.open(tmp_path) as src:
            arr = src.read(1).astype(np.float32)

        # Pulizia
        Path(tmp_path).unlink(missing_ok=True)

        # Maschera nodata (0 nelle bande Sentinel-2 = nodata)
        arr = np.where(arr == 0, np.nan, arr)

        print(f"    ✅  Banda scaricata: shape={arr.shape}, validi={np.sum(np.isfinite(arr))}")
        return arr

    except Exception as e:
        print(f"    ⚠️  Band download error: {e}")
        # Pulizia eventuale tempfile
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Calcolo indici
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Entry point principale
# ---------------------------------------------------------------------------

def fetch_sentinel_indices(comuni: list[dict], output_path: Path) -> dict:
    """
    Per ogni regione italiana: trova la scena Sentinel-2 più recente,
    scarica bande B03/B04/B08, calcola NDVI e NDWI medi regionali,
    propaga il valore a tutti i comuni della regione.
    """
    token = get_access_token()
    if not token:
        print("⚠️  Impossibile autenticarsi su Copernicus. Controlla credenziali.")
        return {}

    results = {}
    date_to   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_from = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")

    # Raggruppa comuni per regione
    by_region = defaultdict(list)
    for c in comuni:
        by_region[c["reg"]].append(c)

    print(f"🛰️  Fetching Sentinel-2 per {len(by_region)} regioni ({date_from} → {date_to})...")

    for reg_name, reg_comuni in by_region.items():
        lats = [c["lat"] for c in reg_comuni]
        lons = [c["lon"] for c in reg_comuni]
        bbox = [min(lons) - 0.1, min(lats) - 0.1, max(lons) + 0.1, max(lats) + 0.1]

        print(f"\n  📍 Regione: {reg_name} ({len(reg_comuni)} comuni)")
        scenes = find_scenes(bbox, date_from, date_to)

        if not scenes:
            print(f"  ⚠️  Nessuna scena disponibile — provo con finestra 30 giorni")
            date_from_ext = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
            scenes = find_scenes(bbox, date_from_ext, date_to, max_cloud=30)

        if not scenes:
            print(f"  ❌  Ancora nessuna scena per {reg_name}, skip")
            for c in reg_comuni:
                results[c["istat"]] = _empty_result()
            continue

        # Prendi la scena più recente
        scene = scenes[0]
        props = scene.get("properties", {})
        scene_date   = props.get("datetime", "")[:10]
        cloud_cover  = props.get("eo:cloud_cover")
        assets       = scene.get("assets", {})

        print(f"    Scena: {scene_date} | Cloud: {cloud_cover}%")

        # URL bande — Copernicus Data Space usa chiavi come "B04", "B08", "B03"
        # oppure nomi alternativi: controlla entrambi i pattern
        band_keys = {
            "red":   ["B04", "red"],
            "nir":   ["B08", "nir", "B8A"],
            "green": ["B03", "green"],
        }

        band_urls = {}
        for band_name, candidates in band_keys.items():
            for key in candidates:
                asset = assets.get(key)
                if asset and asset.get("href"):
                    band_urls[band_name] = asset["href"]
                    break

        missing = [k for k in ["red", "nir", "green"] if k not in band_urls]
        if missing:
            print(f"    ⚠️  Bande mancanti: {missing}")
            print(f"    Asset keys disponibili: {list(assets.keys())}")
            for c in reg_comuni:
                results[c["istat"]] = _empty_result()
            continue

        # Download bande
        red   = download_band(band_urls["red"],   token)
        nir   = download_band(band_urls["nir"],   token)
        green = download_band(band_urls["green"], token)

        if red is None or nir is None:
            print(f"    ❌  Download bande fallito per {reg_name}")
            for c in reg_comuni:
                results[c["istat"]] = _empty_result()
            continue

        # Calcolo indici
        ndvi_arr  = compute_ndvi(red, nir)
        ndwi_arr  = compute_ndwi(green, nir) if green is not None else None

        ndvi_mean = float(np.nanmean(ndvi_arr))
        ndwi_mean = float(np.nanmean(ndwi_arr)) if ndwi_arr is not None else None

        print(f"    📊 NDVI medio: {ndvi_mean:.3f} | NDWI medio: {ndwi_mean:.3f if ndwi_mean else 'n/d'}")

        # Propaga a tutti i comuni della regione
        for c in reg_comuni:
            results[c["istat"]] = {
                "ndvi":        round(ndvi_mean, 3),
                "ndwi":        round(ndwi_mean, 3) if ndwi_mean is not None else None,
                "ndvi_label":  ndvi_label(ndvi_mean),
                "scene_date":  scene_date,
                "cloud_cover": cloud_cover,
                "updated_at":  datetime.now(timezone.utc).isoformat(),
            }

    _save(results, output_path)
    print(f"\n✅  Sentinel-2 salvato: {output_path} ({len(results)} comuni)")
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_result() -> dict:
    return {
        "ndvi":        None,
        "ndwi":        None,
        "ndvi_label":  "n/d",
        "scene_date":  None,
        "cloud_cover": None,
        "updated_at":  datetime.now(timezone.utc).isoformat(),
    }


def _save(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source":     "Sentinel-2 L2A — Copernicus Data Space",
            "indices":    ["NDVI", "NDWI"],
            "data":       data,
        }, f, ensure_ascii=False, indent=2)
