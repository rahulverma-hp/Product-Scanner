from __future__ import annotations

import io
import os
from typing import Any

INGREDIENT_DETECTION_MODEL = "openfoodfacts/ingredient-detection"
NUTRITION_EXTRACTOR_MODEL = "openfoodfacts/nutrition-extractor"

_ingredient_detector = None
_nutrition_extractor = None


def _hf_vision_enabled() -> bool:
    return os.getenv("HF_VISION_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _load_image(file_storage):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Install Pillow for package photo scanning: pip install -r Backend/requirements-hf.txt") from exc
    image = Image.open(file_storage.stream).convert("RGB")
    return image


def extract_ingredients_from_image(file_storage) -> dict[str, Any]:
    if not _hf_vision_enabled():
        return {
            "enabled": False,
            "error": "Set HF_VISION_ENABLED=1 to use package photo ingredient detection.",
        }

    global _ingredient_detector
    try:
        if _ingredient_detector is None:
            from transformers import pipeline

            _ingredient_detector = pipeline(
                "image-to-text",
                model=os.getenv("HF_INGREDIENT_MODEL", INGREDIENT_DETECTION_MODEL),
            )
        image = _load_image(file_storage)
        output = _ingredient_detector(image)
        text = ""
        if isinstance(output, list) and output:
            text = output[0].get("generated_text") or output[0].get("text") or ""
        elif isinstance(output, dict):
            text = output.get("generated_text") or output.get("text") or ""
        text = text.strip()
        return {
            "enabled": True,
            "model": INGREDIENT_DETECTION_MODEL,
            "ingredients_text": text or None,
            "raw": output,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "model": INGREDIENT_DETECTION_MODEL,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def extract_nutrition_from_image(file_storage) -> dict[str, Any]:
    if not _hf_vision_enabled():
        return {
            "enabled": False,
            "error": "Set HF_VISION_ENABLED=1 to use package photo nutrition extraction.",
        }

    global _nutrition_extractor
    try:
        if _nutrition_extractor is None:
            from transformers import pipeline

            _nutrition_extractor = pipeline(
                "document-question-answering",
                model=os.getenv("HF_NUTRITION_MODEL", NUTRITION_EXTRACTOR_MODEL),
            )
        image = _load_image(file_storage)
        questions = [
            "What is the sugar per 100g?",
            "What is the fat per 100g?",
            "What is the salt per 100g?",
        ]
        answers = []
        for question in questions:
            try:
                answers.append(_nutrition_extractor(image=image, question=question))
            except TypeError:
                answers.append(_nutrition_extractor(question=question, image=image))
        return {
            "enabled": True,
            "model": NUTRITION_EXTRACTOR_MODEL,
            "answers": answers,
            "note": "Experimental — map answers into nutriments in a future pass.",
        }
    except Exception as exc:
        return {
            "enabled": True,
            "model": NUTRITION_EXTRACTOR_MODEL,
            "error": f"{exc.__class__.__name__}: {exc}",
        }
