"""
TerraWatch — Pipeline principale
Orchestra il fetch di tutti i layer e genera i JSON per il sito.

Uso:
  python pipeline/run.py --layer all        # tutti i layer
  python pipeline/run.py --layer air        # solo qualità aria
  python pipeline/run.py --layer temp       # solo temperatura
  python pipeline/run.py --layer sentinel   # solo Sentinel-2
  python pipeline/run.py --layer hydro      # solo rischio idrogeologico
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Path del progetto
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
META = DATA / "meta"
CURRENT = DATA / "current"

sys.path.insert(0, str(ROOT))

from pipeline.sources.air_quality import fetch_air_quality_for_comuni
from pipeline.sources.temperature import fetch_temperature_anomaly
from pipeline.sources.sentinel import fetch_sentinel_indices
from pipeline.sources.hydro_risk import build_hydro_data
from pipeline.output.writer import merge_and_write


def load_comuni() -> list[dict]:
    comuni_path = META / "comuni.json"
    if not comuni_path.exists():
        print("❌  comuni.json non trovato in data/meta/")
        print("   Esegui prima: python pipeline/setup_meta.py")
        sys.exit(1)
    with open(comuni_path, encoding="utf-8") as f:
        return json.load(f)


def run(layer: str):
    comuni = load_comuni()
    print(f"\n🌍 TerraWatch Pipeline — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"   Comuni: {len(comuni)} | Layer: {layer}\n")

    if layer in ("all", "hydro"):
        build_hydro_data(comuni, CURRENT / "hydro_risk.json")

    if layer in ("all", "air"):
        fetch_air_quality_for_comuni(comuni, CURRENT / "air_quality.json")

    if layer in ("all", "temp"):
        fetch_temperature_anomaly(comuni, CURRENT / "temperature.json")

    if layer in ("all", "sentinel"):
        fetch_sentinel_indices(comuni, CURRENT / "sentinel.json")

    if layer == "all":
        print("\n🔀 Merging tutti i layer...")
        merge_and_write(comuni, CURRENT, DATA / "current" / "teri_full.json")
        print("✅  Pipeline completata!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TerraWatch data pipeline")
    parser.add_argument(
        "--layer",
        choices=["all", "air", "temp", "sentinel", "hydro"],
        default="all",
        help="Layer da aggiornare"
    )
    args = parser.parse_args()
    run(args.layer)
