from __future__ import annotations

import os
from typing import Any

import requests

ROBOTOFF_CATEGORY_URL = "https://robotoff.openfoodfacts.org/api/v1/predict/categories"


def _hf_category_enabled() -> bool:
    if os.getenv("HF_CATEGORY_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return os.getenv("HF_MODELS_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _product_has_categories(product: dict[str, Any]) -> bool:
    for key in ("categories", "categories_tags", "categories_hierarchy"):
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
    return False


def _build_robotoff_product(product: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if product.get("product_name"):
        payload["product_name"] = product["product_name"]
    if product.get("ingredients_text"):
        payload["ingredients"] = product["ingredients_text"]
    nutriments = product.get("nutriments") or {}
    if nutriments:
        payload["nutriments"] = nutriments
    return payload


def predict_categories(product: dict[str, Any]) -> dict[str, Any] | None:
    if not _hf_category_enabled():
        return None
    if _product_has_categories(product):
        return None

    robotoff_product = _build_robotoff_product(product)
    if not robotoff_product:
        return None

    try:
        response = requests.post(
            ROBOTOFF_CATEGORY_URL,
            json={"product": robotoff_product},
            timeout=20,
            headers={"User-Agent": "Lifeve-Scanner/1.0"},
        )
        if response.status_code != 200:
            return {
                "source": "openfoodfacts/robotoff",
                "categories": [],
                "error": f"Robotoff HTTP {response.status_code}",
            }
        body = response.json()
    except requests.RequestException as exc:
        return {
            "source": "openfoodfacts/robotoff",
            "categories": [],
            "error": f"{exc.__class__.__name__}: {exc}",
        }

    predictions = body.get("predictions") or body.get("categories") or body
    categories: list[dict[str, Any]] = []
    if isinstance(predictions, list):
        for item in predictions:
            if isinstance(item, dict):
                name = item.get("category") or item.get("value") or item.get("name")
                score = item.get("score") or item.get("confidence")
                if name:
                    categories.append({
                        "name": str(name),
                        "score": round(float(score), 3) if score is not None else None,
                    })
            elif isinstance(item, str):
                categories.append({"name": item, "score": None})

    categories = categories[:8]
    return {
        "source": "openfoodfacts/robotoff",
        "model": "openfoodfacts/category_classifier",
        "categories": categories,
        "category_names": [c["name"] for c in categories],
    }
