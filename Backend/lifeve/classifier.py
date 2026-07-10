from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from Backend.lifeve.features import FEATURE_COLUMNS, FLAG_COLUMNS

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "health_classifier.joblib"


class HealthClassifier:
    def __init__(self, artifact: dict[str, Any]):
        self.pipeline = artifact["pipeline"]
        self.label_encoder = artifact["label_encoder"]
        self.feature_columns = artifact.get("feature_columns", FEATURE_COLUMNS)
        self.flags_pipeline = artifact.get("flags_pipeline")
        self.flag_columns = artifact.get("flag_columns", FLAG_COLUMNS)
        self.model_type = artifact.get("model_type", "random_forest")

    @classmethod
    def load(cls, path: str | Path | None = None) -> "HealthClassifier | None":
        model_path = Path(path or os.getenv("CLASSIFIER_MODEL_PATH", DEFAULT_MODEL_PATH))
        if not model_path.exists():
            return None
        artifact = joblib.load(model_path)
        return cls(artifact)

    def predict(self, feature_row: dict[str, Any]) -> dict[str, Any]:
        matrix = np.array([[feature_row[col] for col in self.feature_columns]], dtype=float)
        probabilities = self.pipeline.predict_proba(matrix)[0]
        predicted_idx = int(np.argmax(probabilities))
        label = self.label_encoder.inverse_transform([predicted_idx])[0]
        confidence = float(probabilities[predicted_idx])
        distribution = {
            self.label_encoder.inverse_transform([idx])[0]: float(prob)
            for idx, prob in enumerate(probabilities)
        }

        result: dict[str, Any] = {
            "health_tier": label,
            "confidence": round(confidence, 3),
            "distribution": distribution,
            "source": "trained_classifier",
            "model_type": self.model_type,
        }

        if self.flags_pipeline is not None:
            flag_probs = self.flags_pipeline.predict_proba(matrix)
            flags: dict[str, dict[str, float | bool]] = {}
            for idx, flag_name in enumerate(self.flag_columns):
                prob_row = flag_probs[idx][0]
                positive_prob = float(prob_row[1]) if len(prob_row) > 1 else float(prob_row[0])
                flags[flag_name] = {
                    "active": positive_prob >= 0.5,
                    "confidence": round(positive_prob, 3),
                }
            result["flags"] = flags

        return result


def save_classifier(artifact: dict[str, Any], path: str | Path = DEFAULT_MODEL_PATH) -> Path:
    model_path = Path(path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)
    metadata_path = model_path.with_suffix(".json")
    metadata_path.write_text(
        json.dumps(
            {
                "feature_columns": artifact.get("feature_columns", FEATURE_COLUMNS),
                "flag_columns": artifact.get("flag_columns", FLAG_COLUMNS),
                "labels": list(artifact["label_encoder"].classes_),
                "model_type": artifact.get("model_type", "random_forest"),
                "metrics": artifact.get("metrics", {}),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return model_path
