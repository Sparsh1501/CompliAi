"""
Training Data Export Script for CompliAI Local LLM Fine-tuning

This script exports Claude-generated data from MongoDB for fine-tuning a local LLM.
It creates JSONL files suitable for LoRA/QLoRA fine-tuning.

Usage:
    python scripts/export_training_data.py --output ./training_data

Output Files:
    - clause_extraction_train.jsonl    (document -> clauses pairs)
    - gap_analysis_train.jsonl         (policy+regulation clauses -> gaps)
    - chat_train.jsonl                 (user messages -> AI responses)
    - task_generation_train.jsonl      (gaps -> tasks)
"""

import os
import sys
import json
import argparse
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "compliance_db")


async def get_db():
    """Get MongoDB database connection."""
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def format_for_training(
    system_prompt: str,
    user_input: str,
    assistant_output: str
) -> Dict[str, Any]:
    """
    Format a single training example in the Llama instruction format.
    
    Returns a dict compatible with most fine-tuning frameworks.
    """
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_output}
        ]
    }


async def export_clause_extraction_data(db, output_dir: Path) -> int:
    """
    Export clause extraction training data from policies and regulations.
    
    Extracts pairs of (document_text, extracted_clauses) from the database.
    """
    output_file = output_dir / "clause_extraction_train.jsonl"
    count = 0
    
    system_prompt = """You are a regulatory compliance expert specialized in extracting clauses from policy and regulation documents.

Given a document text, extract all distinct clauses with the following structure for each clause:
- clause_id: A unique identifier (e.g., CL-001)
- clause_text: The full text of the clause
- clause_type: The type (e.g., requirement, prohibition, definition, procedure)
- key_requirements: List of specific requirements from this clause
- entities: Any entities mentioned (organizations, roles, etc.)

Respond with a valid JSON array of clause objects."""

    # Export from policies
    policies_collection = db["policies"]
    async for policy in policies_collection.find({"clauses": {"$exists": True, "$ne": []}}):
        if policy.get("original_text") and policy.get("clauses"):
            user_input = f"Extract clauses from the following policy document:\n\n{policy['original_text'][:8000]}"
            assistant_output = json.dumps(policy["clauses"], indent=2)
            
            example = format_for_training(system_prompt, user_input, assistant_output)
            
            with open(output_file, "a") as f:
                f.write(json.dumps(example) + "\n")
            count += 1
    
    # Export from regulations
    regulations_collection = db["regulations"]
    async for regulation in regulations_collection.find({"clauses": {"$exists": True, "$ne": []}}):
        if regulation.get("original_text") and regulation.get("clauses"):
            user_input = f"Extract clauses from the following regulation document:\n\n{regulation['original_text'][:8000]}"
            assistant_output = json.dumps(regulation["clauses"], indent=2)
            
            example = format_for_training(system_prompt, user_input, assistant_output)
            
            with open(output_file, "a") as f:
                f.write(json.dumps(example) + "\n")
            count += 1
    
    print(f"✅ Exported {count} clause extraction examples to {output_file}")
    return count


async def export_gap_analysis_data(db, output_dir: Path) -> int:
    """
    Export gap analysis training data.
    
    Extracts (policy_clauses, regulation_clauses, gap_results) from the database.
    """
    output_file = output_dir / "gap_analysis_train.jsonl"
    count = 0
    
    system_prompt = """You are a regulatory compliance expert specialized in gap analysis.

Given policy clauses and regulatory requirement clauses, analyze compliance gaps with the following structure:
- compliance_status: "compliant", "partial", "non_compliant", "missing"
- severity: "critical", "high", "medium", "low"
- gap_description: Description of the gap if not fully compliant
- remediation_suggestion: Suggested fix for the gap
- regulatory_reference: Reference to the specific regulation clause
- confidence_score: Score from 0.0 to 1.0 indicating confidence

Respond with a valid JSON object containing the analysis."""

    gap_analyses_collection = db["gap_analyses"]
    async for gap in gap_analyses_collection.find({"gaps": {"$exists": True, "$ne": []}}):
        if gap.get("policy_clauses") and gap.get("regulation_clauses") and gap.get("gaps"):
            user_input = f"""Analyze compliance gaps between the following:

POLICY CLAUSES:
{json.dumps(gap['policy_clauses'][:10], indent=2)}

REGULATORY REQUIREMENT CLAUSES:
{json.dumps(gap['regulation_clauses'][:10], indent=2)}

Identify all compliance gaps."""

            assistant_output = json.dumps({
                "compliance_score": gap.get("compliance_score", 0),
                "gaps": gap["gaps"][:20],  # Limit for token efficiency
                "summary": gap.get("summary", "")
            }, indent=2)
            
            example = format_for_training(system_prompt, user_input, assistant_output)
            
            with open(output_file, "a") as f:
                f.write(json.dumps(example) + "\n")
            count += 1
    
    print(f"✅ Exported {count} gap analysis examples to {output_file}")
    return count


