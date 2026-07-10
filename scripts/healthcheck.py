#!/usr/bin/env python3
"""Quick Lifeve backend health check — run: python scripts/healthcheck.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Backend.server import create_app


def main() -> int:
    print("Lifeve health check\n" + "=" * 40)

    lora_dir = ROOT / "Backend" / "models" / "lifeve-advice-lora"
    clf_path = ROOT / "Backend" / "models" / "health_classifier.joblib"
    print(f"Classifier model: {'OK' if clf_path.exists() else 'MISSING'}")
    print(f"LoRA adapter:     {'OK' if (lora_dir / 'adapter_model.safetensors').exists() else 'MISSING'}")

    app = create_app()
    client = app.test_client()

    r = client.post("/scan", json={"barcode": "3017620422003"})
    data = r.get_json() or {}
    print(f"\nNutella scan HTTP {r.status_code}")
    print(f"  data_source:    {data.get('data_source')}")
    print(f"  product:        {data.get('product_name')}")
    print(f"  ml_tier:        {(data.get('ml_prediction') or {}).get('health_tier')}")
    print(f"  ml_error:       {data.get('ml_prediction_error')}")
    print(f"  personalised:   {(data.get('personalised') or {}).get('source')}")
    if "lora_advice_error" in data:
        print(f"  lora_error:     {data.get('lora_advice_error')}")
    else:
        print("  lora:           skipped (off by default)")
    print(f"  scan_error:     {data.get('error')}")

    ok = r.status_code == 200 and data.get("product_name") and not data.get("error")
    print("\n" + ("PASS — core scan pipeline works." if ok else "FAIL — see errors above."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
