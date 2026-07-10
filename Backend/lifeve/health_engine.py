from __future__ import annotations

from typing import Any

from Backend.lifeve.hf_ner import format_ingredient_signal_phrase

GOOD_KEYWORDS = [
    "whole grain",
    "wholegrain",
    "oats",
    "vegetable",
    "fruit",
    "fruits",
    "nuts",
    "seeds",
    "olive oil",
    "canola oil",
    "high fiber",
    "legume",
    "lentil",
    "bean",
    "peas",
]

BAD_KEYWORDS = [
    "sugar",
    "glucose",
    "fructose",
    "corn syrup",
    "high fructose",
    "palm oil",
    "hydrogenated",
    "trans fat",
    "msg",
    "monosodium glutamate",
    "artificial sweetener",
    "aspartame",
    "acesulfame k",
    "sucralose",
]

DEFAULT_PROFILE = {"gender": "male", "age": 30, "weight_kg": 70.0, "height_cm": 175}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_profile_type(profile: dict[str, Any] | None) -> tuple[str | None, float | None]:
    profile = profile or {}
    gender = (profile.get("gender") or "male").lower()
    age = profile.get("age")
    weight_kg = _to_float(profile.get("weight_kg"))

    try:
        age_int = int(age) if age is not None else None
    except (TypeError, ValueError):
        age_int = None

    if age_int is not None and age_int < 13:
        return "kid", weight_kg
    if gender == "female":
        return "adult_female", weight_kg
    if gender == "male":
        return "adult_male", weight_kg
    return "adult_male", weight_kg


