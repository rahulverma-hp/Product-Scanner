from __future__ import annotations

from typing import Any

from Backend.lifeve.hf_category import predict_categories
from Backend.lifeve.hf_ner import analyze_ingredients_text


def enrich_product(product: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run optional Hugging Face add-ons. Never raises — scan must stay fast."""
    enriched = dict(product)
    insights: dict[str, Any] = {}

    try:
        ingredients_text = enriched.get("ingredients_text") or ""
        ner = analyze_ingredients_text(ingredients_text)
        if ner is not None:
            insights["ingredient_ner"] = ner
    except Exception as exc:
        insights["ingredient_ner"] = {
            "status": "error",
            "error": f"{exc.__class__.__name__}: {exc}",
        }

    try:
        category = predict_categories(enriched)
        if category is not None:
            insights["category_prediction"] = category
            if category.get("category_names"):
                enriched["inferred_categories"] = category["category_names"]
    except Exception as exc:
        insights["category_prediction"] = {
            "status": "error",
            "error": f"{exc.__class__.__name__}: {exc}",
        }

    return enriched, insights
