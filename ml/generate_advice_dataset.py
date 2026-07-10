#!/usr/bin/env python3
"""Generate (product_facts, profile) → advice pairs for Level 2 LoRA training."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from Backend.lifeve.health_engine import TRAINING_PROFILES, build_advice_text, evaluate_health

OFF_HEADERS = {"User-Agent": "Lifeve-Scanner/1.0 (+local-dev)"}
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
INSTRUCTION = (
    "You are Lifeve, a grocery health assistant. Using only the structured facts provided, "
    "write personalised shopper advice. Do not invent nutrients or medical claims."
)


def load_sample_products() -> list[dict]:
    sample_path = ROOT / "Backend" / "data" / "sample_products.json"
    return json.loads(sample_path.read_text(encoding="utf-8"))


def load_barcodes(dataset_csv: Path, limit: int | None = None) -> list[str]:
    with dataset_csv.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        barcodes, seen = [], set()
        for row in reader:
            barcode = (row.get("barcode") or "").strip()
            if barcode and barcode not in seen:
                seen.add(barcode)
                barcodes.append(barcode)
            if limit and len(barcodes) >= limit:
                break
        return barcodes


def fetch_product(barcode: str) -> dict | None:
    try:
        response = requests.get(OFF_PRODUCT_URL.format(barcode=barcode), headers=OFF_HEADERS, timeout=20)
        if response.status_code != 200:
            return None
        payload = response.json()
        if payload.get("status") == 0:
            return None
        return payload.get("product") or None
    except requests.RequestException:
        return None


def build_records(products: list[dict]) -> list[dict]:
    records = []
    for product in products:
        barcode = str(product.get("code") or "").strip()
        for profile in TRAINING_PROFILES:
            health = evaluate_health(product, profile=profile)
            facts = {
                "product_name": product.get("product_name"),
                "brand": product.get("brands"),
                "nutriscore": product.get("nutriscore_grade"),
                "ingredients": product.get("ingredients_text"),
                "health": health,
                "profile": profile,
            }
            output = build_advice_text(health)
            if output.strip():
                records.append({
                    "instruction": INSTRUCTION,
                    "input": json.dumps(facts, ensure_ascii=False),
                    "output": output,
                    "barcode": barcode,
                })
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="Backend/data/health_classifier_dataset.csv")
    parser.add_argument("--output", default="Backend/data/lifeve_advice_train.jsonl")
    parser.add_argument("--limit-products", type=int, default=300)
    parser.add_argument("--use-samples", action="store_true", help="Use bundled sample products only (offline)")
    args = parser.parse_args()

    if args.use_samples:
        products = load_sample_products()
    else:
        dataset_path = Path(args.dataset)
        if not dataset_path.exists():
            raise SystemExit("Run ml/build_dataset.py first, or pass --use-samples.")

        products = []
        for barcode in load_barcodes(dataset_path, limit=args.limit_products):
            product = fetch_product(barcode)
            if product:
                products.append(product)
        if not products:
            print("No OFF products fetched; falling back to bundled samples")
            products = load_sample_products()

    records = build_records(products)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {"records": len(records), "products": len(products), "output": str(output_path)}
    output_path.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
