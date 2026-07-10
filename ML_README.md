# Lifeve Scanner — ML Training Guide

Correct project repo: `d:\Everything unwanted\Desktop\scaner project`

## Architecture

```text
Barcode → OpenFoodFacts / FoodRepo / local JSON
       → rule engine (facts + weak labels)
       → Level 1: YOUR trained classifier (healthy | moderate | avoid + flags)
       → personalised LLM via OpenRouter (production)
       → Level 2 (optional): fine-tuned small LLM on your advice style
```

**Rules own facts.** The classifier learns patterns from rule labels. The LLM explains for the shopper's profile.

---

## Level 1 — Train a small classifier

**Input:** ingredients + nutriments + profile  
**Output:** `healthy | moderate | avoid` plus flags like `high_sugar`, `has_palm_oil`, etc.

### Model options

| Flag | Algorithm |
|------|-----------|
| `--model random_forest` | Random Forest (default) |
| `--model logistic` | Logistic regression |
| `--model xgboost` | XGBoost |

### Data

- **Source:** OpenFoodFacts (barcode, ingredients, nutriments, Nutri-Score)
- **Labels:** derived from `Backend/lifeve/health_engine.py` rules
- **Offline fallback:** `Backend/data/sample_products.json` (20 products)
- **Target scale:** 1k–10k+ labeled rows for production quality

### Commands

```powershell
cd "d:\Everything unwanted\Desktop\scaner project"
pip install -r Backend/requirements.txt -r Backend/requirements-ml.txt

# Offline (bundled samples — good for dev/demo)
python ml/build_dataset.py --use-samples
python ml/train_classifier.py --model random_forest

# Production dataset from OpenFoodFacts
python ml/build_dataset.py --max-pages 20 --page-size 100
python ml/train_classifier.py --model xgboost

# Run the app
python -m Backend.app
```

### `/scan` response fields

| Field | Source |
|-------|--------|
| `health` | Rule engine (always) |
| `ml_prediction.health_tier` | Trained classifier |
| `ml_prediction.flags` | Trained flag classifiers |
| `personalised` | Rule-based advice, or LoRA text when the fine-tuned model is available |
| `lora_advice` | Your fine-tuned LoRA model output |
| `ai_analysis` | OpenRouter personalised LLM (when `OPENROUTER_API_KEY` set) |

---

## Level 2 — Fine-tune a small LLM (LoRA)

**Input:** structured product + profile JSON  
**Output:** personalised shopper advice in Lifeve tone

### Models (base, not from scratch)

- `microsoft/Phi-3-mini-4k-instruct` (default)
- `meta-llama/Llama-3.2-3B-Instruct`
- `mistralai/Mistral-7B-Instruct-v0.3`

### Data

- `(product_facts, profile) → ideal_advice` pairs
- Generated from rule engine + manual edits
- **Minimum:** 500+ high-quality examples; **target:** 5,000+

### Commands

```powershell
pip install -r Backend/requirements-llm.txt

# Offline advice pairs from bundled products
python ml/generate_advice_dataset.py --use-samples

# From OFF barcodes in classifier dataset
python ml/generate_advice_dataset.py --limit-products 500

# Train LoRA (GPU required — Colab Pro, Kaggle, campus cloud)
python ml/train_lora.py --base-model microsoft/Phi-3-mini-4k-instruct --epochs 2
```

Output: `Backend/models/lifeve-advice-lora/`

### How the stack fits together

> Rules bootstrap labels → classifier learns tabular patterns → LoRA adapts advice tone → OpenRouter handles production personalised summaries. Facts stay grounded in nutrition data; models explain, they don't invent.

---

## File map

| Path | Role |
|------|------|
| `Backend/lifeve/health_engine.py` | Rule engine + weak labels |
| `Backend/lifeve/features.py` | Tabular features + tier/flag labels |
| `Backend/lifeve/classifier.py` | Load + inference |
| `ml/build_dataset.py` | Pull OFF → CSV |
| `ml/train_classifier.py` | Train tier + flag models |
| `ml/generate_advice_dataset.py` | Build LoRA JSONL |
| `ml/train_lora.py` | Hugging Face + PEFT LoRA |
| `Backend/lifeve/hf_ner.py` | FDA nutrition NER on ingredients |
| `Backend/lifeve/hf_category.py` | OFF category via Robotoff API |
| `Backend/lifeve/hf_vision.py` | Package photo models (Season 2) |
| `Backend/lifeve/enrichment.py` | Orchestrates HF add-ons before health eval |

---

## Hugging Face add-ons

```env
# Backend/.env
HF_MODELS_ENABLED=1    # NER + category (lightweight vs LoRA)
HF_VISION_ENABLED=1    # package photos only (heavy)
```

| Model | How Lifeve uses it |
|-------|-------------------|
| `sgarbi/bert-fda-nutrition-ner` | Flags additives, colorants, lipids on ingredient text |
| `openfoodfacts/category_classifier` | Robotoff API when categories missing |
| `openfoodfacts/ingredient-detection` | `POST /scan/package-photo` |
| `openfoodfacts/nutrition-extractor` | `POST /scan/package-photo` with `mode=nutrition` |

Install: `pip install -r Backend/requirements-hf.txt`

---

## Environment

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | Personalised LLM in `/scan` |
| `CLASSIFIER_MODEL_PATH` | Override classifier location |
| `HF_MODELS_ENABLED` | Set `1` for ingredient NER + category inference (Robotoff API) |
| `HF_VISION_ENABLED` | Set `1` for package photo ingredient/nutrition extraction |
| `LORA_ADVICE_ENABLED` | Set `1` to run local LoRA at scan time (heavy; off by default) |
| `LORA_ADVICE_DISABLED` | Set `1` to force-skip LoRA even when enabled |
| `FOODREPO_API_KEY` | Backup product lookup |
