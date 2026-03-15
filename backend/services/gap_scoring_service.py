"""
Gap Scoring and Compliance Percentage Service for CompliAI

Provides reusable scoring functions for gap analysis results:
- Weighted compliance scoring by criticality
- Category-level compliance breakdown
- Compliance trend tracking over time
- RBI-specific compliance thresholds
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Gap type to compliance score mapping
GAP_TYPE_SCORES = {
    "compliant": 100,
    "exceeds": 100,
    "partial": 60,
    "weak": 75,
    "missing": 0,
    "conflicting": 0,
}

# Criticality weights
CRITICALITY_WEIGHTS = {
    "high": 3,
    "medium": 2,
    "low": 1,
}

# RBI compliance thresholds
COMPLIANCE_THRESHOLDS = {
    "acceptable": 80,      # >= 80% is acceptable
    "warning": 60,         # 60-79% needs attention
    "critical": 40,        # < 40% is critical
}


class GapScoringService:
    """Calculates compliance scores and generates compliance reports."""

    def __init__(self, db=None):
        self.db = db

    def calculate_weighted_score(self, gaps: List[Dict[str, Any]]) -> float:
        """
        Calculate weighted compliance score from gap results.
        Weights by criticality: high=3, medium=2, low=1.
        Returns 0-100 score.
        """
        if not gaps:
            return 0.0

        weighted_sum = 0.0
        max_weighted_sum = 0.0

        for gap in gaps:
            gap_type = gap.get("gap_type", "missing")
            criticality = gap.get("criticality") or gap.get("metadata", {}).get("criticality", "medium")
            weight = CRITICALITY_WEIGHTS.get(criticality, 2)
            score = GAP_TYPE_SCORES.get(gap_type, 50)
            weighted_sum += score * weight
            max_weighted_sum += 100 * weight

        if max_weighted_sum == 0:
            return 0.0

        return round((weighted_sum / max_weighted_sum) * 100, 1)

    def calculate_category_scores(self, gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate compliance scores broken down by subject category.
        Returns dict of { category: { score, total, compliant, partial, missing, gaps } }
        """
        categories = {}
        for gap in gaps:
            category = gap.get("metadata", {}).get("subject_category") or gap.get("subject_category", "general")
            if category not in categories:
                categories[category] = {"gaps": [], "total": 0, "compliant": 0, "partial": 0, "missing": 0}
            categories[category]["gaps"].append(gap)
            categories[category]["total"] += 1

            gap_type = gap.get("gap_type", "missing")
            if gap_type in ("compliant", "exceeds"):
                categories[category]["compliant"] += 1
            elif gap_type in ("partial", "weak"):
                categories[category]["partial"] += 1
            else:
                categories[category]["missing"] += 1

        result = {}
        for cat, data in categories.items():
            result[cat] = {
                "score": self.calculate_weighted_score(data["gaps"]),
                "total": data["total"],
                "compliant": data["compliant"],
                "partial": data["partial"],
                "missing": data["missing"],
                "status": self._get_compliance_status(self.calculate_weighted_score(data["gaps"])),
            }
        return result

    def calculate_severity_breakdown(self, gaps: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count gaps by severity."""
        breakdown = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for gap in gaps:
            severity = gap.get("severity", "Medium")
            if severity in breakdown:
                breakdown[severity] += 1
        return breakdown

    def calculate_gap_type_breakdown(self, gaps: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count gaps by type."""
        breakdown = {"compliant": 0, "exceeds": 0, "partial": 0, "weak": 0, "missing": 0, "conflicting": 0}
        for gap in gaps:
            gap_type = gap.get("gap_type", "missing")
            if gap_type in breakdown:
                breakdown[gap_type] += 1
        return breakdown

    def generate_compliance_summary(self, gaps: List[Dict[str, Any]], policy_title: str = "", regulation_title: str = "") -> Dict[str, Any]:
        """
        Generate a complete compliance summary with all metrics.
        Used by dashboard, reports, and export features.
        """
        overall_score = self.calculate_weighted_score(gaps)
        category_scores = self.calculate_category_scores(gaps)
        severity_breakdown = self.calculate_severity_breakdown(gaps)
        type_breakdown = self.calculate_gap_type_breakdown(gaps)

        # Priority action items (critical + high severity non-compliant)
        priority_gaps = [
            g for g in gaps
            if g.get("gap_type") in ("missing", "conflicting", "weak")
            and g.get("severity") in ("Critical", "High")
        ]

        return {
            "overall_score": overall_score,
            "status": self._get_compliance_status(overall_score),
            "total_requirements": len(gaps),
            "compliant_count": type_breakdown["compliant"] + type_breakdown["exceeds"],
            "partial_count": type_breakdown["partial"] + type_breakdown["weak"],
            "non_compliant_count": type_breakdown["missing"] + type_breakdown["conflicting"],
            "category_scores": category_scores,
            "severity_breakdown": severity_breakdown,
            "type_breakdown": type_breakdown,
            "priority_action_count": len(priority_gaps),
            "policy_title": policy_title,
            "regulation_title": regulation_title,
            "thresholds": COMPLIANCE_THRESHOLDS,
        }

    def _get_compliance_status(self, score: float) -> str:
        """Map score to status label."""
        if score >= COMPLIANCE_THRESHOLDS["acceptable"]:
            return "acceptable"
        elif score >= COMPLIANCE_THRESHOLDS["warning"]:
            return "warning"
        elif score >= COMPLIANCE_THRESHOLDS["critical"]:
            return "needs_attention"
        else:
            return "critical"

    async def get_compliance_trend(
        self,
        policy_id: Optional[str] = None,
        regulation_id: Optional[str] = None,
        organization: str = "",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get compliance score trend over time from historical gap analyses.
        Returns list of { date, score, analysis_id }.
        """
        if not self.db:
            return []

        query = {"organization": organization}
        if policy_id:
            query["policy_id"] = policy_id
        if regulation_id:
            query["regulation_id"] = regulation_id

        cursor = self.db.gap_analyses.find(
            query,
            {"_id": 0, "id": 1, "compliance_score": 1, "created_at": 1, "policy_id": 1, "regulation_id": 1}
        ).sort("created_at", -1).limit(limit)

        analyses = await cursor.to_list(length=limit)
        return [
            {
                "date": a.get("created_at", ""),
                "score": a.get("compliance_score", 0),
                "analysis_id": a.get("id", ""),
            }
            for a in reversed(analyses)  # Chronological order
        ]

    async def get_organization_compliance_overview(self, organization: str) -> Dict[str, Any]:
        """
        Get organization-wide compliance overview across all analyses.
        Used by the main dashboard.
        """
        if not self.db:
            return {"average_score": 0, "total_analyses": 0, "recent_analyses": []}

        pipeline = [
            {"$match": {"organization": organization}},
            {"$sort": {"created_at": -1}},
            {"$limit": 50},
            {"$group": {
                "_id": None,
                "average_score": {"$avg": "$compliance_score"},
                "total_analyses": {"$sum": 1},
                "latest_score": {"$first": "$compliance_score"},
                "latest_date": {"$first": "$created_at"},
            }}
        ]

        result = await self.db.gap_analyses.aggregate(pipeline).to_list(length=1)
        if not result:
            return {"average_score": 0, "total_analyses": 0, "latest_score": 0}

        r = result[0]
        return {
            "average_score": round(r.get("average_score", 0), 1),
            "total_analyses": r.get("total_analyses", 0),
            "latest_score": round(r.get("latest_score", 0), 1),
            "latest_date": r.get("latest_date", ""),
            "status": self._get_compliance_status(r.get("average_score", 0)),
        }
