#!/usr/bin/env bash
set -euo pipefail

pip install -r Backend/requirements.txt -r Backend/requirements-ml.txt

python ml/build_dataset.py --use-samples
python ml/train_classifier.py --model random_forest
