"""
Organization Profile Service for CompliAI

Manages organization profiles including entity classification (bank PA,
non-bank PA, etc.), license tracking, and regulatory scope determination.
"""

import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# Entity-specific compliance thresholds
ENTITY_THRESHOLDS = {
    "non_bank_pa": {
        "min_net_worth_crore": 15,
        "escrow_account_required": True,
        "nodal_account_required": True,
        "min_key_personnel": ["cco", "ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": True,
        "physical_inspection": False,
    },
    "bank_pa": {
        "min_net_worth_crore": None,
        "escrow_account_required": True,
        "nodal_account_required": True,
        "min_key_personnel": ["cco", "ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": False,
        "physical_inspection": False,
    },
    "pa_p": {
        "min_net_worth_crore": 15,
        "escrow_account_required": True,
        "nodal_account_required": True,
        "min_key_personnel": ["cco", "ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": True,
        "physical_inspection": True,
        "terminal_compliance_check": True,
    },
    "pg_only": {
        "min_net_worth_crore": None,
        "escrow_account_required": False,
        "nodal_account_required": False,
        "min_key_personnel": ["ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": False,
        "physical_inspection": False,
    },
    "nbfc": {
        "min_net_worth_crore": None,
        "escrow_account_required": False,
        "nodal_account_required": False,
        "min_key_personnel": ["cco"],
        "system_audit_frequency": "annual",
        "pravaah_required": False,
        "physical_inspection": False,
    },
}

# Entity type to regulation scope mapping
ENTITY_TO_REGULATIONS = {
    "bank_pa": ["rbi_pa_pg", "kyc_master", "it_governance"],
    "non_bank_pa": ["rbi_pa_pg", "kyc_master", "it_governance", "capital_adequacy"],
    "pa_p": ["rbi_pa_pg", "kyc_master", "it_governance", "capital_adequacy"],
    "pg_only": ["it_governance"],
    "nbfc": ["nbfc_master", "kyc_master", "digital_lending"],
    "digital_lender": ["digital_lending", "kyc_master"],
    "fintech": ["kyc_master", "it_governance"],
    "unknown": [],
}


def calculate_profile_completeness(profile: Dict[str, Any]) -> int:
    """Calculate profile completion percentage (0-100)."""
    score = 0

    # Entity classification (20 points)
    if profile.get('entity_type') and profile['entity_type'] != 'unknown':
        score += 10
    if profile.get('authorized_activities'):
        score += 10

    # License (20 points)
    if profile.get('license_status') and profile['license_status'] != 'not_applied':
        score += 10
    if profile.get('rbi_registration_number'):
        score += 10

    # Financial (20 points)
    if profile.get('net_worth_crore') is not None:
        score += 10
    if profile.get('escrow_bank_name') or profile.get('entity_type') in ['pg_only', 'bank_pa']:
        score += 10

    # Personnel (20 points)
    personnel = profile.get('key_personnel', [])
    roles = {p.get('role') for p in personnel}
    if 'cco' in roles:
        score += 10
    if 'ciso' in roles or 'cto' in roles:
        score += 10

    # Business (20 points)
    if profile.get('cin_number'):
        score += 10
    if profile.get('business_commencement_date'):
        score += 10

    return min(score, 100)


class OrganizationProfileService:
    """CRUD + business logic for organization profiles."""

    def __init__(self, db=None):
        self.db = db

    async def create_profile(
        self,
        organization_name: str,
        entity_type: str,
        created_by_user_id: str,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new organization profile."""
        # Check if profile already exists
        existing = await self.db.organizations.find_one(
            {"organization": organization_name}, {"_id": 0}
        )
        if existing:
            raise ValueError(f"Profile already exists for organization: {organization_name}")

        now = datetime.now(timezone.utc).isoformat()
        profile = {
            "id": str(uuid.uuid4()),
            "organization": organization_name,
            "entity_type": entity_type,
            "bank_type": profile_data.get("bank_type"),
            "authorized_activities": profile_data.get("authorized_activities", []),
            "business_categories": profile_data.get("business_categories", []),
            "license_status": profile_data.get("license_status", "not_applied"),
            "rbi_registration_number": profile_data.get("rbi_registration_number"),
            "authorization_date": profile_data.get("authorization_date"),
            "authorization_validity": profile_data.get("authorization_validity"),
            "pravaah_application_id": profile_data.get("pravaah_application_id"),
            "net_worth_crore": profile_data.get("net_worth_crore"),
            "net_worth_as_of": profile_data.get("net_worth_as_of"),
            "escrow_bank_name": profile_data.get("escrow_bank_name"),
            "escrow_account_number": profile_data.get("escrow_account_number"),
            "nodal_account_bank": profile_data.get("nodal_account_bank"),
            "nodal_account_number": profile_data.get("nodal_account_number"),
            "key_personnel": profile_data.get("key_personnel", []),
            "business_commencement_date": profile_data.get("business_commencement_date"),
            "registered_address": profile_data.get("registered_address"),
            "cin_number": profile_data.get("cin_number"),
            "website": profile_data.get("website"),
            "merchant_count": profile_data.get("merchant_count"),
            "annual_transaction_volume": profile_data.get("annual_transaction_volume"),
            "applicable_regulations": ENTITY_TO_REGULATIONS.get(entity_type, []),
            "compliance_charters": [],
            "last_rbi_inspection_date": None,
            "next_audit_due_date": None,
            "setup_completed": False,
            "setup_completion_pct": 0,
            "created_by": created_by_user_id,
            "updated_by": created_by_user_id,
            "created_at": now,
            "updated_at": now,
        }

        profile["setup_completion_pct"] = calculate_profile_completeness(profile)
        profile["setup_completed"] = profile["setup_completion_pct"] >= 60

        await self.db.organizations.insert_one(profile)
        # Remove MongoDB's _id field
        profile.pop("_id", None)

        logger.info(f"Created organization profile for '{organization_name}' (type: {entity_type})")
        return profile

    async def get_profile(self, organization: str) -> Optional[Dict[str, Any]]:
        """Get organization profile by name."""
        profile = await self.db.organizations.find_one(
            {"organization": organization}, {"_id": 0}
        )
        return profile

    async def update_profile(
        self,
        organization: str,
        update_data: Dict[str, Any],
        updated_by_user_id: str
    ) -> Dict[str, Any]:
        """Update organization profile with audit trail."""
        existing = await self.db.organizations.find_one(
            {"organization": organization}, {"_id": 0}
        )
        if not existing:
            raise ValueError(f"No profile found for organization: {organization}")

        now = datetime.now(timezone.utc).isoformat()

        # Record changes in history
        for field, new_value in update_data.items():
            if field in existing and existing[field] != new_value:
                history_entry = {
                    "id": str(uuid.uuid4()),
                    "organization": organization,
                    "timestamp": now,
                    "changed_by": updated_by_user_id,
                    "field": field,
                    "old_value": existing[field],
                    "new_value": new_value,
                }
                await self.db.organization_profile_history.insert_one(history_entry)

        # Update applicable_regulations if entity_type changed
        if "entity_type" in update_data:
            update_data["applicable_regulations"] = ENTITY_TO_REGULATIONS.get(
                update_data["entity_type"], []
            )

        update_data["updated_by"] = updated_by_user_id
        update_data["updated_at"] = now

        await self.db.organizations.update_one(
            {"organization": organization},
            {"$set": update_data}
        )

        # Recalculate completeness
        updated = await self.db.organizations.find_one(
            {"organization": organization}, {"_id": 0}
        )
        completeness = calculate_profile_completeness(updated)
        await self.db.organizations.update_one(
            {"organization": organization},
            {"$set": {
                "setup_completion_pct": completeness,
                "setup_completed": completeness >= 60,
            }}
        )

        result = await self.db.organizations.find_one(
            {"organization": organization}, {"_id": 0}
        )
        return result

    async def get_or_create_default_profile(
        self,
        organization: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get existing profile or create a minimal default."""
        profile = await self.get_profile(organization)
        if profile:
            return profile

        return await self.create_profile(
            organization_name=organization,
            entity_type="unknown",
            created_by_user_id=user_id,
            profile_data={}
        )

    async def get_applicable_entity_scope(self, organization: str) -> str:
        """Determine the ApplicabilityScope for requirement filtering."""
        profile = await self.get_profile(organization)
        if not profile:
            return "all"

        entity_type = profile.get("entity_type", "unknown")
        scope_map = {
            "bank_pa": "bank_pa",
            "non_bank_pa": "non_bank_pa",
            "pa_p": "pa_p",
            "pg_only": "pg_only",
            "nbfc": "all",
            "digital_lender": "all",
            "fintech": "all",
            "unknown": "all",
        }
        return scope_map.get(entity_type, "all")

    async def get_applicable_regulations(self, organization: str) -> List[str]:
        """Determine which regulation types apply."""
        profile = await self.get_profile(organization)
        if not profile:
            return []
        entity_type = profile.get("entity_type", "unknown")
        return ENTITY_TO_REGULATIONS.get(entity_type, [])

    def get_entity_specific_thresholds(self, entity_type: str) -> Dict[str, Any]:
        """Return entity-specific compliance thresholds."""
        return ENTITY_THRESHOLDS.get(entity_type, ENTITY_THRESHOLDS.get("non_bank_pa", {}))

    async def update_key_personnel(
        self,
        organization: str,
        personnel: List[Dict[str, Any]],
        updated_by_user_id: str
    ) -> Dict[str, Any]:
        """Update key personnel list."""
        return await self.update_profile(
            organization=organization,
            update_data={"key_personnel": personnel},
            updated_by_user_id=updated_by_user_id
        )

    async def update_license_status(
        self,
        organization: str,
        license_data: Dict[str, Any],
        updated_by_user_id: str
    ) -> Dict[str, Any]:
        """Update license/authorization status and record timeline event."""
        now = datetime.now(timezone.utc).isoformat()

        # Record timeline event
        timeline_event = {
            "id": str(uuid.uuid4()),
            "organization": organization,
            "date": license_data.get("date", now[:10]),
            "event": license_data.get("event", "status_update"),
            "title": license_data.get("title", "License status updated"),
            "description": license_data.get("description", ""),
            "details": license_data.get("details", {}),
            "recorded_by": updated_by_user_id,
            "created_at": now,
        }
        await self.db.license_timeline.insert_one(timeline_event)

        # Update profile fields
        update_fields = {}
        if "license_status" in license_data:
            update_fields["license_status"] = license_data["license_status"]
        if "rbi_registration_number" in license_data:
            update_fields["rbi_registration_number"] = license_data["rbi_registration_number"]
        if "authorization_date" in license_data:
            update_fields["authorization_date"] = license_data["authorization_date"]
        if "authorization_validity" in license_data:
            update_fields["authorization_validity"] = license_data["authorization_validity"]
        if "pravaah_application_id" in license_data:
            update_fields["pravaah_application_id"] = license_data["pravaah_application_id"]

        if update_fields:
            return await self.update_profile(
                organization=organization,
                update_data=update_fields,
                updated_by_user_id=updated_by_user_id
            )

        profile = await self.get_profile(organization)
        return profile

    async def get_license_timeline(
        self,
        organization: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get license status timeline events."""
        cursor = self.db.license_timeline.find(
            {"organization": organization}, {"_id": 0}
        ).sort("date", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_profile_history(
        self,
        organization: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get audit trail of profile changes."""
        cursor = self.db.organization_profile_history.find(
            {"organization": organization}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
