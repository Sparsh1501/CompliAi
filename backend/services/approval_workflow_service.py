"""
Dual-Approval Workflow Service for CompliAI (Task #13)

Implements configurable approval workflows for:
- Policy drafts (draft → review → approved → published)
- Compliance actions requiring sign-off
- Supports sequential approvals (e.g., CCO then Board)
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default approval chains by document type
DEFAULT_APPROVAL_CHAINS = {
    "policy": {
        "stages": [
            {"stage": 1, "role": "compliance_officer", "label": "Compliance Officer Review"},
            {"stage": 2, "role": "cco", "label": "CCO Approval"},
        ],
        "min_approvals_per_stage": 1,
    },
    "SOP": {
        "stages": [
            {"stage": 1, "role": "department_head", "label": "Department Head Review"},
            {"stage": 2, "role": "compliance_officer", "label": "Compliance Officer Approval"},
        ],
        "min_approvals_per_stage": 1,
    },
    "high_risk_policy": {
        "stages": [
            {"stage": 1, "role": "compliance_officer", "label": "Compliance Officer Review"},
            {"stage": 2, "role": "cco", "label": "CCO Approval"},
            {"stage": 3, "role": "board_member", "label": "Board Committee Approval"},
        ],
        "min_approvals_per_stage": 1,
    },
}


class ApprovalWorkflowService:
    """Manages dual/multi-approval workflows for policy documents."""

    def __init__(self, db=None):
        self.db = db

    async def create_approval_request(
        self,
        document_id: str,
        document_type: str,
        document_title: str,
        organization: str,
        requested_by: str,
        chain_type: str = None,
    ) -> Dict[str, Any]:
        """Create a new approval workflow for a document."""
        chain = DEFAULT_APPROVAL_CHAINS.get(chain_type or document_type, DEFAULT_APPROVAL_CHAINS["policy"])

        approval_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        approval_doc = {
            "id": approval_id,
            "document_id": document_id,
            "document_type": document_type,
            "document_title": document_title,
            "organization": organization,
            "requested_by": requested_by,
            "chain_type": chain_type or document_type,
            "current_stage": 1,
            "total_stages": len(chain["stages"]),
            "status": "pending",  # pending, in_review, approved, rejected
            "stages": [
                {
                    **stage,
                    "status": "pending" if stage["stage"] > 1 else "awaiting_review",
                    "approvals": [],
                    "rejections": [],
                }
                for stage in chain["stages"]
            ],
            "created_at": now,
            "updated_at": now,
        }

        await self.db.approval_workflows.insert_one(approval_doc)

        # Update the document status
        if document_type in ("policy", "SOP"):
            await self.db.policy_drafts.update_one(
                {"id": document_id},
                {"$set": {"status": "review", "approval_id": approval_id, "updated_at": now}}
            )

        return {
            "approval_id": approval_id,
            "document_id": document_id,
            "current_stage": 1,
            "total_stages": len(chain["stages"]),
            "status": "pending",
        }

    async def submit_decision(
        self,
        approval_id: str,
        user_id: str,
        user_role: str,
        decision: str,  # "approve" or "reject"
        comments: str = "",
    ) -> Dict[str, Any]:
        """Submit an approval or rejection for the current stage."""
        workflow = await self.db.approval_workflows.find_one({"id": approval_id}, {"_id": 0})
        if not workflow:
            return {"error": "Approval workflow not found"}

        if workflow["status"] in ("approved", "rejected"):
            return {"error": f"Workflow already {workflow['status']}"}

        current_stage = workflow["current_stage"]
        stage_data = None
        for s in workflow["stages"]:
            if s["stage"] == current_stage:
                stage_data = s
                break

        if not stage_data:
            return {"error": "Invalid workflow stage"}

        if stage_data["status"] not in ("awaiting_review", "in_review"):
            return {"error": f"Stage {current_stage} is not awaiting review"}

        now = datetime.now(timezone.utc).isoformat()
        decision_record = {
            "user_id": user_id,
            "user_role": user_role,
            "decision": decision,
            "comments": comments,
            "timestamp": now,
        }

        if decision == "approve":
            stage_data["approvals"].append(decision_record)
            stage_data["status"] = "approved"

            # Advance to next stage or complete
            if current_stage < workflow["total_stages"]:
                next_stage_idx = current_stage  # 0-indexed in list
                workflow["stages"][next_stage_idx]["status"] = "awaiting_review"
                workflow["current_stage"] = current_stage + 1
                workflow["status"] = "in_review"
            else:
                workflow["status"] = "approved"
                # Update document
                await self._update_document_status(workflow["document_id"], workflow["document_type"], "approved")
        else:
            stage_data["rejections"].append(decision_record)
            stage_data["status"] = "rejected"
            workflow["status"] = "rejected"
            await self._update_document_status(workflow["document_id"], workflow["document_type"], "rejected")

        workflow["updated_at"] = now
        await self.db.approval_workflows.replace_one({"id": approval_id}, workflow)

        return {
            "approval_id": approval_id,
            "decision": decision,
            "current_stage": workflow["current_stage"],
            "workflow_status": workflow["status"],
        }

    async def get_workflow(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get approval workflow details."""
        return await self.db.approval_workflows.find_one({"id": approval_id}, {"_id": 0})

    async def list_pending_approvals(self, organization: str, user_role: str = None) -> List[Dict[str, Any]]:
        """List pending approval requests, optionally filtered by role."""
        query = {"organization": organization, "status": {"$in": ["pending", "in_review"]}}
        cursor = self.db.approval_workflows.find(query, {"_id": 0}).sort("created_at", -1).limit(50)
        workflows = await cursor.to_list(length=50)

        if user_role:
            filtered = []
            for w in workflows:
                current_stage = w["current_stage"]
                for s in w["stages"]:
                    if s["stage"] == current_stage and s["role"] == user_role:
                        filtered.append(w)
                        break
            return filtered
        return workflows

    async def get_document_approval_history(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all approval workflow history for a document."""
        cursor = self.db.approval_workflows.find(
            {"document_id": document_id}, {"_id": 0}
        ).sort("created_at", -1)
        return await cursor.to_list(length=20)

    async def _update_document_status(self, document_id: str, document_type: str, status: str):
        """Update the source document's status."""
        now = datetime.now(timezone.utc).isoformat()
        if document_type in ("policy", "SOP"):
            await self.db.policy_drafts.update_one(
                {"id": document_id},
                {"$set": {"status": status, "updated_at": now}}
            )