def evaluate_health(
    product: dict[str, Any],
    profile: dict[str, Any] | None = None,
    *,
    profile_type: str | None = None,
    weight_kg: float | None = None,
    hf_insights: dict[str, Any] | None = None,
):
    nutriments = product.get("nutriments", {}) or {}
    ingredients_text = (product.get("ingredients_text", "") or "").lower()

    if profile_type is None:
        profile_type, weight_kg = _resolve_profile_type(profile)

    def get_nutrient(key):
        value = nutriments.get(f"{key}_100g")
        if value is None:
            value = nutriments.get(key)
        return _to_float(value)

    sugar = get_nutrient("sugars")
    salt = get_nutrient("salt")
    fat = get_nutrient("fat")
    sat_fat = get_nutrient("saturated-fat")
    fiber = get_nutrient("fiber")
    protein = get_nutrient("proteins")

    good_ingredients = [word for word in GOOD_KEYWORDS if word in ingredients_text]
    bad_ingredients = [word for word in BAD_KEYWORDS if word in ingredients_text]

    ner = (hf_insights or {}).get("ingredient_ner") or {}
    if ner.get("status") == "ready":
        for entry in ner.get("risk_entities") or []:
            phrase = format_ingredient_signal_phrase(entry)
            if phrase and phrase not in bad_ingredients:
                bad_ingredients.append(phrase)
        for entry in ner.get("positive_entities") or []:
            phrase = format_ingredient_signal_phrase(entry)
            if phrase and phrase not in good_ingredients:
                good_ingredients.append(phrase)

    category_prediction = (hf_insights or {}).get("category_prediction") or {}
    category_names = category_prediction.get("category_names") or product.get("inferred_categories") or []
    category_notes: list[str] = []
    category_blob = " ".join(str(name) for name in category_names).lower()
    if category_blob:
        if any(token in category_blob for token in ("beverage", "drink", "soda", "juice")):
            category_notes.append("Predicted category: beverage — check sugar per serving.")
        if any(token in category_blob for token in ("snack", "chocolate", "candy", "biscuit", "chip")):
            category_notes.append("Predicted category: snack — watch portion size.")
        if any(token in category_blob for token in ("oil", "spread", "butter")):
            category_notes.append("Predicted category: fat-rich food — check saturated fat.")

    high_nutrients = []
    if sugar is not None and sugar > 10:
        high_nutrients.append({"nutrient": "sugar", "amount_per_100g": sugar})
    if salt is not None and salt > 1.2:
        high_nutrients.append({"nutrient": "salt", "amount_per_100g": salt})
    if fat is not None and fat > 17.5:
        high_nutrients.append({"nutrient": "fat", "amount_per_100g": fat})
    if sat_fat is not None and sat_fat > 5:
        high_nutrients.append({"nutrient": "saturated fat", "amount_per_100g": sat_fat})

    pros = []
    cons = []
    if fiber is not None and fiber >= 3:
        pros.append("Good source of fiber")
    if protein is not None and protein >= 8:
        pros.append("High protein content")
    if sugar is not None and sugar > 15:
        cons.append("Very high in sugar")
    elif sugar is not None and sugar > 10:
        cons.append("High in sugar")
    if salt is not None and salt > 1.5:
        cons.append("Very high in salt")
    elif salt is not None and salt > 1.2:
        cons.append("High in salt")
    if sat_fat is not None and sat_fat > 10:
        cons.append("Very high in saturated fat")
    elif sat_fat is not None and sat_fat > 5:
        cons.append("High in saturated fat")

    if ner.get("status") == "ready":
        for flag in ner.get("risk_flags") or []:
            note = f"Contains {flag.replace('_', ' ')}"
            if note not in cons:
                cons.append(note)

    for note in category_notes:
        if note not in cons:
            cons.append(note)

    if not pros and not cons and not high_nutrients and not bad_ingredients and not good_ingredients:
        generic_summary = "Not enough information to evaluate this product."
    else:
        parts = []
        if pros:
            parts.append("Positives: " + ", ".join(pros) + ".")
        if cons:
            parts.append("Concerns: " + ", ".join(cons) + ".")
        if high_nutrients:
            detail = ", ".join(
                f"{n['nutrient']} is high ({n['amount_per_100g']} g per 100 g)" for n in high_nutrients
            )
            parts.append("High nutrients: " + detail + ".")
        if bad_ingredients:
            parts.append("Contains less healthy ingredients like " + ", ".join(bad_ingredients) + ".")
        if good_ingredients:
            parts.append("Includes better ingredients like " + ", ".join(good_ingredients) + ".")
        generic_summary = " ".join(parts)

    profile_info = None
    if profile_type:
        pt = profile_type.lower()
        if pt in ("male", "man", "adult_male"):
            base_limit = 50.0
        elif pt in ("female", "woman", "adult_female"):
            base_limit = 40.0
        elif pt in ("kid", "child"):
            base_limit = 25.0
        else:
            base_limit = 40.0

        if weight_kg:
            w = _to_float(weight_kg)
            if w and w > 0:
                factor = max(0.6, min(1.4, w / 70.0))
                base_limit *= factor

        daily_sugar_limit_g = round(base_limit, 1)
        sugar_per_100g = sugar
        percentage = None
        recommendation = None
        text = None

        if sugar_per_100g is not None and daily_sugar_limit_g > 0:
            percentage = round((sugar_per_100g / daily_sugar_limit_g) * 100, 1)
            if percentage < 20:
                recommendation = "generally fine in moderation"
            elif percentage < 50:
                recommendation = "okay occasionally, but watch your total sugar for the day"
            else:
                recommendation = "very sugary for your profile, limit portion size or frequency"

            text = (
                f"For your profile, an approximate daily added sugar limit is about "
                f"{daily_sugar_limit_g} g. 100 g of this product has about "
                f"{round(sugar_per_100g, 1)} g of sugar (~{percentage}% of your daily limit), "
                f"so it is {recommendation}."
            )
        else:
            text = (
                "Not enough sugar information is available for a personalised evaluation, "
                "but you can still use the generic health notes."
            )

        profile_info = {
            "profile_type": profile_type,
            "weight_kg": weight_kg,
            "daily_sugar_limit_g": daily_sugar_limit_g,
            "sugar_per_100g": sugar_per_100g,
            "sugar_percentage_of_daily_limit": percentage,
            "recommendation": recommendation,
            "summary": text,
        }
        if profile:
            profile_info["username"] = profile.get("display_name") or profile.get("username")

    return {
        "good_ingredients": sorted(set(good_ingredients)),
        "bad_ingredients": sorted(set(bad_ingredients)),
        "high_nutrients": high_nutrients,
        "pros": pros,
        "cons": cons,
        "generic_summary": generic_summary,
        "profile_evaluation": profile_info,
        "inferred_categories": category_names,
        "ingredient_ner": ner or None,
        "nutrients": {
            "sugars": sugar,
            "salt": salt,
            "fat": fat,
            "saturated_fat": sat_fat,
            "fiber": fiber,
            "proteins": protein,
        },
    }


def build_advice_text(health: dict) -> str:
    parts = [health.get("generic_summary") or ""]
    profile_eval = health.get("profile_evaluation") or {}
    if profile_eval.get("summary"):
        parts.append(profile_eval["summary"])
    return " ".join(part.strip() for part in parts if part and part.strip())


TRAINING_PROFILES = [
    {"gender": "male", "age": 30, "weight_kg": 80.0, "height_cm": 178},
    {"gender": "female", "age": 28, "weight_kg": 65.0, "height_cm": 165},
    {"gender": "male", "age": 10, "weight_kg": 35.0, "height_cm": 140},
]
