"""
Requirement Mapping Service for CompliAI

Extracts discrete regulatory requirements from regulation clauses,
catalogues them with structured metadata, and maps them to policy
clauses for gap analysis consumption.
"""

import anthropic
import os
import json
import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Requirement ID category short codes
CATEGORY_CODES = {
    "authorisation": "AUTH",
    "capital_requirements": "CAP",
    "merchant_onboarding": "MER",
    "settlement_operations": "SET",
    "escrow_accounts": "ESC",
    "fraud_monitoring": "FRM",
    "governance_compliance": "GOV",
    "technology_security": "TEC",
    "customer_protection": "CUS",
    "pa_p_physical": "PAP",
    "kyc_cdd": "KYC",
    "aml_cft": "AML",
    "data_protection": "DAT",
    "outsourcing": "OUT",
    "reporting": "RPT",
    "grievance_redressal": "GRV",
    "risk_management": "RSK",
    "information_security": "ISC",
    "licensing": "LIC",
    "general": "GEN",
}

BODY_CODES = {
    "RBI": "RBI",
    "NPCI": "NPCI",
    "FIU-IND": "FIU",
    "SEBI": "SEBI",
}

VALID_CATEGORIES = list(CATEGORY_CODES.keys())


def generate_requirement_id(body: str, regulation_code: str, category: str, sequence: int) -> str:
    """Generate structured requirement ID like RBI-PAPG-AUTH-001."""
    body_code = BODY_CODES.get(body, body[:3].upper())
    cat_code = CATEGORY_CODES.get(category, category[:3].upper())
    return f"{body_code}-{regulation_code}-{cat_code}-{sequence:03d}"


