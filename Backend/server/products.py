from __future__ import annotations

import json
import os
from typing import Any

import requests

from .config import BASE_DIR


def _load_local_products() -> dict[str, Any]:
    path = os.path.join(BASE_DIR, "products.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def fetch_sample_catalog_product(barcode):
    """Offline fallback from Backend/data/sample_products.json (OpenFoodFacts-shaped list)."""
    path = os.path.join(BASE_DIR, "data", "sample_products.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return None
    if not isinstance(items, list):
        return None
    barcode = str(barcode).strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("code") or "").strip() == barcode:
            return item
    return None


def fetch_local_product_off_shape(barcode):
    """
    Optional offline fallback using Backend/products.json:
    {
      "123": { "name": "...", "description": "ingredients text ..." }
    }
    """
    db = _load_local_products()
    rec = db.get(str(barcode))
    if not isinstance(rec, dict):
        return None
    name = (rec.get("name") or "").strip() or f"Product {barcode}"
    ingredients = (rec.get("description") or "").strip()
    return {
        "product_name": name,
        "brands": "Local database",
        "ingredients_text": ingredients or "No ingredient info available",
        "nutriscore_grade": "N/A",
        "nutriments": {},
    }


def fetch_openfoodfacts_product(barcode):
    """
    Fetch OFF product JSON. Returns (product_dict_or_None, error_string_or_None).
    """
    off_url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    headers = {
        # OFF blocks some requests without a recognizable UA
        "User-Agent": "HealthScanner/1.0 (+local-dev; contact: none)",
        "Accept": "application/json",
    }
    try:
        r = requests.get(off_url, headers=headers, timeout=20)
    except Exception as e:
        return None, f"OpenFoodFacts request failed: {e.__class__.__name__}"

    if r.status_code != 200:
        # Many environments return 403 for automated requests
        return None, f"OpenFoodFacts HTTP {r.status_code}"

    try:
        body = r.json()
    except Exception:
        return None, "OpenFoodFacts returned non-JSON response"

    if body.get("status") != 1:
        return None, "Not found in OpenFoodFacts"

    product = body.get("product") or {}
    return product, None


def _pick_translation(trans_obj, prefer=("en", "de", "fr")):
    """Pick a string from FoodRepo-style translation dicts."""
    if not trans_obj or not isinstance(trans_obj, dict):
        return ""
    for lang in prefer:
        val = trans_obj.get(lang)
        if val is not None and str(val).strip():
            return str(val).strip()
    for val in trans_obj.values():
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _foodrepo_nutrients_to_off_nutriments(nutrients):
    """Map FoodRepo nutrients object to OpenFoodFacts-style nutriments (per 100g keys)."""
    if not nutrients or not isinstance(nutrients, dict):
        return {}
    slug_map = {
        "sugars": "sugars",
        "sugar": "sugars",
        "total_sugars": "sugars",
        "salt": "salt",
        "fat": "fat",
        "total_fat": "fat",
        "saturated_fat": "saturated-fat",
        "saturated_fatty_acids": "saturated-fat",
        "fiber": "fiber",
        "dietary_fiber": "fiber",
        "fibre": "fiber",
        "proteins": "proteins",
        "protein": "proteins",
    }
    out = {}
    for slug, obj in nutrients.items():
        if not isinstance(obj, dict):
            continue
        ph = obj.get("per_hundred")
        if ph is None:
            continue
        try:
            ph = float(ph)
        except (TypeError, ValueError):
            continue
        key = slug_map.get(str(slug).lower().replace(" ", "_"))
        if not key:
            continue
        out[f"{key}_100g"] = ph
    return out


def _foodrepo_attributes_to_off_product(attrs):
    """Build an OFF-shaped product dict from FoodRepo product attributes."""
    if not attrs or not isinstance(attrs, dict):
        return None
    name = _pick_translation(
        attrs.get("display_name_translations") or attrs.get("name_translations") or {}
    )
    ingredients = _pick_translation(attrs.get("ingredients_translations") or {})
    nutriments = _foodrepo_nutrients_to_off_nutriments(attrs.get("nutrients") or {})
    bc = attrs.get("barcode")
    if not name and bc:
        name = f"Product {bc}"
    if not name:
        name = "Unknown product"
    return {
        "product_name": name,
        "brands": "Unknown brand",
        "ingredients_text": ingredients or "No ingredient info available",
        "nutriscore_grade": "N/A",
        "nutriments": nutriments,
    }


def fetch_foodrepo_off_product(barcode):
    """
    If FOODREPO_API_KEY is set, look up barcode on Open Food Repo and return an OFF-shaped product dict.
    See https://www.foodrepo.org/en/developers — Authorization: Token token="YOUR_KEY"
    """
    api_key = (os.environ.get("FOODREPO_API_KEY") or "").strip()
    if not api_key:
        return None
    barcode = str(barcode).strip()
    if not barcode:
        return None
    headers = {"Authorization": f'Token token="{api_key}"'}
    url = "https://www.foodrepo.org/api/v3/products"
    try:
        r = requests.get(
            url,
            headers=headers,
            params={"barcodes": barcode, "page[size]": 1},
            timeout=20,
        )
        if r.status_code != 200:
            r = requests.get(
                url,
                headers=headers,
                params={"filter[barcodes]": barcode, "page[size]": 1},
                timeout=20,
            )
        if r.status_code != 200:
            return None
        body = r.json()
    except Exception:
        return None
    data = body.get("data")
    if not data:
        return None
    item = data[0] if isinstance(data, list) else data
    if not isinstance(item, dict):
        return None
    attrs = item.get("attributes")
    if not isinstance(attrs, dict):
        attrs = item
    return _foodrepo_attributes_to_off_product(attrs)

