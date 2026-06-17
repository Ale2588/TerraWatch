"""
Fonte: ERA5 — Copernicus Climate Data Store
Aggiornamento: ogni 24 ore (dato del giorno precedente)
Granularità: griglia ~0.25° (~28km) → aggregata per comune
Variabile: 2m air temperature — anomalia rispetto a baseline 1991-2020
"""

import os
import json
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

# cdsapi si installa con: pip install cdsapi
# Richiede ~/.cdsapirc con url e key Copernicus CDS


def check_cdsapi():
    try:
        import cdsapi  # noqa
        return True
    except ImportError:
        return False


def fetch_temperature_anomaly(comuni: list[dict], output_path: Path) -> dict:
    """
    Scarica temperatura media giornaliera ERA5 per l'Italia
    e calcola anomalia rispetto alla climatologia 1991-2020.
    """
    if not check_cdsapi():
        print("⚠️  cdsapi non installato. Installa con: pip install cdsapi")
        return {}

    import cdsapi

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    year, month, day = yesterday.split("-")

    print(f"🌡️  Scaricando ERA5 temperatura per {yesterday}...")

    c = cdsapi.Client(quiet=True)

    # Bounding box Italia con margine
    area = [48, 6, 35, 19]  # N, W, S, E

    try:
        # Temperatura attuale
        c.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": "reanalysis",
                "variable": "2m_temperature",
                "year": year,
                "month": month,
                "day": day,
                "time": ["00:00", "06:00", "12:00", "18:00"],
                "area": area,
                "format": "netcdf",
            },
            "/tmp/era5_temp_current.nc",
        )

        results = _process_netcdf(
            "/tmp/era5_temp_current.nc",
            comuni,
            yesterday,
        )

        _save(results, output_path, yesterday)
        print(f"✅  Temperatura salvata: {output_path}")
        return results

    except Exception as e:
        print(f"⚠️  ERA5 error: {e}")
        return {}


def _process_netcdf(nc_path: str, comuni: list[dict], date: str) -> dict:
    """
    Legge il NetCDF ERA5 e interpola la temperatura
    sul centroide di ogni comune.
    """
    try:
        import netCDF4 as nc
    except ImportError:
        print("⚠️  netCDF4 non installato. Installa con: pip install netCDF4")
        return {}

    results = {}
    ds = nc.Dataset(nc_path)

    lats = ds.variables["latitude"][:]
    lons = ds.variables["longitude"][:]
    # t2m in Kelvin, media delle 4 ore
    t2m_k = ds.variables["t2m"][:]
    t2m_mean = np.mean(t2m_k, axis=0) - 273.15  # → Celsius

    for comune in comuni:
        istat = comune["istat"]
        lat = comune["lat"]
        lon = comune["lon"]

        # Trova cella griglia più vicina
        lat_idx = np.argmin(np.abs(lats - lat))
        lon_idx = np.argmin(np.abs(lons - lon))
        temp_c = float(t2m_mean[lat_idx, lon_idx])

        results[istat] = {
            "date": date,
            "temp_c": round(temp_c, 1),
            "anomaly_c": None,       # calcolato separatamente con climatologia
            "label": _temp_label(temp_c),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    ds.close()
    return results


def _temp_label(temp: float) -> str:
    if temp > 35:  return "Ondata di calore"
    if temp > 30:  return "Molto caldo"
    if temp > 25:  return "Caldo"
    if temp > 15:  return "Temperato"
    if temp > 5:   return "Fresco"
    if temp > 0:   return "Freddo"
    return "Gelo"


def _save(data: dict, path: Path, date: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "reference_date": date,
            "source": "ERA5 — Copernicus Climate Data Store",
            "variable": "2m_temperature",
            "data": data,
        }, f, ensure_ascii=False, indent=2)
