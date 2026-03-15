"""
Regulatory Amendment Feed Service for CompliAI (Task #2)

Manages regulatory amendment tracking and notifications:
- Tracks amendments to RBI Master Directions
- Stores amendment metadata and change summaries
- Provides a feed of recent regulatory changes
- Supports subscription/alert preferences per organization
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Known regulatory sources
REGULATORY_SOURCES = {
    "rbi_pa_pg": {
        "name": "RBI Master Direction on PA/PG",
        "issuer": "Reserve Bank of India",
        "url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12156",
        "current_version": "September 2025",
    },
    "rbi_digital_lending": {
        "name": "RBI Guidelines on Digital Lending",
        "issuer": "Reserve Bank of India",
        "url": "https://www.rbi.org.in",
        "current_version": "September 2022",
    },
    "npci_upi": {
        "name": "NPCI UPI Procedural Guidelines",
        "issuer": "NPCI",
        "url": "https://www.npci.org.in",
        "current_version": "Latest",
    },
    "fiu_ind": {
        "name": "FIU-IND PMLA Compliance",
        "issuer": "FIU-IND",
        "url": "https://fiuindia.gov.in",
        "current_version": "Latest",
    },
}


class RegulatoryFeedService:
    """Manages regulatory amendment tracking and subscriptions."""

    def __init__(self, db=None):
        self.db = db

    async def create_amendment(
        self,
        source_key: str,
        title: str,
        summary: str,
        effective_date: str,
        change_type: str = "amendment",  # amendment, circular, notification, guideline
        impact_areas: List[str] = None,
        full_text: str = "",
        url: str = "",
        created_by: str = "",
    ) -> Dict[str, Any]:
        """Record a new regulatory amendment."""
        amendment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        source = REGULATORY_SOURCES.get(source_key, {})

        doc = {
            "id": amendment_id,
            "source_key": source_key,
            "source_name": source.get("name", source_key),
            "issuer": source.get("issuer", ""),
            "title": title,
            "summary": summary,
            "full_text": full_text,
            "url": url,
            "change_type": change_type,
            "effective_date": effective_date,
            "impact_areas": impact_areas or [],
            "status": "active",
            "created_by": created_by,
            "created_at": now,
        }

        await self.db.regulatory_amendments.insert_one(doc)

        return {
            "amendment_id": amendment_id,
            "title": title,
            "source": source.get("name", source_key),
            "effective_date": effective_date,
        }

    async def get_feed(
        self,
        source_key: str = None,
        change_type: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get regulatory amendment feed."""
        query = {"status": "active"}
        if source_key:
            query["source_key"] = source_key
        if change_type:
            query["change_type"] = change_type

        total = await self.db.regulatory_amendments.count_documents(query)
        cursor = self.db.regulatory_amendments.find(
            query, {"_id": 0, "full_text": 0}
        ).sort("created_at", -1).skip(offset).limit(limit)
        amendments = await cursor.to_list(length=limit)

        return {
            "amendments": amendments,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_amendment(self, amendment_id: str) -> Optional[Dict[str, Any]]:
        """Get full details of an amendment."""
        return await self.db.regulatory_amendments.find_one({"id": amendment_id}, {"_id": 0})

    async def subscribe(
        self,
        organization: str,
        user_id: str,
        source_keys: List[str] = None,
        alert_types: List[str] = None,
    ) -> Dict[str, Any]:
        """Subscribe to regulatory amendment alerts."""
        sub_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        sub_doc = {
            "id": sub_id,
            "organization": organization,
            "user_id": user_id,
            "source_keys": source_keys or list(REGULATORY_SOURCES.keys()),
            "alert_types": alert_types or ["amendment", "circular", "notification", "guideline"],
            "active": True,
            "created_at": now,
        }

        # Upsert - one subscription per user per org
        await self.db.regulatory_subscriptions.update_one(
            {"user_id": user_id, "organization": organization},
            {"$set": sub_doc},
            upsert=True,
        )

        return {
            "subscription_id": sub_id,
            "sources": sub_doc["source_keys"],
            "alert_types": sub_doc["alert_types"],
            "active": True,
        }

    async def get_subscription(self, user_id: str, organization: str) -> Optional[Dict[str, Any]]:
        """Get user's subscription preferences."""
        return await self.db.regulatory_subscriptions.find_one(
            {"user_id": user_id, "organization": organization},
            {"_id": 0}
        )

    async def get_impact_assessment(self, amendment_id: str, organization: str) -> Dict[str, Any]:
        """Assess impact of an amendment on the organization's compliance status."""
        amendment = await self.get_amendment(amendment_id)
        if not amendment:
            return {"error": "Amendment not found"}

        # Check if org has gap analyses affected by this amendment's impact areas
        impact_areas = amendment.get("impact_areas", [])
        affected_analyses = []
        if impact_areas:
            cursor = self.db.gap_analyses.find(
                {"organization": organization},
                {"_id": 0, "id": 1, "policy_title": 1, "regulation_title": 1, "compliance_score": 1}
            ).sort("created_at", -1).limit(10)
            affected_analyses = await cursor.to_list(length=10)

        return {
            "amendment_id": amendment_id,
            "title": amendment.get("title", ""),
            "impact_areas": impact_areas,
            "affected_analyses": len(affected_analyses),
            "analyses": affected_analyses,
            "recommendation": "Re-run gap analysis to assess impact of this regulatory change." if affected_analyses else "No existing analyses to assess.",
        }

    def list_sources(self) -> List[Dict[str, Any]]:
        """List all known regulatory sources."""
        return [
            {"key": k, **v}
            for k, v in REGULATORY_SOURCES.items()
        ]
