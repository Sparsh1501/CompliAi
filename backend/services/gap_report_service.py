"""
Gap Analysis Report Service for CompliAI (Task #15)

Generates structured gap analysis reports with:
- RBI paragraph citations
- Clause-level comparisons
- Remediation recommendations
- Executive summary and detailed findings
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class GapReportService:
    """Generates detailed gap analysis reports with RBI para citations."""

    def __init__(self, db=None, gap_scoring_service=None):
        self.db = db
        self.gap_scoring_service = gap_scoring_service

    async def generate_report(self, analysis_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive gap analysis report from a stored analysis.

        Returns structured report with executive summary, detailed findings,
        and RBI citation cross-references.
        """
        analysis = await self.db.gap_analyses.find_one({"id": analysis_id}, {"_id": 0})
        if not analysis:
            return {"error": "Analysis not found"}

        gaps = analysis.get("gaps", [])

        # Get scoring
        scoring = {}
        if self.gap_scoring_service:
            scoring = self.gap_scoring_service.generate_compliance_summary(
                gaps,
                policy_title=analysis.get("policy_title", ""),
                regulation_title=analysis.get("regulation_title", ""),
            )

        # Build findings
        findings = []
        for i, gap in enumerate(gaps):
            reg_clause = gap.get("regulation_clause", {})
            pol_clause = gap.get("policy_clause", {})

            rbi_citation = ""
            if reg_clause:
                section = reg_clause.get("section") or reg_clause.get("title", "")
                rbi_citation = f"RBI Master Direction, {section}"
                clause_ref = reg_clause.get("clause_id") or reg_clause.get("id", "")
                if clause_ref:
                    rbi_citation += f" (Clause {clause_ref})"

            finding = {
                "finding_number": i + 1,
                "gap_type": gap.get("gap_type", "missing"),
                "severity": gap.get("severity", "Medium"),
                "criticality": gap.get("metadata", {}).get("criticality", "medium"),
                "description": gap.get("description", ""),
                "rbi_citation": rbi_citation,
                "regulation_text": (reg_clause.get("text") or "")[:800],
                "regulation_section": reg_clause.get("section") or reg_clause.get("title", ""),
                "policy_text": (pol_clause.get("text") or "")[:800],
                "policy_section": pol_clause.get("section") or pol_clause.get("title", ""),
                "suggested_fix": gap.get("suggested_fix", ""),
                "missing_elements": gap.get("metadata", {}).get("missing_elements", []),
                "weak_elements": gap.get("metadata", {}).get("weak_elements", []),
                "evidence_map": gap.get("evidence_map", []),
                "subject_category": gap.get("metadata", {}).get("subject_category", "general"),
                "assigned_department": gap.get("metadata", {}).get("assigned_department", "Compliance"),
            }
            findings.append(finding)

        # Sort findings by severity
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        findings.sort(key=lambda f: severity_order.get(f["severity"], 9))

        # Build citation index
        citation_index = {}
        for f in findings:
            if f["rbi_citation"]:
                if f["rbi_citation"] not in citation_index:
                    citation_index[f["rbi_citation"]] = []
                citation_index[f["rbi_citation"]].append(f["finding_number"])

        # Executive summary
        total = len(gaps)
        compliant = len([g for g in gaps if g.get("gap_type") in ("compliant", "exceeds")])
        critical_gaps = len([g for g in gaps if g.get("severity") == "Critical" and g.get("gap_type") not in ("compliant", "exceeds")])
        high_gaps = len([g for g in gaps if g.get("severity") == "High" and g.get("gap_type") not in ("compliant", "exceeds")])

        executive_summary = {
            "total_requirements_assessed": total,
            "compliant_count": compliant,
            "compliance_percentage": round((compliant / total) * 100, 1) if total else 0,
            "critical_gaps": critical_gaps,
            "high_severity_gaps": high_gaps,
            "overall_status": scoring.get("status", "unknown"),
            "weighted_score": scoring.get("overall_score", 0),
            "narrative": self._generate_narrative(
                total, compliant, critical_gaps, high_gaps,
                analysis.get("policy_title", ""),
                analysis.get("regulation_title", ""),
            ),
        }

        # Category breakdown
        category_findings = {}
        for f in findings:
            cat = f["subject_category"]
            if cat not in category_findings:
                category_findings[cat] = {"findings": [], "count": 0}
            category_findings[cat]["findings"].append(f["finding_number"])
            category_findings[cat]["count"] += 1

        report = {
            "report_id": f"report-{analysis_id}",
            "analysis_id": analysis_id,
            "policy_id": analysis.get("policy_id"),
            "regulation_id": analysis.get("regulation_id"),
            "policy_title": analysis.get("policy_title", ""),
            "regulation_title": analysis.get("regulation_title", ""),
            "organization": analysis.get("organization", ""),
            "executive_summary": executive_summary,
            "scoring": scoring,
            "findings": findings,
            "citation_index": citation_index,
            "category_breakdown": category_findings,
            "total_findings": len(findings),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store report
        await self.db.gap_reports.insert_one({**report, "_id": None})
        # Remove _id for response
        report.pop("_id", None)

        return report

    async def get_report(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Get a previously generated report."""
        return await self.db.gap_reports.find_one(
            {"analysis_id": analysis_id}, {"_id": 0}
        )

    async def list_reports(self, organization: str) -> List[Dict[str, Any]]:
        """List all gap analysis reports for an organization."""
        cursor = self.db.gap_reports.find(
            {"organization": organization},
            {"_id": 0, "findings": 0, "citation_index": 0}
        ).sort("generated_at", -1).limit(50)
        return await cursor.to_list(length=50)

    def _generate_narrative(
        self, total: int, compliant: int, critical: int, high: int,
        policy_title: str, regulation_title: str
    ) -> str:
        """Generate a human-readable executive summary narrative."""
        pct = round((compliant / total) * 100, 1) if total else 0
        non_compliant = total - compliant

        narrative = f"This gap analysis assessed {total} regulatory requirements "
        if regulation_title:
            narrative += f"from {regulation_title} "
        if policy_title:
            narrative += f"against {policy_title}. "
        else:
            narrative += "against the organization's policies. "

        narrative += f"The overall compliance rate is {pct}%, with {compliant} requirements met and {non_compliant} gaps identified. "

        if critical > 0:
            narrative += f"There are {critical} critical gaps requiring immediate attention. "
        if high > 0:
            narrative += f"{high} high-severity gaps require action within 30 days. "

        if pct >= 80:
            narrative += "The organization demonstrates a strong compliance posture with targeted improvements needed."
        elif pct >= 60:
            narrative += "Significant compliance gaps exist that require a structured remediation plan."
        else:
            narrative += "The compliance posture requires urgent attention. A comprehensive remediation program is recommended."

        return narrative
