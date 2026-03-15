"""
Create Ollama Model Script

Converts a fine-tuned HuggingFace model to Ollama format using GGUF.
Creates a Modelfile and registers the model with Ollama.

Usage:
    python create_ollama_model.py --model ./llama-compliai/merged

Requirements:
    - llama.cpp installed (for GGUF conversion)
    - Ollama installed and running
"""

import os
import subprocess
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_MODEL_NAME = "compliai-llama3.1"


def create_modelfile(model_path: Path, output_path: Path) -> Path:
    """Create an Ollama Modelfile for the fine-tuned model."""
    
    modelfile_content = f'''# CompliAI Fine-tuned Llama 3.1 8B
# Specialized for Indian financial regulatory compliance

FROM {model_path}/gguf/compliai-llama3.1-q4_K_M.gguf

# Model parameters optimized for compliance analysis
PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 8192
PARAMETER repeat_penalty 1.1

# System prompt for compliance tasks
SYSTEM """You are CompliAI, an expert AI assistant specialized in Indian financial regulatory compliance.

Your expertise covers:
- RBI (Reserve Bank of India) regulations and circulars
- FIU-IND (Financial Intelligence Unit) AML/CFT requirements
- NPCI (National Payments Corporation of India) guidelines
- Digital Lending Regulations
- KYC/AML policies and procedures
- Outsourcing and Risk Management guidelines

When analyzing documents:
1. Extract clauses accurately with proper structure
2. Identify compliance gaps precisely
3. Provide actionable remediation suggestions
4. Reference specific regulatory provisions
5. Assign appropriate severity levels

Always be accurate, professional, and cite specific regulations when possible.
If uncertain about something, clearly state your uncertainty."""

# License and metadata
LICENSE "Apache 2.0 (fine-tuned model), Llama 3.1 Community License (base model)"
'''
    
    modelfile_path = output_path / "Modelfile"
    with open(modelfile_path, "w") as f:
        f.write(modelfile_content)
    
    logger.info(f"Created Modelfile at: {modelfile_path}")
    return modelfile_path


def convert_to_gguf(model_path: Path) -> Path:
    """Convert HuggingFace model to GGUF format using llama.cpp."""
    
    gguf_dir = model_path / "gguf"
    gguf_dir.mkdir(exist_ok=True)
    gguf_file = gguf_dir / "compliai-llama3.1-q4_K_M.gguf"
    
    logger.info("Converting to GGUF format...")
    logger.info("This requires llama.cpp to be installed.")
    logger.info("If not installed, run: brew install llama.cpp (macOS) or build from source")
    
    # Check if llama.cpp convert script exists
    convert_script = Path.home() / "llama.cpp" / "convert.py"
    
    if not convert_script.exists():
        # Try common installation paths
        possible_paths = [
            "/opt/homebrew/bin/llama-gguf-convert",
            "/usr/local/bin/llama-gguf-convert",
            Path.home() / "llama.cpp" / "convert-hf-to-gguf.py"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                convert_script = Path(path)
                break
    
    if not convert_script.exists():
        logger.warning(
            "llama.cpp conversion tools not found.\n"
            "Please install llama.cpp and run the conversion manually:\n"
            f"  python llama.cpp/convert-hf-to-gguf.py {model_path} --outfile {gguf_file} --outtype q4_K_M\n"
            "Or use the HuggingFace GGUF converter:\n"
            f"  huggingface-cli gguf-convert {model_path} --out-file {gguf_file}"
        )
        
        # Create a placeholder script for manual conversion
        conversion_script = gguf_dir / "convert.sh"
        with open(conversion_script, "w") as f:
            f.write(f"""#!/bin/bash
# Manual GGUF Conversion Script
# Install llama.cpp first: https://github.com/ggerganov/llama.cpp

# Option 1: Using llama.cpp (recommended)
python ~/llama.cpp/convert-hf-to-gguf.py {model_path} --outfile {gguf_file} --outtype q4_K_M

# Option 2: Using HuggingFace CLI
# pip install huggingface_hub[cli]
# huggingface-cli gguf-convert {model_path} --out-file {gguf_file}
""")
        os.chmod(conversion_script, 0o755)
        logger.info(f"Created conversion script: {conversion_script}")
        
        return gguf_file
    
    # Run conversion
    try:
        subprocess.run([
            "python", str(convert_script),
            str(model_path),
            "--outfile", str(gguf_file),
            "--outtype", "q4_K_M"
        ], check=True)
        logger.info(f"✅ GGUF file created: {gguf_file}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Conversion failed: {e}")
        raise
    
    return gguf_file


def register_with_ollama(modelfile_path: Path):
    """Register the model with Ollama."""
    
    logger.info(f"Registering model '{OLLAMA_MODEL_NAME}' with Ollama...")
    
    try:
        subprocess.run([
            "ollama", "create", OLLAMA_MODEL_NAME,
            "-f", str(modelfile_path)
        ], check=True)
        logger.info(f"✅ Model registered: {OLLAMA_MODEL_NAME}")
    except FileNotFoundError:
        logger.error(
            "Ollama not found. Install Ollama first:\n"
            "  curl -fsSL https://ollama.com/install.sh | sh\n"
            "Then run:\n"
            f"  ollama create {OLLAMA_MODEL_NAME} -f {modelfile_path}"
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to register model: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Create Ollama model from fine-tuned HuggingFace model")
    parser.add_argument(
        "--model", "-m",
        type=str,
        required=True,
        help="Path to the merged HuggingFace model"
    )
    parser.add_argument(
        "--skip-convert",
        action="store_true",
        help="Skip GGUF conversion (if already done)"
    )
    parser.add_argument(
        "--skip-register",
        action="store_true",
        help="Skip Ollama registration"
    )
    
    args = parser.parse_args()
    model_path = Path(args.model)
    
    logger.info("=" * 50)
    logger.info("Creating Ollama Model")
    logger.info("=" * 50)
    logger.info(f"Source model: {model_path}")
    logger.info(f"Ollama model name: {OLLAMA_MODEL_NAME}")
    
    # Convert to GGUF
    if not args.skip_convert:
        logger.info("\n📦 Converting to GGUF format...")
        gguf_file = convert_to_gguf(model_path)
    else:
        gguf_file = model_path / "gguf" / "compliai-llama3.1-q4_K_M.gguf"
    
    # Create Modelfile
    logger.info("\n📝 Creating Modelfile...")
    modelfile_path = create_modelfile(model_path, model_path)
    
    # Register with Ollama
    if not args.skip_register:
        logger.info("\n🚀 Registering with Ollama...")
        register_with_ollama(modelfile_path)
    
    logger.info("\n" + "=" * 50)
    logger.info("✅ Setup Complete!")
    logger.info("=" * 50)
    logger.info(f"\nTo use your fine-tuned model:")
    logger.info(f"  1. Set USE_LOCAL_LLM=true in your .env")
    logger.info(f"  2. Set OLLAMA_MODEL={OLLAMA_MODEL_NAME}")
    logger.info(f"  3. Start Ollama: ollama serve")
    logger.info(f"  4. Test: ollama run {OLLAMA_MODEL_NAME} 'Hello!'")


if __name__ == "__main__":
    main()
