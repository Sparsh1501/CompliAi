"""
Remediation Service for CompliAI

Generates prioritized remediation lists from gap analysis results:
- Priority ranking by severity × criticality
- RBI paragraph citations for each gap
- Suggested remediation actions with timelines
- Task auto-generation for remediation items
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Priority scoring: severity × criticality multiplier
SEVERITY_SCORES = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
CRITICALITY_MULTIPLIERS = {"high": 3, "medium": 2, "low": 1}

# Default remediation timelines by severity
REMEDIATION_TIMELINES = {
    "Critical": "Immediate (within 7 days)",
    "High": "Within 30 days",
    "Medium": "Within 90 days",
    "Low": "Within 180 days",
}


class RemediationService:
    """Generates prioritized remediation lists from gap analysis."""

    def __init__(self, db=None):
        self.db = db

    async def generate_remediation_list(
        self,
        analysis_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Generate a prioritized remediation list from a gap analysis.

        Returns items sorted by priority score (highest first),
        with RBI citations and suggested actions.
        """
        analysis = await self.db.gap_analyses.find_one({"id": analysis_id}, {"_id": 0})
        if not analysis:
            return {"error": "Analysis not found"}

        gaps = analysis.get("gaps", [])
        non_compliant = [
            g for g in gaps
            if g.get("gap_type") not in ("compliant", "exceeds")
        ]

        items = []
        for gap in non_compliant:
            severity = gap.get("severity", "Medium")
            criticality = gap.get("metadata", {}).get("criticality", "medium")
            priority_score = SEVERITY_SCORES.get(severity, 2) * CRITICALITY_MULTIPLIERS.get(criticality, 2)

            reg_clause = gap.get("regulation_clause", {})
            rbi_citation = ""
            if reg_clause:
                section = reg_clause.get("section") or reg_clause.get("title", "")
                rbi_citation = f"RBI Master Direction, {section}"

            items.append({
                "gap_id": gap.get("id", ""),
                "title": gap.get("description", "")[:200],
                "gap_type": gap.get("gap_type", "missing"),
                "severity": severity,
                "criticality": criticality,
                "priority_score": priority_score,
                "rbi_citation": rbi_citation,
                "regulation_text": (reg_clause.get("text") or "")[:500],
                "policy_text": (gap.get("policy_clause", {}).get("text") or "")[:300],
                "suggested_action": gap.get("suggested_fix", "Review and address this compliance gap"),
                "timeline": REMEDIATION_TIMELINES.get(severity, "Within 90 days"),
                "assigned_department": gap.get("metadata", {}).get("assigned_department", "Compliance"),
                "missing_elements": gap.get("metadata", {}).get("missing_elements", []),
                "weak_elements": gap.get("metadata", {}).get("weak_elements", []),
                "evidence_required": [
                    e.get("indicator") for e in gap.get("evidence_map", [])
                    if e.get("status") in ("missing", "partial")
                ],
            })

        # Sort by priority score descending
        items.sort(key=lambda x: x["priority_score"], reverse=True)

        # Assign rank
        for i, item in enumerate(items):
            item["rank"] = i + 1

        return {
            "analysis_id": analysis_id,
            "total_gaps": len(gaps),
            "remediation_items": len(items),
            "critical_items": len([i for i in items if i["severity"] == "Critical"]),
            "high_items": len([i for i in items if i["severity"] == "High"]),
            "items": items,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_remediation_tasks(
        self,
        analysis_id: str,
        user_id: str,
        organization: str,
        max_tasks: int = 20
    ) -> Dict[str, Any]:
        """Auto-create tasks from top remediation items."""
        remediation = await self.generate_remediation_list(analysis_id, user_id)
        items = remediation.get("items", [])[:max_tasks]

        import uuid
        tasks_created = 0
        for item in items:
            task_doc = {
                "id": str(uuid.uuid4()),
                "title": f"Remediate: {item['title'][:100]}",
                "description": f"Gap Type: {item['gap_type']}\nSeverity: {item['severity']}\n\nRBI Citation: {item['rbi_citation']}\n\nAction: {item['suggested_action']}\n\nMissing: {', '.join(item.get('missing_elements', [])[:5])}",
                "status": "Open",
                "priority": item["severity"],
                "department": item.get("assigned_department"),
                "source_type": "gap_analysis",
                "gap_analysis_id": analysis_id,
                "gap_id": item.get("gap_id"),
                "user_id": user_id,
                "organization": organization,
                "due_date": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.db.tasks.insert_one(task_doc)
            tasks_created += 1

        return {
            "analysis_id": analysis_id,
            "tasks_created": tasks_created,
        }
