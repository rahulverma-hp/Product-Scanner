# Lifeve

**Scan · Evaluate · Personalise** — a barcode health scanner that turns grocery packaging into clear, profile-aware nutrition advice.

Point your camera at a barcode, pull product data from Open Food Facts, and get structured health insights tailored to who you are — not a generic label on the back of the box.

## Live demo

| | URL |
|---|---|
| **App** | https://rahulverma-hp.github.io/Product-Scanner/ |
| **API** | https://product-scanner-3gh1.onrender.com |

Try barcodes: **3017620422003** (Nutella), **5000159484695** (Weetabix), **87104022** (yogurt).

> Runs on free hosting — the first request after idle can take 30–60 seconds while the server wakes up.

## How it works

```text
Barcode or package photo
  → Open Food Facts (+ FoodRepo / local fallbacks)
  → Smart ingredient reading (optional HF NER)
  → Rule engine (deterministic health JSON)
  → Trained classifier (healthy · moderate · avoid)
  → OpenRouter personalised AI analysis
  → React UI
```

Rules establish the facts. A classifier learns patterns from those labels. NER enriches ingredient text. An LLM explains the result for the shopper's profile.

## Local development

### Backend (port 5000)

```powershell
cd "path\to\scaner project"
pip install -r Backend/requirements.txt
pip install -r Backend/requirements-ml.txt    # classifier
pip install -r Backend/requirements-hf.txt    # optional NER + vision

copy Backend\.env.example Backend\.env
# Set OPENROUTER_API_KEY, HF_MODELS_ENABLED=1, etc.

python ml/build_dataset.py --use-samples
python ml/train_classifier.py

python -m Backend.app
```

### Frontend (port 5173)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies API calls to Flask.

## Features

- **ZXing** barcode scanner in the browser
- **Account profiles** — register, login, personalised sugar guidance
- **Rule engine** — ingredient keywords, nutrient thresholds, pros/cons
- **Trained classifier** — `healthy | moderate | avoid` + nutrient flags
- **OpenRouter AI** — structured personalised analysis JSON
- **Smart ingredient reading** — FDA nutrition NER (`HF_MODELS_ENABLED=1`)
- **Package photo** — read ingredients from a label photo (`HF_VISION_ENABLED=1`)

## Environment variables

See `Backend/.env.example` and `ML_README.md` for the full list.

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | Personalised AI analysis |
| `HF_MODELS_ENABLED=1` | Ingredient NER + category inference |
| `HF_VISION_ENABLED=1` | Package photo ingredient reading |
| `LORA_ADVICE_ENABLED=1` | Optional local LoRA (heavy, off by default) |

## Repo map

| Path | What |
|------|------|
| `Backend/server/routes.py` | `/scan`, `/scan/package-photo`, auth |
| `Backend/lifeve/health_engine.py` | Rule-based health evaluation |
| `Backend/lifeve/classifier.py` | ML inference |
| `frontend/src/pages/ScannerPage.tsx` | Scanner UI |
| `ml/` | Dataset build + classifier + LoRA training |
| `ML_README.md` | ML training deep-dive |

## Health check

```powershell
python scripts/healthcheck.py
```