async def export_chat_data(db, output_dir: Path) -> int:
    """
    Export chat/assistant training data.
    
    Extracts (user_message, ai_response) pairs from chat history.
    """
    output_file = output_dir / "chat_train.jsonl"
    count = 0
    
    system_prompt = """You are CompliAI, an AI assistant specialized in Indian financial regulatory compliance.

You help users understand:
- RBI (Reserve Bank of India) regulations
- FIU-IND (Financial Intelligence Unit) requirements
- NPCI (National Payments Corporation of India) guidelines
- Digital Lending compliance
- KYC/AML policies

You provide accurate, helpful, and professional responses about compliance matters.
When uncertain, clearly indicate this and suggest consulting with a compliance officer."""

    chat_collection = db["chat_messages"]
    async for chat in chat_collection.find({"role": "assistant", "content": {"$exists": True}}):
        # Find the corresponding user message
        user_msg = await chat_collection.find_one({
            "session_id": chat.get("session_id"),
            "role": "user",
            "created_at": {"$lt": chat.get("created_at")}
        }, sort=[("created_at", -1)])
        
        if user_msg and user_msg.get("content") and chat.get("content"):
            example = format_for_training(
                system_prompt,
                user_msg["content"],
                chat["content"]
            )
            
            with open(output_file, "a") as f:
                f.write(json.dumps(example) + "\n")
            count += 1
    
    print(f"✅ Exported {count} chat examples to {output_file}")
    return count


async def export_task_generation_data(db, output_dir: Path) -> int:
    """
    Export task generation training data.
    
    Extracts (gap_description, generated_task) pairs.
    """
    output_file = output_dir / "task_generation_train.jsonl"
    count = 0
    
    system_prompt = """You are a compliance task manager AI.

Given a compliance gap description, generate a remediation task with:
- title: Clear, actionable task title
- description: Detailed description of what needs to be done
- priority: "critical", "high", "medium", or "low"
- estimated_hours: Estimated time to complete
- required_evidence: List of evidence needed to verify completion
- assignee_role: Recommended role for assignment (e.g., "Compliance Officer", "Legal Team")

Respond with a valid JSON object."""

    tasks_collection = db["tasks"]
    gap_analyses_collection = db["gap_analyses"]
    
    async for task in tasks_collection.find({
        "source": "gap_analysis",
        "gap_id": {"$exists": True}
    }):
        # Try to find the related gap
        gap = await gap_analyses_collection.find_one({"_id": task.get("gap_analysis_id")})
        
        if gap and task.get("title") and task.get("description"):
            gap_description = f"""Gap Analysis Result:
- Gap ID: {task.get('gap_id')}
- Severity: {task.get('priority', 'medium')}
- Related Policy: {gap.get('policy_title', 'Unknown')}
- Related Regulation: {gap.get('regulation_title', 'Unknown')}"""

            task_output = {
                "title": task["title"],
                "description": task["description"],
                "priority": task.get("priority", "medium"),
                "estimated_hours": task.get("estimated_hours"),
                "required_evidence": task.get("required_evidence", []),
                "assignee_role": task.get("assigned_role", "Compliance Officer")
            }
            
            example = format_for_training(
                system_prompt,
                f"Generate a remediation task for the following gap:\n\n{gap_description}",
                json.dumps(task_output, indent=2)
            )
            
            with open(output_file, "a") as f:
                f.write(json.dumps(example) + "\n")
            count += 1
    
    print(f"✅ Exported {count} task generation examples to {output_file}")
    return count


async def main():
    parser = argparse.ArgumentParser(description="Export training data for local LLM fine-tuning")
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./training_data",
        help="Output directory for training data files"
    )
    parser.add_argument(
        "--types", "-t",
        type=str,
        nargs="+",
        default=["all"],
        choices=["all", "clauses", "gaps", "chat", "tasks"],
        help="Types of data to export"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📦 Exporting training data to: {output_dir}")
    print(f"📅 Export started at: {datetime.now().isoformat()}")
    print("-" * 50)
    
    # Connect to database
    db = await get_db()
    
    total = 0
    export_all = "all" in args.types
    
    if export_all or "clauses" in args.types:
        total += await export_clause_extraction_data(db, output_dir)
    
    if export_all or "gaps" in args.types:
        total += await export_gap_analysis_data(db, output_dir)
    
    if export_all or "chat" in args.types:
        total += await export_chat_data(db, output_dir)
    
    if export_all or "tasks" in args.types:
        total += await export_task_generation_data(db, output_dir)
    
    print("-" * 50)
    print(f"✅ Total examples exported: {total}")
    print(f"📂 Output directory: {output_dir.absolute()}")
    print(f"\n🚀 Next steps:")
    print(f"   1. Review the exported JSONL files")
    print(f"   2. Run fine-tuning: python finetune/finetune_lora.py --data {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
