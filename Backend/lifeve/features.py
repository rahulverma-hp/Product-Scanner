from __future__ import annotations

from typing import Any

from Backend.lifeve.health_engine import BAD_KEYWORDS, DEFAULT_PROFILE, GOOD_KEYWORDS, _to_float, _resolve_profile_type, evaluate_health

NUTRISCORE_MAP = {"a": 4, "b": 3, "c": 2, "d": 1, "e": 0, "unknown": 1}
PROFILE_MAP = {"adult_male": 0, "adult_female": 1, "kid": 2, "unknown": 0}
FLAG_COLUMNS = [
    "high_sugar",
    "high_salt",
    "high_fat",
    "high_saturated_fat",
    "has_palm_oil",
    "has_artificial_sweetener",
    "has_whole_grain",
]


def derive_health_tier(product: dict[str, Any], health: dict[str, Any]) -> str:
    score = 0.0
    nutriscore = (product.get("nutriscore_grade") or product.get("nutrition_grades") or "unknown").lower()
    if nutriscore in ("a", "b"):
        score += 2
    elif nutriscore == "c":
        score += 0.5
    elif nutriscore in ("d", "e"):
        score -= 2

    score += len(health.get("pros", [])) * 1.0
    score -= len(health.get("cons", [])) * 1.25
    score -= len(health.get("high_nutrients", [])) * 1.0
    score += len(health.get("good_ingredients", [])) * 0.5
    score -= len(health.get("bad_ingredients", [])) * 0.75

    profile_eval = health.get("profile_evaluation") or {}
    sugar_pct = profile_eval.get("sugar_percentage_of_daily_limit")
    if sugar_pct is not None:
        if sugar_pct > 50:
            score -= 2
        elif sugar_pct > 20:
            score -= 1

    if score >= 1.5:
        return "healthy"
    if score <= -1.5:
        return "avoid"
    return "moderate"


def derive_flag_labels(health: dict[str, Any], ingredients_text: str) -> dict[str, int]:
    ingredients_text = (ingredients_text or "").lower()
    nutrients = health.get("nutrients") or {}
    high = {item["nutrient"] for item in health.get("high_nutrients", [])}

    return {
        "high_sugar": int("sugar" in high or (nutrients.get("sugars") or 0) > 10),
        "high_salt": int("salt" in high or (nutrients.get("salt") or 0) > 1.2),
        "high_fat": int("fat" in high or (nutrients.get("fat") or 0) > 17.5),
        "high_saturated_fat": int(
            "saturated fat" in high or (nutrients.get("saturated_fat") or 0) > 5
        ),
        "has_palm_oil": int("palm oil" in ingredients_text),
        "has_artificial_sweetener": int(
            any(word in ingredients_text for word in ("aspartame", "sucralose", "acesulfame"))
        ),
        "has_whole_grain": int(any(word in ingredients_text for word in ("whole grain", "wholegrain", "oats"))),
    }


def extract_feature_row(
    product: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
) -> dict[str, float | int | str]:
    profile = profile or DEFAULT_PROFILE
    profile_type, weight_kg = _resolve_profile_type(profile)
    try:
        age = float(profile.get("age") or 30)
    except (TypeError, ValueError):
        age = 30.0

    health = health or evaluate_health(product, profile=profile)
    nutriments = product.get("nutriments", {}) or {}
    ingredients_text = (product.get("ingredients_text", "") or "").lower()
    nutriscore = (product.get("nutriscore_grade") or "unknown").lower()

    def nutrient(key: str) -> float:
        value = nutriments.get(f"{key}_100g", nutriments.get(key))
        parsed = _to_float(value)
        return parsed if parsed is not None else -1.0

    row: dict[str, float | int | str] = {
        "barcode": product.get("code") or product.get("_id") or "",
        "profile_type": profile_type or "adult_male",
        "age": age,
        "weight_kg": float(weight_kg or 70.0),
        "nutriscore_encoded": NUTRISCORE_MAP.get(nutriscore[:1] if nutriscore else "unknown", 1),
        "profile_encoded": PROFILE_MAP.get(profile_type or "adult_male", 0),
        "ingredient_text_len": len(ingredients_text),
        "good_keyword_hits": sum(1 for word in GOOD_KEYWORDS if word in ingredients_text),
        "bad_keyword_hits": sum(1 for word in BAD_KEYWORDS if word in ingredients_text),
        "pros_count": len(health.get("pros", [])),
        "cons_count": len(health.get("cons", [])),
        "high_nutrient_count": len(health.get("high_nutrients", [])),
        "sugars_100g": nutrient("sugars"),
        "salt_100g": nutrient("salt"),
        "fat_100g": nutrient("fat"),
        "saturated_fat_100g": nutrient("saturated-fat"),
        "fiber_100g": nutrient("fiber"),
        "proteins_100g": nutrient("proteins"),
        "health_tier": derive_health_tier(product, health),
    }
    row.update(derive_flag_labels(health, ingredients_text))
    return row


FEATURE_COLUMNS = [
    "nutriscore_encoded",
    "profile_encoded",
    "age",
    "weight_kg",
    "ingredient_text_len",
    "good_keyword_hits",
    "bad_keyword_hits",
    "pros_count",
    "cons_count",
    "high_nutrient_count",
    "sugars_100g",
    "salt_100g",
    "fat_100g",
    "saturated_fat_100g",
    "fiber_100g",
    "proteins_100g",
    *FLAG_COLUMNS,
]
