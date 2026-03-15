"""
Audit Trail Service for CompliAI (Task #16)

Records all compliance-relevant actions for audit purposes:
- Document uploads, edits, deletions
- Gap analysis runs
- Approval decisions
- Policy changes
- Evidence submissions
- Login/access events
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Action categories for filtering
ACTION_CATEGORIES = {
    "document": ["upload", "edit", "delete", "download", "version_create"],
    "analysis": ["gap_analysis_run", "report_generate", "score_calculate"],
    "policy": ["draft_create", "draft_edit", "status_change", "version_create", "rollback"],
    "approval": ["approval_request", "approval_decision", "approval_reject"],
    "evidence": ["evidence_upload", "evidence_validate", "evidence_delete"],
    "compliance": ["check_run", "remediation_create", "task_create"],
    "access": ["login", "logout", "role_change", "permission_change"],
    "settings": ["profile_update", "config_change"],
}


class AuditTrailService:
    """Records and queries audit trail entries for compliance tracking."""

    def __init__(self, db=None):
        self.db = db

    async def log_action(
        self,
        action: str,
        category: str,
        user_id: str,
        organization: str,
        resource_type: str = "",
        resource_id: str = "",
        details: Dict[str, Any] = None,
        ip_address: str = "",
    ) -> str:
        """Record an audit trail entry. Returns the audit entry ID."""
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        entry = {
            "id": entry_id,
            "action": action,
            "category": category,
            "user_id": user_id,
            "organization": organization,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "timestamp": now,
        }

        await self.db.audit_trail.insert_one(entry)
        return entry_id

    async def get_trail(
        self,
        organization: str,
        category: str = None,
        user_id: str = None,
        resource_type: str = None,
        resource_id: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Query audit trail with filters."""
        query = {"organization": organization}
        if category:
            query["category"] = category
        if user_id:
            query["user_id"] = user_id
        if resource_type:
            query["resource_type"] = resource_type
        if resource_id:
            query["resource_id"] = resource_id
        if start_date:
            query.setdefault("timestamp", {})["$gte"] = start_date
        if end_date:
            query.setdefault("timestamp", {})["$lte"] = end_date

        total = await self.db.audit_trail.count_documents(query)
        cursor = self.db.audit_trail.find(
            query, {"_id": 0}
        ).sort("timestamp", -1).skip(offset).limit(limit)
        entries = await cursor.to_list(length=limit)

        return {
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_resource_history(self, resource_type: str, resource_id: str) -> List[Dict[str, Any]]:
        """Get full audit history for a specific resource."""
        cursor = self.db.audit_trail.find(
            {"resource_type": resource_type, "resource_id": resource_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(200)
        return await cursor.to_list(length=200)

    async def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activity for a specific user."""
        cursor = self.db.audit_trail.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_activity_summary(self, organization: str, days: int = 30) -> Dict[str, Any]:
        """Get activity summary for the organization over a period."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        pipeline = [
            {"$match": {"organization": organization, "timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "latest": {"$max": "$timestamp"},
            }},
            {"$sort": {"count": -1}},
        ]

        results = await self.db.audit_trail.aggregate(pipeline).to_list(length=20)

        total_actions = sum(r["count"] for r in results)
        by_category = {r["_id"]: {"count": r["count"], "latest": r["latest"]} for r in results}

        # Unique users
        user_pipeline = [
            {"$match": {"organization": organization, "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$user_id"}},
            {"$count": "unique_users"},
        ]
        user_result = await self.db.audit_trail.aggregate(user_pipeline).to_list(length=1)
        unique_users = user_result[0]["unique_users"] if user_result else 0

        return {
            "period_days": days,
            "total_actions": total_actions,
            "unique_users": unique_users,
            "by_category": by_category,
        }
