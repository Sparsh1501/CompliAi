# CompliAI Local LLM Fine-tuning

This directory contains scripts for fine-tuning Llama 3.1 8B on CompliAI's compliance data
to create a local, cost-free alternative to Claude Sonnet.

## Overview

The fine-tuning uses **QLoRA** (Quantized LoRA) for memory-efficient training on consumer hardware.

### Resource Requirements

| Phase | RAM | GPU VRAM | Time |
|-------|-----|----------|------|
| Export Data | 4GB | - | ~5 min |
| Fine-tune (CPU) | 8GB+ | - | 4-8 hours |
| Fine-tune (GPU) | 8GB | 8GB+ | 30-60 min |
| Inference | 4GB | - | 5-30s/response |

## Quick Start

### 1. Export Training Data

```bash
# From the backend directory
cd /path/to/compliAi/backend

# Export all training data types
python scripts/export_training_data.py --output ./training_data

# Or export specific types
python scripts/export_training_data.py --output ./training_data --types clauses gaps chat
```

### 2. Install Fine-tuning Dependencies

```bash
pip install -r finetune/requirements-finetune.txt
```

### 3. Get HuggingFace Access

1. Create account at https://huggingface.co
2. Accept Llama 3.1 license at https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
3. Create access token at https://huggingface.co/settings/tokens
4. Set token: `export HF_TOKEN=your_token_here`

### 4. Run Fine-tuning

**On Local Machine (8GB RAM):**
```bash
python finetune/finetune_lora.py \
    --data ./training_data \
    --output ./llama-compliai \
    --epochs 3 \
    --batch-size 1
```

**On Google Colab (Free GPU):**
```bash
python finetune/finetune_lora.py \
    --data ./training_data \
    --output ./llama-compliai \
    --epochs 3 \
    --use-colab
```

### 5. Merge Adapter

```bash
python finetune/merge_adapter.py \
    --adapter ./llama-compliai/adapter \
    --output ./llama-compliai/merged
```

### 6. Create Ollama Model

```bash
# Install Ollama first
curl -fsSL https://ollama.com/install.sh | sh

# Create and register model
python finetune/create_ollama_model.py --model ./llama-compliai/merged
```

### 7. Use in CompliAI

```bash
# Set environment variables
export USE_LOCAL_LLM=true
export OLLAMA_MODEL=compliai-qwen2.5

# Start Ollama server
ollama serve

# Start CompliAI backend
cd backend && python server.py
```

## Using Base Model (Without Fine-tuning)

If you want to use Qwen 2.5 32B without fine-tuning:

```bash
# Pull the base model
ollama pull qwen2.5:32b-instruct-q4_K_M

# Set environment
export USE_LOCAL_LLM=true
export OLLAMA_MODEL=qwen2.5:32b-instruct-q4_K_M
```

## File Structure

```
finetune/
├── requirements-finetune.txt  # Training dependencies
├── finetune_lora.py          # Main QLoRA training script
├── merge_adapter.py          # Merge LoRA adapter into base model
├── create_ollama_model.py    # Convert to GGUF + register with Ollama
└── README.md                 # This file

scripts/
└── export_training_data.py   # Export Claude-generated data for training
```

## Training Data Format

The export script creates JSONL files with this structure:

```json
{
  "messages": [
    {"role": "system", "content": "System prompt..."},
    {"role": "user", "content": "User input..."},
    {"role": "assistant", "content": "Model response..."}
  ]
}
```

## Tips for Better Results

1. **More data = better quality**: Upload more policies/regulations before exporting
2. **Review exports**: Check the JSONL files for quality issues before training
3. **Adjust epochs**: More epochs if underfitting, fewer if overfitting
4. **Use GPU if possible**: Google Colab T4 is free and 10x faster than CPU
