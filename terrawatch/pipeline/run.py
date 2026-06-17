"""
TerraWatch — Pipeline principale
Uso:
  python pipeline/run.py --layer air
  python pipeline/run.py --layer all
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
META = DATA / "meta"
CURRENT = DATA / "current"

sys.path.insert(0, str(ROOT))


def load_comuni():
    comuni_path = META / "comuni.json"
    if not comuni_path.exists():
        print("❌  comuni.json non trovato in data/meta/")
        sys.exit(1)
    with open(comuni_path, encoding="utf-8") as f:
        return json.load(f)


def run(layer):
    comuni = load_comuni()
    print(f"\n🌍 TerraWatch Pipeline — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"   Comuni: {len(comuni)} | Layer: {layer}\n")

    if layer in ("all", "hydro"):
        from pipeline.sources.hydro_risk import build_hydro_data
        build_hydro_data(comuni, CURRENT / "hydro_risk.json")

    if layer in ("all", "air"):
        from pipeline.sources.air_quality import fetch_air_quality_for_comuni
        fetch_air_quality_for_comuni(comuni, CURRENT / "air_quality.json")

    if layer in ("all", "temp"):
        from pipeline.sources.temperature import fetch_temperature_anomaly
        fetch_temperature_anomaly(comuni, CURRENT / "temperature.json")

    if layer in ("all", "sentinel"):
        from pipeline.sources.sentinel import fetch_sentinel_indices
        fetch_sentinel_indices(comuni, CURRENT / "sentinel.json")

    # Merge sempre dopo ogni update
    from pipeline.output.writer import merge_and_write
    merge_and_write(comuni, CURRENT, CURRENT / "teri_full.json")
    print("✅  Pipeline completata!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", choices=["all", "air", "temp", "sentinel", "hydro"], default="air")
    args = parser.parse_args()
    run(args.layer)
