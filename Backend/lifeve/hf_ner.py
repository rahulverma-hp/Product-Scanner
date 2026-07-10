from __future__ import annotations

import os
import re
import threading
from typing import Any

NER_MODEL_ID = "sgarbi/bert-fda-nutrition-ner"

RISKY_ENTITY_GROUPS = {
    "COLORANTS",
    "ADDITIVES",
    "FLAVORING",
    "STIMULANTS",
    "EMULSIFIERS",
    "ACIDS",
}
GOOD_ENTITY_GROUPS = {
    "DIETARYFIBER",
    "PROBIOTICS",
    "PROTEIN",
    "ANTIOXIDANTS",
    "VITAMINS",
    "MINERALS",
}

_CONSUMER_LABELS = {
    "PROTEIN": "protein",
    "EMULSIFIERS": "emulsifier",
    "FLAVORING": "flavouring",
    "COLORANTS": "colour additive",
    "ADDITIVES": "additive",
    "ACIDS": "acid",
    "ANTIOXIDANTS": "antioxidant",
    "VITAMINS": "vitamin",
    "MINERALS": "mineral",
    "DIETARYFIBER": "fibre",
    "PROBIOTICS": "probiotic",
    "LIPIDS": "fat source",
    "CARBOHYDRATES": "carbohydrate",
    "STIMULANTS": "stimulant",
}

_JUNK_ENTITY_PHRASES = (
    "may contain",
    "traces of",
)

_ner_pipeline = None
_ner_failed = False
_ner_loading = False
_preload_started = False
_load_lock = threading.Lock()


def _hf_ner_enabled() -> bool:
    if os.getenv("HF_NER_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return os.getenv("HF_MODELS_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def ner_is_ready() -> bool:
    return _ner_pipeline is not None and not _ner_failed


def warm_hf_models() -> None:
    """Preload HF models in the background so /scan never blocks on first download."""
    global _preload_started
    if not _hf_ner_enabled() or _preload_started or _ner_failed:
        return
    _preload_started = True
    threading.Thread(target=_load_ner_pipeline, daemon=True, name="lifeve-hf-ner-preload").start()


def _normalize_entity_group(label: str) -> str:
    label = (label or "").upper()
    if label.startswith("B-") or label.startswith("I-"):
        return label[2:]
    return label


def consumer_label_for_group(group: str) -> str:
    key = _normalize_entity_group(group)
    return _CONSUMER_LABELS.get(key, key.lower().replace("_", " "))


def _surface_from_span(text: str, start: int | None, end: int | None, fallback_word: str) -> str:
    if start is not None and end is not None and 0 <= start < end <= len(text):
        return text[start:end]
    return fallback_word


def _clean_entity_word(word: str) -> str:
    word = re.sub(r"(?:#|\uFF03){2}", "", word or "")
    word = word.replace("##", "")
    word = re.sub(r"\s+", " ", word.strip(" ,;.()"))
    return word


def is_displayable_entity(surface: str) -> bool:
    s = _clean_entity_word(surface)
    if not s:
        return False
    lowered = s.lower()
    if any(phrase in lowered for phrase in _JUNK_ENTITY_PHRASES):
        return False
    letters = sum(c.isalpha() for c in s)
    if letters == 0:
        return False
    if len(s) <= 2 and " " not in s:
        return False
    if letters < 3 and " " not in s:
        return False
    if letters / max(len(s), 1) < 0.55:
        return False
    return True


def format_ingredient_signal_phrase(entry: dict[str, Any]) -> str | None:
    word = _clean_entity_word(entry.get("word") or "")
    if not is_displayable_entity(word):
        return None
    label = consumer_label_for_group(entry.get("entity_group") or "")
    return f"{word} ({label})"


def _normalize_entities(text: str, raw_entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for item in raw_entities or []:
        word = (item.get("word") or "").strip()
        if not word:
            continue
        start = item.get("start")
        end = item.get("end")
        group = _normalize_entity_group(item.get("entity_group") or item.get("entity") or "")
        score = float(item.get("score", 0.0))
        is_subword = word.startswith("##")

        if merged and is_subword and merged[-1]["entity_group"] == group:
            prev = merged[-1]
            if end is not None:
                prev["end"] = end
            prev["word"] = _clean_entity_word(_surface_from_span(text, prev.get("start"), prev.get("end"), ""))
            prev["score"] = max(float(prev["score"]), score)
            continue

        surface = _clean_entity_word(_surface_from_span(text, start, end, word))
        if not surface or group == "O":
            continue
        merged.append({"word": surface, "entity_group": group, "score": score, "start": start, "end": end})

    result: list[dict[str, Any]] = []
    for entry in merged:
        if not is_displayable_entity(entry["word"]):
            continue
        result.append(
            {
                "word": entry["word"],
                "entity_group": entry["entity_group"],
                "score": entry["score"],
            }
        )
    return result


def _load_ner_pipeline() -> None:
    global _ner_pipeline, _ner_failed, _ner_loading
    if _ner_pipeline is not None or _ner_failed or not _hf_ner_enabled():
        return
    with _load_lock:
        if _ner_pipeline is not None or _ner_failed:
            return
        _ner_loading = True
        try:
            from transformers import pipeline

            _ner_pipeline = pipeline(
                "token-classification",
                model=os.getenv("HF_NER_MODEL", NER_MODEL_ID),
                aggregation_strategy="simple",
            )
        except Exception:
            _ner_failed = True
        finally:
            _ner_loading = False


def analyze_ingredients_text(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text or not _hf_ner_enabled():
        return None

    if _ner_pipeline is None:
        if _ner_failed:
            return {
                "model": NER_MODEL_ID,
                "status": "unavailable",
                "message": "Smart ingredient reading is unavailable right now.",
            }
        if _ner_loading:
            return {
                "model": NER_MODEL_ID,
                "status": "loading",
                "message": "Still reading ingredients — try scanning again in a moment.",
            }
        return {
            "model": NER_MODEL_ID,
            "status": "loading",
            "message": "Still reading ingredients — try scanning again in a moment.",
        }

    try:
        raw_entities = _ner_pipeline(text)
    except Exception as exc:
        return {
            "model": NER_MODEL_ID,
            "status": "error",
            "entities": [],
            "risk_entities": [],
            "positive_entities": [],
            "error": f"{exc.__class__.__name__}: {exc}",
        }

    entities: list[dict[str, Any]] = []
    risk_entities: list[dict[str, Any]] = []
    positive_entities: list[dict[str, Any]] = []

    for item in _normalize_entities(text, raw_entities or []):
        group = item["entity_group"]
        word = item["word"]
        entry = {
            "word": word,
            "entity_group": group,
            "score": round(float(item.get("score", 0.0)), 3),
        }
        entities.append(entry)
        if group in RISKY_ENTITY_GROUPS:
            risk_entities.append(entry)
        if group in GOOD_ENTITY_GROUPS:
            positive_entities.append(entry)

    return {
        "model": NER_MODEL_ID,
        "status": "ready",
        "entities": entities,
        "risk_entities": risk_entities,
        "positive_entities": positive_entities,
        "risk_flags": sorted({e["entity_group"].lower() for e in risk_entities}),
        "positive_flags": sorted({e["entity_group"].lower() for e in positive_entities}),
    }
