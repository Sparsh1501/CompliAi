from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
from typing import List, Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)

class LLMService:
    """
    LLM Service using Claude Sonnet 4 for all text-based AI operations.
    Uses the emergentintegrations library for unified LLM access.
    """
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            logger.warning("No API key found. Set EMERGENT_LLM_KEY environment variable")
        
    async def extract_clauses_with_llm(self, text: str, document_type: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.error("LLM service not initialized - no API key")
            return []
            
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"clause_extraction_{document_type}",
                system_message="You are an expert in regulatory compliance and legal document analysis for Indian financial institutions."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Extract key clauses from this {document_type} document. 
            For each clause, identify:
            - The main requirement or statement
            - Section heading if available
            - Key compliance points
            
            Return a JSON array with objects containing: text, section, importance (high/medium/low)
            
            Document text (first 3000 chars):
            {text[:3000]}
            
            Return only valid JSON array."""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            
            try:
                clauses_data = json.loads(response)
                return clauses_data if isinstance(clauses_data, list) else []
            except json.JSONDecodeError:
                logger.warning("LLM response not valid JSON, returning empty list")
                return []
        except Exception as e:
            logger.error(f"Error in LLM clause extraction: {str(e)}")
            return []
    
    async def analyze_gap(self, policy_clause: str, regulation_clause: str) -> Dict[str, Any]:
        if not self.api_key:
            logger.error("LLM service not initialized - no API key")
            return {
                "gap_type": "error",
                "severity": "Low",
                "confidence_score": 0.0,
                "description": "LLM service not configured - missing EMERGENT_LLM_KEY",
                "suggested_fix": "Configure EMERGENT_LLM_KEY environment variable"
            }
            
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="gap_analysis",
                system_message="You are an expert compliance auditor specializing in regulatory gap analysis for Indian financial institutions (NBFCs, banks)."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Analyze the compliance gap between this policy clause and regulation requirement.
            
            Policy Clause:
            {policy_clause}
            
            Regulation Requirement:
            {regulation_clause}
            
            Provide analysis as JSON with:
            - gap_type: (missing, weak, conflicting, compliant)
            - severity: (Critical, High, Medium, Low)
            - confidence_score: (0.0 to 1.0)
            - description: Brief explanation
            - suggested_fix: Recommended action
            
            Return only valid JSON object."""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            
            try:
                gap_data = json.loads(response)
                return gap_data
            except json.JSONDecodeError:
                logger.warning("LLM gap analysis response not valid JSON")
                return {
                    "gap_type": "unknown",
                    "severity": "Medium",
                    "confidence_score": 0.5,
                    "description": "Unable to parse gap analysis",
                    "suggested_fix": "Manual review required"
                }
        except Exception as e:
            logger.error(f"Error in gap analysis: {str(e)}")
            return {
                "gap_type": "error",
                "severity": "Low",
                "confidence_score": 0.0,
                "description": f"Analysis error: {str(e)}",
                "suggested_fix": "Retry analysis"
            }
    
    async def generate_embeddings(self, text: str) -> List[float]:
        dummy_embedding = [0.1] * 384
        return dummy_embedding
