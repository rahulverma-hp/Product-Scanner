#!/usr/bin/env python3
"""Level 2: LoRA fine-tune a small instruct model on Lifeve advice pairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT_TEMPLATE = """### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}"""


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def format_example(record: dict) -> dict:
    return {
        "text": PROMPT_TEMPLATE.format(
            instruction=record["instruction"],
            input=record["input"],
            output=record["output"],
        )
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="Backend/data/lifeve_advice_train.jsonl")
    parser.add_argument("--base-model", default="microsoft/Phi-3-mini-4k-instruct")
    parser.add_argument("--output-dir", default="Backend/models/lifeve-advice-lora")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-seq-length", type=int, default=1024)
    args = parser.parse_args()

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model
        from transformers import (
            AutoConfig,
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit("Install: pip install -r Backend/requirements-llm.txt") from exc

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"Missing {dataset_path}. Run ml/generate_advice_dataset.py first.")

    records = load_jsonl(dataset_path)
    if len(records) < 10:
        raise SystemExit("Need more advice examples in the dataset.")

    formatted = [format_example(record) for record in records]
    split_idx = max(1, int(len(formatted) * 0.9))
    train_dataset = Dataset.from_list(formatted[:split_idx])
    eval_dataset = Dataset.from_list(formatted[split_idx:] or formatted[-3:])

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    config = AutoConfig.from_pretrained(args.base_model, trust_remote_code=True)
    # Phi-3 4k checkpoints ship a partial rope_scaling dict that breaks newer transformers.
    if "phi-3" in args.base_model.lower():
        config.rope_scaling = None

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        config=config,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
        trust_remote_code=True,
    )
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        ),
    )

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=args.max_seq_length,
            padding="max_length",
        )

    train_tokenized = train_dataset.map(tokenize, batched=True, remove_columns=["text"])
    eval_tokenized = eval_dataset.map(tokenize, batched=True, remove_columns=["text"])
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            logging_steps=10,
            eval_strategy="epoch",
            save_strategy="epoch",
            fp16=torch.cuda.is_available(),
            report_to=[],
        ),
        train_dataset=train_tokenized,
        eval_dataset=eval_tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    metadata = {
        "base_model": args.base_model,
        "train_rows": len(train_tokenized),
        "eval_rows": len(eval_tokenized),
        "output_dir": str(output_dir),
    }
    (output_dir / "training_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
