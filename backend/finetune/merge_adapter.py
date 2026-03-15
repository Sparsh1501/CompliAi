"""
Merge LoRA Adapter Script

Merges the fine-tuned LoRA adapter weights back into the base model
to create a standalone model that can be converted to GGUF format for Ollama.

Usage:
    python merge_adapter.py --adapter ./llama-compliai/adapter --output ./llama-compliai/merged
"""

import os
import argparse
import logging
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


def main():
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into base model")
    parser.add_argument(
        "--adapter", "-a",
        type=str,
        required=True,
        help="Path to the fine-tuned LoRA adapter"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output directory for merged model"
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=None,
        help="HuggingFace token (or set HF_TOKEN env var)"
    )
    
    args = parser.parse_args()
    
    hf_token = args.hf_token or os.getenv("HF_TOKEN")
    adapter_path = Path(args.adapter)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 50)
    logger.info("Merging LoRA Adapter")
    logger.info("=" * 50)
    logger.info(f"Base model: {BASE_MODEL}")
    logger.info(f"Adapter: {adapter_path}")
    logger.info(f"Output: {output_path}")
    
    # Load base model
    logger.info("\n🤖 Loading base model...")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        token=hf_token,
        trust_remote_code=True
    )
    
    # Load tokenizer
    logger.info("🔧 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        str(adapter_path),
        token=hf_token,
        trust_remote_code=True
    )
    
    # Load and merge adapter
    logger.info("🔌 Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    
    logger.info("🔀 Merging adapter into base model...")
    model = model.merge_and_unload()
    
    # Save merged model
    logger.info(f"💾 Saving merged model to {output_path}...")
    model.save_pretrained(str(output_path))
    tokenizer.save_pretrained(str(output_path))
    
    logger.info("\n✅ Merge complete!")
    logger.info(f"Merged model saved to: {output_path}")
    logger.info("\n🚀 Next step:")
    logger.info(f"   python create_ollama_model.py --model {output_path}")


if __name__ == "__main__":
    main()
