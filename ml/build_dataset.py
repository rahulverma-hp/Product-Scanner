#!/usr/bin/env python3
"""Build classifier dataset from OpenFoodFacts for the scanner project."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from Backend.lifeve.features import FLAG_COLUMNS, extract_feature_row
from Backend.lifeve.health_engine import TRAINING_PROFILES, evaluate_health

SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_HEADERS = {"User-Agent": "Lifeve-Scanner/1.0 (+local-dev; contact: rahulvermaa.hp@gmail.com)"}
FIELDS = "code,product_name,brands,ingredients_text,nutriments,nutriscore_grade,nutrition_grades"
DEFAULT_TAGS = ["en:snacks", "en:beverages", "en:breakfast-cereals", "en:dairy", "en:chocolates"]


def fetch_products(tag: str, *, page_size: int = 100, max_pages: int = 10) -> list[dict]:
    products: list[dict] = []
    for page in range(1, max_pages + 1):
        params = {
            "action": "process",
            "tagtype_0": "categories",
            "tag_contains_0": "contains",
            "tag_0": tag,
            "page_size": page_size,
            "page": page,
            "json": 1,
            "fields": FIELDS,
        }
        for attempt in range(3):
            try:
                response = requests.get(SEARCH_URL, params=params, headers=OFF_HEADERS, timeout=30)
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    print(f"Skipping {tag} page {page}: {exc}")
                    return products
                time.sleep(1.5 * (attempt + 1))
        batch = response.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
        time.sleep(0.3)
    return products


def load_sample_products() -> list[dict]:
    sample_path = ROOT / "Backend" / "data" / "sample_products.json"
    return json.loads(sample_path.read_text(encoding="utf-8"))


def build_rows(products: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for product in products:
        barcode = str(product.get("code") or "").strip()
        if not barcode or barcode in seen or not product.get("ingredients_text"):
            continue
        seen.add(barcode)
        for profile in TRAINING_PROFILES:
            health = evaluate_health(product, profile=profile)
            row = extract_feature_row(product, profile=profile, health=health)
            row["product_name"] = product.get("product_name") or ""
            row["nutriscore_grade"] = product.get("nutriscore_grade") or ""
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="Backend/data/health_classifier_dataset.csv")
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--use-samples", action="store_true")
    args = parser.parse_args()

    if args.use_samples:
        all_products = load_sample_products()
    else:
        all_products = []
        for tag in DEFAULT_TAGS:
            print(f"Fetching {tag}")
            all_products.extend(fetch_products(tag, page_size=args.page_size, max_pages=args.max_pages))
        if not all_products:
            print("Falling back to bundled samples")
            all_products = load_sample_products()

    rows = build_rows(all_products)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "barcode", "product_name", "nutriscore_grade", "profile_type", "age", "weight_kg", "health_tier",
        *FLAG_COLUMNS, "nutriscore_encoded", "profile_encoded", "ingredient_text_len",
        "good_keyword_hits", "bad_keyword_hits", "pros_count", "cons_count", "high_nutrient_count",
        "sugars_100g", "salt_100g", "fat_100g", "saturated_fat_100g", "fiber_100g", "proteins_100g",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "rows": len(rows),
        "unique_products": len({row["barcode"] for row in rows}),
        "output": str(output_path),
    }
    output_path.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
