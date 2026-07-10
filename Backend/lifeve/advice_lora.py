from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from Backend.lifeve.health_engine import evaluate_health

DEFAULT_LORA_DIR = Path(__file__).resolve().parents[1] / "models" / "lifeve-advice-lora"
DEFAULT_BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
_load_lock = threading.Lock()

INSTRUCTION = (
    "You are Lifeve, a grocery health assistant. Using only the structured facts provided, "
    "write personalised shopper advice. Do not invent nutrients or medical claims."
)

PROMPT_TEMPLATE = """### Instruction:
{instruction}

### Input:
{input}

### Response:
"""


def _facts_payload(product: dict[str, Any], profile: dict[str, Any] | None, health: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_name": product.get("product_name"),
        "brand": product.get("brands"),
        "nutriscore": product.get("nutriscore_grade"),
        "ingredients": product.get("ingredients_text"),
        "health": health,
        "profile": profile or {},
    }


def _read_metadata(lora_dir: Path) -> dict[str, Any]:
    metadata_path = lora_dir / "training_metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


class AdviceLoraModel:
    def __init__(self, lora_dir: Path, base_model: str):
        self.lora_dir = lora_dir
        self.base_model = base_model
        self._model = None
        self._tokenizer = None
        self._device = "cpu"

    @classmethod
    def load(cls, path: str | Path | None = None) -> "AdviceLoraModel | None":
        lora_dir = Path(path or os.getenv("LORA_ADVICE_PATH", DEFAULT_LORA_DIR))
        if not lora_dir.exists() or not (lora_dir / "adapter_config.json").exists():
            return None
        metadata = _read_metadata(lora_dir)
        base_model = os.getenv("LORA_BASE_MODEL", metadata.get("base_model", DEFAULT_BASE_MODEL))
        return cls(lora_dir=lora_dir, base_model=base_model)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with _load_lock:
            if self._model is not None:
                return
            try:
                import torch
                from peft import PeftModel
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                raise RuntimeError(
                    "LoRA inference requires ML packages. Install: pip install -r Backend/requirements-llm.txt"
                ) from exc

            device = "cuda" if torch.cuda.is_available() else "cpu"

            tokenizer = AutoTokenizer.from_pretrained(str(self.lora_dir))
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            base = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            )
            base.to(device)
            model = PeftModel.from_pretrained(base, str(self.lora_dir))
            model.to(device)
            model.eval()

            self._tokenizer = tokenizer
            self._model = model
            self._device = device

    def generate(
        self,
        product: dict[str, Any],
        profile: dict[str, Any] | None = None,
        *,
        health: dict[str, Any] | None = None,
        max_new_tokens: int = 180,
    ) -> str:
        import torch

        self._ensure_loaded()
        health = health or evaluate_health(product, profile=profile)
        facts = _facts_payload(product, profile, health)
        prompt = PROMPT_TEMPLATE.format(
            instruction=INSTRUCTION,
            input=json.dumps(facts, ensure_ascii=False),
        )

        inputs = self._tokenizer(prompt, return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

        generated = output_ids[0][inputs["input_ids"].shape[-1] :]
        text = self._tokenizer.decode(generated, skip_special_tokens=True).strip()
        return text


_advisor: AdviceLoraModel | None | bool = None


def get_advice_lora_model() -> AdviceLoraModel | None:
    global _advisor
    if _advisor is False:
        return None
    if _advisor is None:
        _advisor = AdviceLoraModel.load() or False
    return _advisor if _advisor is not False else None


def call_lora_advice(
    product: dict[str, Any],
    profile: dict[str, Any] | None,
    *,
    health: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if os.getenv("LORA_ADVICE_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return None, "LoRA advice disabled via LORA_ADVICE_DISABLED."

    enabled = os.getenv("LORA_ADVICE_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return None, "LoRA advice not enabled. Set LORA_ADVICE_ENABLED=1 in Backend/.env to use your fine-tuned model."

    advisor = get_advice_lora_model()
    if advisor is None:
        return None, "LoRA advice model not found. Place weights in Backend/models/lifeve-advice-lora/."

    try:
        text = advisor.generate(product, profile, health=health)
        if not text:
            return None, "LoRA model returned empty advice."
        return {
            "personalised_summary": text,
            "source": "fine_tuned_lora",
            "base_model": advisor.base_model,
            "disclaimer": "General food guidance only — not medical advice.",
        }, None
    except MemoryError:
        return None, "LoRA advice skipped: not enough memory to run the local model."
    except Exception as exc:
        return None, f"LoRA advice failed: {exc.__class__.__name__}: {exc}"
