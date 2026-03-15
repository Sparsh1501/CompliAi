"""
Policy Version Control Service for CompliAI (Task #14)

Tracks policy document versions with:
- Version numbering (major.minor)
- Change tracking between versions
- Version comparison
- Rollback support
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PolicyVersionService:
    """Manages policy document versioning and change history."""

    def __init__(self, db=None):
        self.db = db

    async def create_version(
        self,
        draft_id: str,
        user_id: str,
        change_summary: str = "",
        bump_type: str = "minor",  # "major" or "minor"
    ) -> Dict[str, Any]:
        """Create a new version snapshot of a policy draft."""
        draft = await self.db.policy_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not draft:
            return {"error": "Draft not found"}

        # Get latest version number
        latest = await self.db.policy_versions.find_one(
            {"draft_id": draft_id},
            {"_id": 0, "version_major": 1, "version_minor": 1},
            sort=[("version_major", -1), ("version_minor", -1)]
        )

        if latest:
            if bump_type == "major":
                major = latest["version_major"] + 1
                minor = 0
            else:
                major = latest["version_major"]
                minor = latest["version_minor"] + 1
        else:
            major = 1
            minor = 0

        version_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        version_doc = {
            "id": version_id,
            "draft_id": draft_id,
            "version_major": major,
            "version_minor": minor,
            "version_label": f"v{major}.{minor}",
            "content": draft.get("content", {}),
            "title": draft.get("title", ""),
            "status": draft.get("status", "draft"),
            "change_summary": change_summary,
            "created_by": user_id,
            "created_at": now,
        }

        await self.db.policy_versions.insert_one(version_doc)

        # Update draft with current version info
        await self.db.policy_drafts.update_one(
            {"id": draft_id},
            {"$set": {
                "current_version": f"v{major}.{minor}",
                "version_id": version_id,
                "updated_at": now,
            }}
        )

        return {
            "version_id": version_id,
            "draft_id": draft_id,
            "version": f"v{major}.{minor}",
            "change_summary": change_summary,
        }

    async def list_versions(self, draft_id: str) -> List[Dict[str, Any]]:
        """List all versions of a policy draft."""
        cursor = self.db.policy_versions.find(
            {"draft_id": draft_id},
            {"_id": 0, "content": 0}  # Exclude content for list view
        ).sort([("version_major", -1), ("version_minor", -1)])
        return await cursor.to_list(length=100)

    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific version with full content."""
        return await self.db.policy_versions.find_one({"id": version_id}, {"_id": 0})

    async def compare_versions(self, version_id_a: str, version_id_b: str) -> Dict[str, Any]:
        """Compare two versions and return differences."""
        version_a = await self.get_version(version_id_a)
        version_b = await self.get_version(version_id_b)

        if not version_a or not version_b:
            return {"error": "One or both versions not found"}

        sections_a = version_a.get("content", {}).get("sections", [])
        sections_b = version_b.get("content", {}).get("sections", [])

        # Build section maps by heading
        map_a = {s.get("heading", ""): s for s in sections_a}
        map_b = {s.get("heading", ""): s for s in sections_b}

        changes = []
        all_headings = list(dict.fromkeys(
            [s.get("heading", "") for s in sections_a] +
            [s.get("heading", "") for s in sections_b]
        ))

        for heading in all_headings:
            sec_a = map_a.get(heading)
            sec_b = map_b.get(heading)

            if sec_a and not sec_b:
                changes.append({"type": "removed", "heading": heading, "content_before": sec_a.get("content", "")})
            elif sec_b and not sec_a:
                changes.append({"type": "added", "heading": heading, "content_after": sec_b.get("content", "")})
            elif sec_a and sec_b:
                content_a = sec_a.get("content", "")
                content_b = sec_b.get("content", "")
                if content_a != content_b:
                    changes.append({
                        "type": "modified",
                        "heading": heading,
                        "content_before": content_a[:500],
                        "content_after": content_b[:500],
                    })

        return {
            "version_a": version_a.get("version_label"),
            "version_b": version_b.get("version_label"),
            "draft_id": version_a.get("draft_id"),
            "total_changes": len(changes),
            "changes": changes,
        }

    async def rollback_to_version(self, draft_id: str, version_id: str, user_id: str) -> Dict[str, Any]:
        """Rollback a draft to a previous version."""
        version = await self.get_version(version_id)
        if not version:
            return {"error": "Version not found"}

        if version["draft_id"] != draft_id:
            return {"error": "Version does not belong to this draft"}

        now = datetime.now(timezone.utc).isoformat()

        # Update the draft content to the version's content
        await self.db.policy_drafts.update_one(
            {"id": draft_id},
            {"$set": {
                "content": version["content"],
                "title": version["title"],
                "status": "draft",
                "updated_at": now,
            }}
        )

        # Create a new version recording the rollback
        rollback_version = await self.create_version(
            draft_id=draft_id,
            user_id=user_id,
            change_summary=f"Rolled back to {version['version_label']}",
            bump_type="minor",
        )

        return {
            "draft_id": draft_id,
            "rolled_back_to": version["version_label"],
            "new_version": rollback_version.get("version"),
        }
