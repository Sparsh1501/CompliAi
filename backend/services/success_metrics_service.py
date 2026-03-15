"""
Success Metrics Tracking Service for CompliAI (Task #29)

Tracks and reports on compliance program success metrics:
- Time to compliance
- Gap remediation rate
- Policy coverage percentage
- Audit readiness score
- Evidence collection rate
- Task completion trends
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class SuccessMetricsService:
    """Tracks compliance program success metrics and KPIs."""

    def __init__(self, db=None):
        self.db = db

    async def get_compliance_metrics(self, organization: str) -> Dict[str, Any]:
        """Get comprehensive compliance success metrics for the organization."""
        now = datetime.now(timezone.utc)
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        ninety_days_ago = (now - timedelta(days=90)).isoformat()

        metrics = {
            "organization": organization,
            "generated_at": now.isoformat(),
            "overall": await self._get_overall_metrics(organization),
            "gap_remediation": await self._get_gap_remediation_metrics(organization, thirty_days_ago),
            "policy_coverage": await self._get_policy_coverage_metrics(organization),
            "task_completion": await self._get_task_completion_metrics(organization, thirty_days_ago),
            "evidence_collection": await self._get_evidence_metrics(organization),
            "audit_readiness": await self._get_audit_readiness(organization),
            "trend_30d": await self._get_trend_metrics(organization, thirty_days_ago),
            "trend_90d": await self._get_trend_metrics(organization, ninety_days_ago),
        }

        return metrics

    async def _get_overall_metrics(self, organization: str) -> Dict[str, Any]:
        """Get overall compliance score metrics."""
        pipeline = [
            {"$match": {"organization": organization}},
            {"$sort": {"created_at": -1}},
            {"$limit": 1},
        ]
        latest = await self.db.gap_analyses.aggregate(pipeline).to_list(length=1)

        if not latest:
            return {"latest_score": 0, "total_analyses": 0}

        total = await self.db.gap_analyses.count_documents({"organization": organization})

        return {
            "latest_score": latest[0].get("compliance_score", 0),
            "total_analyses": total,
            "latest_analysis_date": latest[0].get("created_at", ""),
        }

    async def _get_gap_remediation_metrics(self, organization: str, since: str) -> Dict[str, Any]:
        """Track gap remediation progress."""
        # Tasks created from gap analysis
        total_remediation_tasks = await self.db.tasks.count_documents({
            "organization": organization,
            "source_type": "gap_analysis",
        })
        completed_remediation = await self.db.tasks.count_documents({
            "organization": organization,
            "source_type": "gap_analysis",
            "status": {"$in": ["Completed", "Closed"]},
        })
        recent_completed = await self.db.tasks.count_documents({
            "organization": organization,
            "source_type": "gap_analysis",
            "status": {"$in": ["Completed", "Closed"]},
            "updated_at": {"$gte": since},
        })

        remediation_rate = round((completed_remediation / max(total_remediation_tasks, 1)) * 100, 1)

        return {
            "total_tasks": total_remediation_tasks,
            "completed": completed_remediation,
            "pending": total_remediation_tasks - completed_remediation,
            "remediation_rate": remediation_rate,
            "recent_completed_30d": recent_completed,
        }

    async def _get_policy_coverage_metrics(self, organization: str) -> Dict[str, Any]:
        """Track policy coverage across regulation requirements."""
        total_policies = await self.db.policies.count_documents({"organization": organization})
        total_regulations = await self.db.regulations.count_documents({})
        total_analyses = await self.db.gap_analyses.count_documents({"organization": organization})
        total_drafts = await self.db.policy_drafts.count_documents({"organization": organization})
        approved_drafts = await self.db.policy_drafts.count_documents({
            "organization": organization,
            "status": {"$in": ["approved", "published"]},
        })

        return {
            "total_policies": total_policies,
            "total_regulations": total_regulations,
            "total_analyses_run": total_analyses,
            "total_drafts": total_drafts,
            "approved_drafts": approved_drafts,
            "coverage_rate": round((total_analyses / max(total_regulations, 1)) * 100, 1),
        }

    async def _get_task_completion_metrics(self, organization: str, since: str) -> Dict[str, Any]:
        """Track task completion rates and trends."""
        total = await self.db.tasks.count_documents({"organization": organization})
        completed = await self.db.tasks.count_documents({
            "organization": organization,
            "status": {"$in": ["Completed", "Closed"]},
        })
        overdue = await self.db.tasks.count_documents({
            "organization": organization,
            "status": {"$nin": ["Completed", "Closed"]},
            "due_date": {"$lt": datetime.now(timezone.utc).isoformat(), "$ne": None},
        })
        recent_created = await self.db.tasks.count_documents({
            "organization": organization,
            "created_at": {"$gte": since},
        })
        recent_completed = await self.db.tasks.count_documents({
            "organization": organization,
            "status": {"$in": ["Completed", "Closed"]},
            "updated_at": {"$gte": since},
        })

        return {
            "total": total,
            "completed": completed,
            "in_progress": total - completed,
            "overdue": overdue,
            "completion_rate": round((completed / max(total, 1)) * 100, 1),
            "tasks_created_30d": recent_created,
            "tasks_completed_30d": recent_completed,
        }

    async def _get_evidence_metrics(self, organization: str) -> Dict[str, Any]:
        """Track evidence collection progress."""
        total = await self.db.evidence.count_documents({"organization": organization})
        validated = await self.db.evidence.count_documents({
            "organization": organization,
            "validation_status": "valid",
        })
        pending = await self.db.evidence.count_documents({
            "organization": organization,
            "validation_status": {"$in": ["pending", "needs_review"]},
        })

        return {
            "total_evidence": total,
            "validated": validated,
            "pending": pending,
            "validation_rate": round((validated / max(total, 1)) * 100, 1),
        }

    async def _get_audit_readiness(self, organization: str) -> Dict[str, Any]:
        """Calculate audit readiness score based on multiple factors."""
        # Get latest gap analysis score
        latest_analysis = await self.db.gap_analyses.find_one(
            {"organization": organization},
            {"_id": 0, "compliance_score": 1},
            sort=[("created_at", -1)]
        )
        compliance_score = (latest_analysis or {}).get("compliance_score", 0)

        # Evidence completeness
        total_evidence = await self.db.evidence.count_documents({"organization": organization})
        valid_evidence = await self.db.evidence.count_documents({
            "organization": organization, "validation_status": "valid",
        })
        evidence_rate = round((valid_evidence / max(total_evidence, 1)) * 100, 1)

        # Task completion
        total_tasks = await self.db.tasks.count_documents({"organization": organization})
        completed_tasks = await self.db.tasks.count_documents({
            "organization": organization, "status": {"$in": ["Completed", "Closed"]},
        })
        task_rate = round((completed_tasks / max(total_tasks, 1)) * 100, 1)

        # Policy coverage
        total_policies = await self.db.policies.count_documents({"organization": organization})
        has_policies = 100 if total_policies > 0 else 0

        # Weighted audit readiness
        readiness = round(
            compliance_score * 0.4 +
            evidence_rate * 0.25 +
            task_rate * 0.2 +
            has_policies * 0.15
        , 1)

        return {
            "readiness_score": readiness,
            "components": {
                "compliance_score": {"value": compliance_score, "weight": 0.4},
                "evidence_completeness": {"value": evidence_rate, "weight": 0.25},
                "task_completion": {"value": task_rate, "weight": 0.2},
                "policy_coverage": {"value": has_policies, "weight": 0.15},
            },
            "status": "ready" if readiness >= 80 else "preparing" if readiness >= 60 else "not_ready",
        }

    async def _get_trend_metrics(self, organization: str, since: str) -> Dict[str, Any]:
        """Get trend data over a period."""
        pipeline = [
            {"$match": {"organization": organization, "created_at": {"$gte": since}}},
            {"$sort": {"created_at": 1}},
            {"$project": {"_id": 0, "created_at": 1, "compliance_score": 1}},
        ]
        analyses = await self.db.gap_analyses.aggregate(pipeline).to_list(length=100)

        return {
            "data_points": len(analyses),
            "scores": [
                {"date": a.get("created_at", ""), "score": a.get("compliance_score", 0)}
                for a in analyses
            ],
        }
