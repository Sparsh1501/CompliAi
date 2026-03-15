"""
LoRA Fine-tuning Script for CompliAI Local LLM

This script fine-tunes Llama 3.1 8B using QLoRA (Quantized LoRA) for memory-efficient
training on consumer hardware (8GB RAM/VRAM).

Usage:
    python finetune_lora.py --data ./training_data --output ./llama-compliai

For Google Colab (free GPU), upload this script and training data, then run:
    !python finetune_lora.py --data ./training_data --output ./llama-compliai --use-colab
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Optional

import torch
from datasets import load_dataset, Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    pipeline
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    PeftModel
)
from trl import SFTTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configuration
BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
OLLAMA_MODEL_NAME = "llama3.1:8b-instruct-q4_K_M"


def setup_quantization_config():
    """Configure 4-bit quantization for memory-efficient training."""
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )


def setup_lora_config():
    """Configure LoRA for parameter-efficient fine-tuning."""
    return LoraConfig(
        r=16,  # LoRA rank
        lora_alpha=32,  # LoRA scaling factor
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",  # Attention
            "gate_proj", "up_proj", "down_proj"  # MLP
        ]
    )


def load_training_data(data_dir: Path) -> Dataset:
    """
    Load training data from JSONL files exported by export_training_data.py.
    
    Combines all training examples into a single dataset.
    """
    all_examples = []
    
    # Load all JSONL files
    for jsonl_file in data_dir.glob("*.jsonl"):
        logger.info(f"Loading: {jsonl_file}")
        with open(jsonl_file, "r") as f:
            for line in f:
                if line.strip():
                    example = json.loads(line)
                    all_examples.append(example)
    
    if not all_examples:
        raise ValueError(f"No training data found in {data_dir}")
    
    logger.info(f"Loaded {len(all_examples)} training examples")
    
    # Convert to HuggingFace Dataset
    return Dataset.from_list(all_examples)


def format_for_llama(example: dict, tokenizer) -> str:
    """
    Format a training example for Llama 3.1 instruction format.
    
    Llama 3.1 uses this format:
    <|begin_of_text|><|start_header_id|>system<|end_header_id|>
    {system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>
    {user_message}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
    {assistant_message}<|eot_id|>
    """
    messages = example.get("messages", [])
    
    if not messages:
        return ""
    
    # Use tokenizer's built-in chat template
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False
    )


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Llama 3.1 8B with LoRA")
    parser.add_argument(
        "--data", "-d",
        type=str,
        required=True,
        help="Directory containing training data JSONL files"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./llama-compliai",
        help="Output directory for fine-tuned model"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Training batch size (keep at 1 for 8GB RAM)"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=2e-4,
        help="Learning rate"
    )
    parser.add_argument(
        "--use-colab",
        action="store_true",
        help="Optimize settings for Google Colab free tier"
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=None,
        help="HuggingFace token for accessing Llama (or set HF_TOKEN env var)"
    )
    
    args = parser.parse_args()
    
    # Get HuggingFace token
    hf_token = args.hf_token or os.getenv("HF_TOKEN")
    if not hf_token:
        logger.warning(
            "No HuggingFace token provided. You may need to accept Llama license "
            "at https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct"
        )
    
    data_dir = Path(args.data)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 50)
    logger.info("CompliAI Local LLM Fine-tuning")
    logger.info("=" * 50)
    logger.info(f"Base model: {BASE_MODEL}")
    logger.info(f"Training data: {data_dir}")
    logger.info(f"Output: {output_dir}")
    
    # Load training data
    logger.info("\n📦 Loading training data...")
    dataset = load_training_data(data_dir)
    
    # Load tokenizer
    logger.info("\n🔧 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL,
        token=hf_token,
        trust_remote_code=True
    )
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    # Format dataset
    logger.info("\n📝 Formatting dataset for Llama 3.1...")
    dataset = dataset.map(
        lambda x: {"text": format_for_llama(x, tokenizer)},
        remove_columns=dataset.column_names
    )
    
    # Filter empty examples
    dataset = dataset.filter(lambda x: len(x["text"]) > 0)
    logger.info(f"Formatted dataset: {len(dataset)} examples")
    
    # Load model with quantization
    logger.info("\n🤖 Loading model with 4-bit quantization...")
    bnb_config = setup_quantization_config()
    
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        token=hf_token,
        trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model)
    
    # Apply LoRA
    logger.info("\n🔌 Applying LoRA configuration...")
    lora_config = setup_lora_config()
    model = get_peft_model(model, lora_config)
    
    # Print trainable parameters
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Trainable params: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)")
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=8 if args.use_colab else 4,
        warmup_steps=10,
        learning_rate=args.lr,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
        evaluation_strategy="no",
        save_total_limit=2,
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        max_grad_norm=0.3,
        report_to="none"  # Disable wandb by default
    )
    
    # Create trainer
    logger.info("\n🏋️ Starting training...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        tokenizer=tokenizer,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=2048,
        packing=True,  # Pack multiple examples into one sequence
    )
    
    # Train
    trainer.train()
    
    # Save the fine-tuned adapter
    logger.info("\n💾 Saving fine-tuned adapter...")
    trainer.save_model(str(output_dir / "adapter"))
    tokenizer.save_pretrained(str(output_dir / "adapter"))
    
    logger.info("\n✅ Training complete!")
    logger.info(f"Adapter saved to: {output_dir / 'adapter'}")
    logger.info("\n🚀 Next steps:")
    logger.info("   1. Merge adapter: python merge_adapter.py --adapter ./llama-compliai/adapter")
    logger.info("   2. Convert to Ollama: python create_ollama_model.py --model ./llama-compliai/merged")


if __name__ == "__main__":
    main()
