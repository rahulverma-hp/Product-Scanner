#!/usr/bin/env python3
"""Train Level 1 health-tier + ingredient/nutrient flag classifiers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

from Backend.lifeve.classifier import save_classifier
from Backend.lifeve.features import FEATURE_COLUMNS, FLAG_COLUMNS

DEFAULT_DATASET = ROOT / "Backend" / "data" / "health_classifier_dataset.csv"
DEFAULT_MODEL = ROOT / "Backend" / "models" / "health_classifier.joblib"


def build_tier_model(model_name: str):
    if model_name == "logistic":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
        ])
    if model_name == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise SystemExit("Install xgboost: pip install xgboost") from exc
        return Pipeline([
            ("model", XGBClassifier(
                n_estimators=300,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="multi:softprob",
                eval_metric="mlogloss",
                random_state=42,
                n_jobs=-1,
            )),
        ])
    return Pipeline([
        ("model", RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])


def build_flags_model(model_name: str):
    if model_name == "logistic":
        base = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    elif model_name == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise SystemExit("Install xgboost: pip install xgboost") from exc
        base = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
    else:
        base = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
    return MultiOutputClassifier(base, n_jobs=-1)


def tier_report(y_test, y_pred, labels) -> dict:
    report = classification_report(
        y_test,
        y_pred,
        labels=list(range(len(labels))),
        target_names=list(labels),
        output_dict=True,
        zero_division=0,
    )
    return {
        "accuracy": float(report["accuracy"]),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "labels": list(labels),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--model-out", default=str(DEFAULT_MODEL))
    parser.add_argument("--model", choices=["random_forest", "logistic", "xgboost"], default="random_forest")
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"Missing dataset: {dataset_path}. Run: python ml/build_dataset.py --use-samples")

    frame = pd.read_csv(dataset_path)
    X = frame[FEATURE_COLUMNS]
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(frame["health_tier"].astype(str))
    y_flags = frame[FLAG_COLUMNS].astype(int)

    X_train, X_test, y_train, y_test, y_flags_train, y_flags_test = train_test_split(
        X, y, y_flags, test_size=args.test_size, random_state=42, stratify=y if len(set(y)) > 1 else None
    )

    tier_pipeline = build_tier_model(args.model)
    tier_pipeline.fit(X_train, y_train)
    y_pred = tier_pipeline.predict(X_test)
    labels = label_encoder.classes_

    flags_pipeline = build_flags_model(args.model)
    flags_pipeline.fit(X_train, y_flags_train)
    y_flags_pred = flags_pipeline.predict(X_test)
    flag_f1 = float(f1_score(y_flags_test, y_flags_pred, average="macro", zero_division=0))

    metrics = {
        "tier": tier_report(y_test, y_pred, labels),
        "flags_macro_f1": flag_f1,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
    }

    save_classifier({
        "pipeline": tier_pipeline,
        "label_encoder": label_encoder,
        "flags_pipeline": flags_pipeline,
        "feature_columns": FEATURE_COLUMNS,
        "flag_columns": FLAG_COLUMNS,
        "model_type": args.model,
        "metrics": metrics,
    }, args.model_out)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
