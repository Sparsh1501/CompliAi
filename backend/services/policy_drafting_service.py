"""
Gen-AI Policy Drafting Service for CompliAI

Uses Claude to generate policy drafts based on:
- Gap analysis results (what's missing)
- Regulation requirements (what's needed)
- Organization profile (entity type, context)
- Existing policies (for consistency)

Task #11: Build gen-AI policy drafting engine
"""

import anthropic
import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PolicyDraftingService:
    """Generates policy drafts using Claude AI."""

    def __init__(self, db=None):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
        self.model = "claude-sonnet-4-20250514"
        self.db = db

    async def generate_policy_draft(
        self,
        title: str,
        policy_type: str,
        requirements: List[Dict[str, Any]] = None,
        gaps: List[Dict[str, Any]] = None,
        entity_type: str = "non_bank_pa",
        organization: str = "",
        user_id: str = "",
        instructions: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a policy document draft using AI.

        Args:
            title: Policy title
            policy_type: Type (KYC, AML, InfoSec, etc.)
            requirements: Specific regulatory requirements to address
            gaps: Gap analysis results to remediate
            entity_type: Organization's entity type
            instructions: Additional user instructions

        Returns:
            Dict with generated policy content, sections, and metadata
        """
        if not self.client:
            return {"error": "AI service not configured"}

        # Build context
        requirements_text = ""
        if requirements:
            for r in requirements[:15]:
                requirements_text += f"\n- {r.get('title', '')}: {r.get('description', '')[:200]}"
                indicators = r.get('compliance_indicators', [])
                if indicators:
                    requirements_text += f"\n  Indicators: {', '.join(indicators[:4])}"

        gaps_text = ""
        if gaps:
            for g in gaps[:10]:
                gaps_text += f"\n- [{g.get('severity', 'Medium')}] {g.get('description', '')[:200]}"
                missing = g.get('metadata', {}).get('missing_elements', [])
                if missing:
                    gaps_text += f"\n  Missing: {', '.join(missing[:3])}"

        entity_labels = {
            "bank_pa": "Bank Payment Aggregator",
            "non_bank_pa": "Non-bank Payment Aggregator",
            "pa_p": "PA-P (Physical POS Aggregator)",
            "pg_only": "Payment Gateway",
            "nbfc": "NBFC",
        }
        entity_label = entity_labels.get(entity_type, entity_type)

        prompt = f"""You are a compliance policy writer for an Indian {entity_label}. Generate a comprehensive policy document.

POLICY TITLE: {title}
POLICY TYPE: {policy_type}
ORGANIZATION TYPE: {entity_label}

{f"REGULATORY REQUIREMENTS TO ADDRESS:{requirements_text}" if requirements_text else ""}

{f"COMPLIANCE GAPS TO REMEDIATE:{gaps_text}" if gaps_text else ""}

{f"ADDITIONAL INSTRUCTIONS: {instructions}" if instructions else ""}

Generate a complete policy document with:
1. Policy Statement / Objective
2. Scope and Applicability
3. Definitions
4. Policy Details (organized into clear sections)
5. Roles and Responsibilities
6. Compliance Monitoring
7. Reporting Requirements
8. Review and Update Frequency
9. Regulatory References

Return JSON:
{{
  "title": "{title}",
  "sections": [
    {{"heading": "...", "content": "...", "sub_sections": []}},
  ],
  "summary": "One-paragraph summary",
  "regulatory_references": ["RBI Master Direction Para X", ...],
  "review_frequency": "annual|quarterly",
  "effective_date_recommendation": "...",
  "key_stakeholders": ["CCO", "Board", ...]
}}

Write in formal Indian regulatory compliance language. Be specific and actionable.
Return ONLY valid JSON."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            draft = json.loads(text)
            draft_id = str(uuid.uuid4())

            # Store the draft
            draft_doc = {
                "id": draft_id,
                "title": title,
                "policy_type": policy_type,
                "entity_type": entity_type,
                "status": "draft",
                "content": draft,
                "user_id": user_id,
                "organization": organization,
                "instructions": instructions,
                "based_on_gaps": [g.get("id") for g in (gaps or [])][:10],
                "based_on_requirements": [r.get("requirement_id") for r in (requirements or [])][:15],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.db.policy_drafts.insert_one(draft_doc)

            return {
                "draft_id": draft_id,
                "title": title,
                "content": draft,
                "status": "draft",
            }

        except Exception as e:
            logger.error(f"Policy draft generation failed: {e}")
            return {"error": str(e)}

    async def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Get a policy draft by ID."""
        return await self.db.policy_drafts.find_one({"id": draft_id}, {"_id": 0})

    async def list_drafts(self, user_id: str, organization: str) -> List[Dict[str, Any]]:
        """List policy drafts for a user/organization."""
        cursor = self.db.policy_drafts.find(
            {"organization": organization},
            {"_id": 0, "content": 0}
        ).sort("created_at", -1).limit(50)
        return await cursor.to_list(length=50)

    async def update_draft_status(self, draft_id: str, status: str, reviewer_id: str = None) -> Dict[str, Any]:
        """Update draft status (draft → review → approved → published)."""
        update = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if reviewer_id:
            update["reviewer_id"] = reviewer_id
            update["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        await self.db.policy_drafts.update_one({"id": draft_id}, {"$set": update})
        return await self.get_draft(draft_id)

    async def generate_sop_from_requirement(
        self,
        requirement_id: str,
        regulation_id: str,
        user_id: str,
        organization: str
    ) -> Dict[str, Any]:
        """
        Generate a Standard Operating Procedure from a specific requirement.
        (Task #12: PA SOP Templates Library)
        """
        req = await self.db.requirements.find_one(
            {"requirement_id": requirement_id, "regulation_id": regulation_id},
            {"_id": 0}
        )
        if not req:
            return {"error": "Requirement not found"}

        return await self.generate_policy_draft(
            title=f"SOP: {req.get('title', 'Untitled')}",
            policy_type="SOP",
            requirements=[req],
            entity_type="non_bank_pa",
            organization=organization,
            user_id=user_id,
            instructions=f"Generate a detailed Standard Operating Procedure (SOP) for: {req.get('description', '')}. Include step-by-step procedures, responsible parties, and verification checklist."
        )