class RequirementMappingService:
    """Extracts, catalogs, and maps regulatory requirements."""

    def __init__(self, db=None, vector_service=None):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
        self.model = "claude-sonnet-4-20250514"
        self.db = db
        self.vector_service = vector_service

    # =========================================================================
    # PHASE 1: CATALOG — Extract requirements from regulation clauses
    # =========================================================================

    async def extract_requirements(
        self,
        regulation_id: str,
        regulation_title: str,
        clauses: List[Dict[str, Any]],
        regulatory_body: str = "RBI",
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Extract discrete requirements from regulation clauses using LLM."""
        if not self.client:
            logger.warning("Anthropic API key not configured, skipping requirement extraction")
            return []

        all_requirements = []
        existing_titles = []
        batch_size = 5
        total = len(clauses)

        for i in range(0, total, batch_size):
            batch = clauses[i:i + batch_size]

            if progress_callback:
                try:
                    pct = int((i / total) * 80)
                    await progress_callback("extracting", pct, f"Extracting requirements from clauses {i+1}-{i+len(batch)}...", {})
                except Exception:
                    pass

            try:
                batch_reqs = await self._extract_batch(
                    clauses_batch=batch,
                    regulation_title=regulation_title,
                    regulatory_body=regulatory_body,
                    existing_req_titles=existing_titles
                )
                for req in batch_reqs:
                    req["regulation_id"] = regulation_id
                    existing_titles.append(req.get("title", ""))
                all_requirements.extend(batch_reqs)
            except Exception as e:
                logger.error(f"Requirement extraction batch {i} failed: {e}")

            if i + batch_size < total:
                await asyncio.sleep(0.5)

        # Assign structured IDs
        reg_code = self._detect_regulation_code(regulation_title)
        all_requirements = self._assign_requirement_ids(all_requirements, regulatory_body, reg_code)

        if progress_callback:
            try:
                await progress_callback("extracted", 85, f"Extracted {len(all_requirements)} requirements", {})
            except Exception:
                pass

        return all_requirements

    async def _extract_batch(
        self,
        clauses_batch: List[Dict[str, Any]],
        regulation_title: str,
        regulatory_body: str,
        existing_req_titles: List[str]
    ) -> List[Dict[str, Any]]:
        """LLM call to extract requirements from a batch of clauses."""
        clauses_text = ""
        for c in clauses_batch:
            cid = c.get("clause_id", "unknown")
            title = c.get("title", "Untitled")
            text = (c.get("original_text") or c.get("text", ""))[:1500]
            category = c.get("subject_category", "general")
            clauses_text += f"\n--- Clause {cid} [{title}] (category: {category}) ---\n{text}\n"

        existing_str = ", ".join(existing_req_titles[-30:]) if existing_req_titles else "None yet"

        prompt = f"""You are a regulatory compliance expert. Given regulation clauses from "{regulation_title}" issued by {regulatory_body}, extract ALL discrete, testable compliance requirements.

For EACH requirement, provide JSON with:
- title: Short name
- description: Full requirement text in clear compliance language
- rbi_para_reference: Paragraph reference (e.g. "Para 5.1(a)")
- category: One of {VALID_CATEGORIES}
- requirement_type: mandatory | recommended | prohibition | conditional | informational
- criticality: high | medium | low
- entity_applicability: Array from [all_pa, bank_pa, non_bank_pa, pa_p, pa_online, pg_only, all]
- compliance_indicators: List of specific verifiable items that prove compliance
- evidence_types: Array from [document, process, record, control, training, report]
- source_clause_ids: Which clause IDs this derives from

IMPORTANT:
- One clause may contain MULTIPLE requirements (split them)
- Do NOT duplicate: {existing_str}
- Focus on TESTABLE obligations

CLAUSES:
{clauses_text}

Return a JSON array of requirement objects. Return ONLY valid JSON, no markdown."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            # Try to parse JSON
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            requirements = json.loads(text)
            if isinstance(requirements, dict):
                requirements = requirements.get("requirements", [requirements])
            return requirements if isinstance(requirements, list) else []
        except Exception as e:
            logger.error(f"LLM requirement extraction failed: {e}")
            return []

    def _detect_regulation_code(self, title: str) -> str:
        """Detect short code from regulation title."""
        title_lower = title.lower()
        if "payment aggregat" in title_lower or "pa/pg" in title_lower or "pa-p" in title_lower:
            return "PAPG"
        if "digital lending" in title_lower:
            return "DL"
        if "kyc" in title_lower or "know your customer" in title_lower:
            return "KYC"
        if "nbfc" in title_lower:
            return "NBFC"
        if "upi" in title_lower:
            return "UPI"
        return "REG"

    def _assign_requirement_ids(
        self,
        requirements: List[Dict],
        regulatory_body: str,
        regulation_code: str
    ) -> List[Dict]:
        """Assign structured IDs like RBI-PAPG-AUTH-001."""
        category_counters = {}
        for req in requirements:
            category = req.get("category", "general")
            if category not in category_counters:
                category_counters[category] = 0
            category_counters[category] += 1
            req["requirement_id"] = generate_requirement_id(
                regulatory_body, regulation_code, category, category_counters[category]
            )
        return requirements

    async def store_requirements(
        self,
        requirements: List[Dict[str, Any]],
        regulation_id: str
    ) -> int:
        """Persist requirements to MongoDB."""
        if not requirements:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        stored = 0
        for req in requirements:
            doc = {
                "id": str(uuid.uuid4()),
                "requirement_id": req.get("requirement_id", ""),
                "regulation_id": regulation_id,
                "source_clause_ids": req.get("source_clause_ids", []),
                "title": req.get("title", ""),
                "description": req.get("description", ""),
                "original_text_excerpts": req.get("original_text_excerpts", []),
                "rbi_para_reference": req.get("rbi_para_reference", ""),
                "category": req.get("category", "general"),
                "sub_category": req.get("sub_category"),
                "requirement_type": req.get("requirement_type", "mandatory"),
                "criticality": req.get("criticality", "medium"),
                "entity_applicability": req.get("entity_applicability", ["all"]),
                "effective_date": req.get("effective_date"),
                "transition_period_days": req.get("transition_period_days"),
                "compliance_indicators": req.get("compliance_indicators", []),
                "evidence_types": req.get("evidence_types", []),
                "depends_on": req.get("depends_on", []),
                "related_requirements": req.get("related_requirements", []),
                "status": "active",
                "version": 1,
                "organization": "system",
                "created_at": now,
                "updated_at": now,
            }
            try:
                # Upsert by requirement_id to avoid duplicates
                await self.db.requirements.update_one(
                    {"requirement_id": doc["requirement_id"], "regulation_id": regulation_id},
                    {"$set": doc},
                    upsert=True
                )
                stored += 1
            except Exception as e:
                logger.error(f"Failed to store requirement {doc['requirement_id']}: {e}")

        # Embed in Qdrant if vector service available
        if self.vector_service:
            try:
                await self._embed_requirements(requirements, regulation_id)
            except Exception as e:
                logger.warning(f"Requirement embedding failed (non-fatal): {e}")

        logger.info(f"Stored {stored} requirements for regulation {regulation_id}")
        return stored

    async def _embed_requirements(self, requirements: List[Dict], regulation_id: str):
        """Embed requirements in Qdrant for semantic search."""
        if not self.vector_service or not self.vector_service.qdrant_client:
            return

        for req in requirements:
            text = f"{req.get('title', '')} {req.get('description', '')} {' '.join(req.get('compliance_indicators', []))}"
            try:
                await self.vector_service.store_clause_embedding(
                    clause_id=req.get("requirement_id", str(uuid.uuid4())),
                    text=text,
                    metadata={
                        "type": "requirement",
                        "regulation_id": regulation_id,
                        "category": req.get("category", "general"),
                        "criticality": req.get("criticality", "medium"),
                    },
                    collection_name="regulation_clauses"
                )
            except Exception as e:
                logger.debug(f"Failed to embed requirement: {e}")

    async def get_requirements_for_regulation(
        self,
        regulation_id: str,
        entity_type: Optional[str] = None,
        category: Optional[str] = None,
        status: str = "active"
    ) -> List[Dict]:
        """Retrieve requirements with optional filtering."""
        query = {"regulation_id": regulation_id, "status": status}
        if category:
            query["category"] = category

        cursor = self.db.requirements.find(query, {"_id": 0})
        requirements = await cursor.to_list(length=500)

        # Filter by entity applicability
        if entity_type and entity_type != "all":
            filtered = []
            for req in requirements:
                applicability = req.get("entity_applicability", ["all"])
                if "all" in applicability or "all_pa" in applicability or entity_type in applicability:
                    filtered.append(req)
            return filtered

        return requirements

    # =========================================================================
    # PHASE 2: MAP — Map requirements to policy clauses
    # =========================================================================

    async def map_requirements_to_policy(
        self,
        regulation_id: str,
        policy_id: str,
        policy_clauses: List[Dict[str, Any]],
        entity_type: str = "all",
        organization: str = "",
        user_id: str = "",
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Map all applicable requirements against policy clauses."""
        requirements = await self.get_requirements_for_regulation(
            regulation_id=regulation_id,
            entity_type=entity_type
        )

        if not requirements:
            return {
                "id": str(uuid.uuid4()),
                "regulation_id": regulation_id,
                "policy_id": policy_id,
                "entity_type": entity_type,
                "total_requirements": 0,
                "applicable_requirements": 0,
                "covered_count": 0,
                "partial_count": 0,
                "missing_count": 0,
                "overall_coverage_score": 0.0,
                "matches": [],
                "user_id": user_id,
                "organization": organization,
            }

        # Prepare policy summaries
        policy_summaries = self._prepare_policy_summaries(policy_clauses)

        matches = []
        total = len(requirements)
        batch_size = 3

        for i in range(0, total, batch_size):
            batch = requirements[i:i + batch_size]

            if progress_callback:
                try:
                    pct = int((i / total) * 90)
                    await progress_callback("mapping", pct, f"Mapping requirement {i+1} of {total}...", {})
                except Exception:
                    pass

            batch_results = await asyncio.gather(*[
                self._match_single_requirement(req, policy_clauses, policy_summaries)
                for req in batch
            ], return_exceptions=True)

            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Requirement mapping failed: {result}")
                    matches.append(self._create_fallback_match(batch[j]))
                else:
                    matches.append(result)

            if i + batch_size < total:
                await asyncio.sleep(0.5)

        # Calculate stats
        covered = len([m for m in matches if m.get("gap_type") in ["compliant", "exceeds"]])
        partial = len([m for m in matches if m.get("gap_type") in ["partial", "weak"]])
        missing = len([m for m in matches if m.get("gap_type") in ["missing", "conflicting"]])

        total_score = sum(m.get("coverage_score", 0) for m in matches)
        overall_score = (total_score / len(matches) * 100) if matches else 0

        result = {
            "id": str(uuid.uuid4()),
            "regulation_id": regulation_id,
            "policy_id": policy_id,
            "entity_type": entity_type,
            "total_requirements": len(requirements),
            "applicable_requirements": len(requirements),
            "covered_count": covered,
            "partial_count": partial,
            "missing_count": missing,
            "overall_coverage_score": round(overall_score, 1),
            "matches": matches,
            "user_id": user_id,
            "organization": organization,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store in MongoDB
        try:
            await self.db.requirement_maps.insert_one(dict(result))
        except Exception as e:
            logger.error(f"Failed to store requirement map: {e}")

        result.pop("_id", None)
        return result

    async def _match_single_requirement(
        self,
        requirement: Dict,
        policy_clauses: List[Dict[str, Any]],
        policy_summaries: str
    ) -> Dict[str, Any]:
        """Match a single requirement against policy clauses."""
        if not self.client:
            return self._create_fallback_match(requirement)

        req_id = requirement.get("requirement_id", "")
        title = requirement.get("title", "")
        description = requirement.get("description", "")
        indicators = requirement.get("compliance_indicators", [])
        criticality = requirement.get("criticality", "medium")

        indicators_str = "\n".join(f"  - {ind}" for ind in indicators)

        prompt = f"""You are a compliance assessor. Given a regulatory REQUIREMENT and POLICY CLAUSE CANDIDATES, determine coverage.

REQUIREMENT:
- ID: {req_id}
- Title: {title}
- Description: {description}
- Compliance Indicators:
{indicators_str}
- Criticality: {criticality}

POLICY CLAUSE CANDIDATES:
{policy_summaries[:6000]}

For EACH compliance indicator, determine: covered, partial, or missing.
Then provide overall assessment.

Return JSON only:
{{
  "matched_clause_indices": [1, 5],
  "primary_match_index": 5,
  "indicator_coverage": [
    {{"indicator": "...", "status": "covered", "source_index": 5, "source_text": "..."}}
  ],
  "gap_type": "compliant|partial|weak|missing",
  "severity": "Critical|High|Medium|Low",
  "confidence": 0.85,
  "missing_elements": [],
  "weak_elements": []
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            assessment = json.loads(text)

            # Map matched indices to clause IDs
            matched_indices = assessment.get("matched_clause_indices", [])
            matched_clause_ids = []
            for idx in matched_indices:
                if 1 <= idx <= len(policy_clauses):
                    matched_clause_ids.append(policy_clauses[idx - 1].get("clause_id", ""))

            primary_idx = assessment.get("primary_match_index")
            primary_clause_id = None
            if primary_idx and 1 <= primary_idx <= len(policy_clauses):
                primary_clause_id = policy_clauses[primary_idx - 1].get("clause_id", "")

            gap_type = assessment.get("gap_type", "missing")
            coverage_map = {"compliant": 1.0, "exceeds": 1.0, "partial": 0.6, "weak": 0.4, "missing": 0.0, "conflicting": 0.0}
            coverage_score = coverage_map.get(gap_type, 0.0)

            return {
                "requirement_id": req_id,
                "requirement_title": title,
                "matched_policy_clause_ids": matched_clause_ids,
                "primary_match_clause_id": primary_clause_id,
                "coverage_score": coverage_score,
                "indicator_coverage": assessment.get("indicator_coverage", []),
                "gap_type": gap_type,
                "severity": assessment.get("severity", "Medium"),
                "confidence": assessment.get("confidence", 0.5),
                "missing_elements": assessment.get("missing_elements", []),
                "weak_elements": assessment.get("weak_elements", []),
            }
        except Exception as e:
            logger.error(f"LLM requirement mapping failed for {req_id}: {e}")
            return self._create_fallback_match(requirement)

    def _prepare_policy_summaries(self, policy_clauses: List[Dict[str, Any]]) -> str:
        """Prepare policy clause summaries for LLM context."""
        summaries = []
        for i, p in enumerate(policy_clauses[:50]):  # Limit to 50 clauses
            title = p.get('title') or 'Untitled'
            text = (p.get('original_text') or p.get('text') or '')[:300]
            summary = (p.get('semantic_summary') or '')[:150]
            category = p.get('subject_category') or 'general'
            summaries.append(f"[{i+1}] {title} (category: {category})\n    {summary or text[:150]}")
        return "\n".join(summaries)

    def _create_fallback_match(self, requirement: Dict) -> Dict[str, Any]:
        """Create a fallback match when LLM fails."""
        return {
            "requirement_id": requirement.get("requirement_id", ""),
            "requirement_title": requirement.get("title", ""),
            "matched_policy_clause_ids": [],
            "primary_match_clause_id": None,
            "coverage_score": 0.0,
            "indicator_coverage": [],
            "gap_type": "missing",
            "severity": "High" if requirement.get("criticality") == "high" else "Medium",
            "confidence": 0.0,
            "missing_elements": requirement.get("compliance_indicators", []),
            "weak_elements": [],
        }

    # =========================================================================
    # PHASE 3: INCREMENTAL UPDATES
    # =========================================================================

    async def diff_requirements(
        self,
        regulation_id: str,
        new_requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare new requirements against existing to find changes."""
        existing = await self.get_requirements_for_regulation(regulation_id)
        existing_by_id = {r["requirement_id"]: r for r in existing}
        new_by_id = {r.get("requirement_id", ""): r for r in new_requirements if r.get("requirement_id")}

        added = [r for rid, r in new_by_id.items() if rid not in existing_by_id]
        removed = [rid for rid in existing_by_id if rid not in new_by_id]
        modified = []
        unchanged = 0

        for rid, new_req in new_by_id.items():
            if rid in existing_by_id:
                old = existing_by_id[rid]
                if new_req.get("description") != old.get("description") or \
                   new_req.get("compliance_indicators") != old.get("compliance_indicators"):
                    modified.append(new_req)
                else:
                    unchanged += 1

        return {
            "added": added,
            "modified": modified,
            "removed": removed,
            "unchanged": unchanged,
        }

    async def apply_diff(self, regulation_id: str, diff: Dict[str, Any]) -> Dict[str, int]:
        """Apply a requirement diff."""
        counts = {"added": 0, "modified": 0, "removed": 0}
        now = datetime.now(timezone.utc).isoformat()

        for req in diff.get("added", []):
            req["regulation_id"] = regulation_id
            req["status"] = "active"
            req["created_at"] = now
            req["updated_at"] = now
            req["id"] = str(uuid.uuid4())
            await self.db.requirements.insert_one(req)
            counts["added"] += 1

        for req in diff.get("modified", []):
            req["updated_at"] = now
            req["version"] = req.get("version", 1) + 1
            await self.db.requirements.update_one(
                {"requirement_id": req["requirement_id"], "regulation_id": regulation_id},
                {"$set": req}
            )
            counts["modified"] += 1

        for rid in diff.get("removed", []):
            await self.db.requirements.update_one(
                {"requirement_id": rid, "regulation_id": regulation_id},
                {"$set": {"status": "superseded", "updated_at": now}}
            )
            counts["removed"] += 1

        return counts
