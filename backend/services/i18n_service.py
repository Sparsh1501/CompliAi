"""
Internationalization (i18n) Service for CompliAI (Task #20)

Provides multilingual support for English and Hindi:
- UI label translations
- Compliance term glossary in both languages
- Dynamic translation of compliance status labels
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Translation dictionaries
TRANSLATIONS = {
    "en": {
        # Navigation
        "nav.dashboard": "Dashboard",
        "nav.policies": "Policies",
        "nav.regulations": "Regulations",
        "nav.gap_analysis": "Gap Analysis",
        "nav.compliance": "Compliance Dashboard",
        "nav.tasks": "Tasks",
        "nav.evidence": "Evidence",
        "nav.audit": "Audit",
        "nav.settings": "Settings",

        # Compliance statuses
        "status.compliant": "Compliant",
        "status.non_compliant": "Non-Compliant",
        "status.partial": "Partially Compliant",
        "status.needs_evidence": "Needs Evidence",
        "status.missing": "Missing",
        "status.weak": "Weak",
        "status.exceeds": "Exceeds Requirements",

        # Severity
        "severity.critical": "Critical",
        "severity.high": "High",
        "severity.medium": "Medium",
        "severity.low": "Low",

        # Gap analysis
        "gap.title": "Gap Analysis Report",
        "gap.executive_summary": "Executive Summary",
        "gap.findings": "Detailed Findings",
        "gap.citation_index": "RBI Citation Index",
        "gap.recommended_action": "Recommended Action",
        "gap.missing_elements": "Missing Elements",
        "gap.regulation_text": "Regulation Requirement",
        "gap.policy_text": "Policy Coverage",

        # Dashboard
        "dashboard.overall_score": "Overall Compliance Score",
        "dashboard.compliance_trend": "Compliance Trend",
        "dashboard.deadlines": "Upcoming Deadlines",
        "dashboard.category_scores": "Category Compliance Scores",

        # Policy
        "policy.draft": "Draft",
        "policy.review": "Under Review",
        "policy.approved": "Approved",
        "policy.published": "Published",
        "policy.rejected": "Rejected",

        # Common
        "common.save": "Save",
        "common.cancel": "Cancel",
        "common.delete": "Delete",
        "common.export": "Export",
        "common.download": "Download",
        "common.upload": "Upload",
        "common.search": "Search",
        "common.filter": "Filter",
        "common.loading": "Loading...",
        "common.no_data": "No data available",
    },
    "hi": {
        # Navigation
        "nav.dashboard": "\u0921\u0948\u0936\u092c\u094b\u0930\u094d\u0921",
        "nav.policies": "\u0928\u0940\u0924\u093f\u092f\u093e\u0901",
        "nav.regulations": "\u0935\u093f\u0928\u093f\u092f\u092e",
        "nav.gap_analysis": "\u0917\u0948\u092a \u0935\u093f\u0936\u094d\u0932\u0947\u0937\u0923",
        "nav.compliance": "\u0905\u0928\u0941\u092a\u093e\u0932\u0928 \u0921\u0948\u0936\u092c\u094b\u0930\u094d\u0921",
        "nav.tasks": "\u0915\u093e\u0930\u094d\u092f",
        "nav.evidence": "\u0938\u093e\u0915\u094d\u0937\u094d\u092f",
        "nav.audit": "\u0932\u0947\u0916\u093e \u092a\u0930\u0940\u0915\u094d\u0937\u093e",
        "nav.settings": "\u0938\u0947\u091f\u093f\u0902\u0917\u094d\u0938",

        # Compliance statuses
        "status.compliant": "\u0905\u0928\u0941\u092a\u093e\u0932\u0928 \u092e\u0947\u0902",
        "status.non_compliant": "\u0917\u0948\u0930-\u0905\u0928\u0941\u092a\u093e\u0932\u0928",
        "status.partial": "\u0906\u0902\u0936\u093f\u0915 \u0905\u0928\u0941\u092a\u093e\u0932\u0928",
        "status.needs_evidence": "\u0938\u093e\u0915\u094d\u0937\u094d\u092f \u0906\u0935\u0936\u094d\u092f\u0915",
        "status.missing": "\u0905\u0928\u0941\u092a\u0938\u094d\u0925\u093f\u0924",
        "status.weak": "\u0915\u092e\u091c\u094b\u0930",
        "status.exceeds": "\u0906\u0935\u0936\u094d\u092f\u0915\u0924\u093e\u0913\u0902 \u0938\u0947 \u0905\u0927\u093f\u0915",

        # Severity
        "severity.critical": "\u0917\u0902\u092d\u0940\u0930",
        "severity.high": "\u0909\u091a\u094d\u091a",
        "severity.medium": "\u092e\u0927\u094d\u092f\u092e",
        "severity.low": "\u0928\u093f\u092e\u094d\u0928",

        # Gap analysis
        "gap.title": "\u0917\u0948\u092a \u0935\u093f\u0936\u094d\u0932\u0947\u0937\u0923 \u0930\u093f\u092a\u094b\u0930\u094d\u091f",
        "gap.executive_summary": "\u0915\u093e\u0930\u094d\u092f\u0915\u093e\u0930\u0940 \u0938\u093e\u0930\u093e\u0902\u0936",
        "gap.findings": "\u0935\u093f\u0938\u094d\u0924\u0943\u0924 \u0928\u093f\u0937\u094d\u0915\u0930\u094d\u0937",
        "gap.citation_index": "RBI \u0909\u0926\u094d\u0927\u0930\u0923 \u0938\u0942\u091a\u0940",
        "gap.recommended_action": "\u0905\u0928\u0941\u0936\u0902\u0938\u093f\u0924 \u0915\u093e\u0930\u094d\u0930\u0935\u093e\u0908",
        "gap.missing_elements": "\u0905\u0928\u0941\u092a\u0938\u094d\u0925\u093f\u0924 \u0924\u0924\u094d\u0935",
        "gap.regulation_text": "\u0935\u093f\u0928\u093f\u092f\u093e\u092e\u0915 \u0906\u0935\u0936\u094d\u092f\u0915\u0924\u093e",
        "gap.policy_text": "\u0928\u0940\u0924\u093f \u0915\u0935\u0930\u0947\u091c",

        # Dashboard
        "dashboard.overall_score": "\u0938\u092e\u0917\u094d\u0930 \u0905\u0928\u0941\u092a\u093e\u0932\u0928 \u0938\u094d\u0915\u094b\u0930",
        "dashboard.compliance_trend": "\u0905\u0928\u0941\u092a\u093e\u0932\u0928 \u0930\u0941\u091d\u093e\u0928",
        "dashboard.deadlines": "\u0906\u0917\u093e\u092e\u0940 \u0938\u092e\u092f \u0938\u0940\u092e\u093e",
        "dashboard.category_scores": "\u0936\u094d\u0930\u0947\u0923\u0940 \u0905\u0928\u0941\u092a\u093e\u0932\u0928 \u0938\u094d\u0915\u094b\u0930",

        # Policy
        "policy.draft": "\u092e\u0938\u094c\u0926\u093e",
        "policy.review": "\u0938\u092e\u0940\u0915\u094d\u0937\u093e\u0927\u0940\u0928",
        "policy.approved": "\u0905\u0928\u0941\u092e\u094b\u0926\u093f\u0924",
        "policy.published": "\u092a\u094d\u0930\u0915\u093e\u0936\u093f\u0924",
        "policy.rejected": "\u0905\u0938\u094d\u0935\u0940\u0915\u0943\u0924",

        # Common
        "common.save": "\u0938\u0939\u0947\u091c\u0947\u0902",
        "common.cancel": "\u0930\u0926\u094d\u0926 \u0915\u0930\u0947\u0902",
        "common.delete": "\u0939\u091f\u093e\u090f\u0902",
        "common.export": "\u0928\u093f\u0930\u094d\u092f\u093e\u0924 \u0915\u0930\u0947\u0902",
        "common.download": "\u0921\u093e\u0909\u0928\u0932\u094b\u0921",
        "common.upload": "\u0905\u092a\u0932\u094b\u0921",
        "common.search": "\u0916\u094b\u091c\u0947\u0902",
        "common.filter": "\u092b\u093f\u0932\u094d\u091f\u0930",
        "common.loading": "\u0932\u094b\u0921 \u0939\u094b \u0930\u0939\u093e \u0939\u0948...",
        "common.no_data": "\u0915\u094b\u0908 \u0921\u0947\u091f\u093e \u0909\u092a\u0932\u092c\u094d\u0927 \u0928\u0939\u0940\u0902",
    }
}

# Compliance term glossary
GLOSSARY = {
    "en": {
        "PA": "Payment Aggregator",
        "PG": "Payment Gateway",
        "PA-P": "Payment Aggregator - Physical (POS)",
        "CCO": "Chief Compliance Officer",
        "KYC": "Know Your Customer",
        "AML": "Anti-Money Laundering",
        "CFT": "Combating the Financing of Terrorism",
        "PMLA": "Prevention of Money Laundering Act",
        "FIU-IND": "Financial Intelligence Unit - India",
        "CERT-In": "Indian Computer Emergency Response Team",
        "PCI-DSS": "Payment Card Industry Data Security Standard",
        "NBFC": "Non-Banking Financial Company",
        "MDR": "Merchant Discount Rate",
        "UPI": "Unified Payments Interface",
    },
    "hi": {
        "PA": "\u092d\u0941\u0917\u0924\u093e\u0928 \u090f\u0917\u094d\u0930\u0940\u0917\u0947\u091f\u0930",
        "PG": "\u092d\u0941\u0917\u0924\u093e\u0928 \u0917\u0947\u091f\u0935\u0947",
        "PA-P": "\u092d\u0941\u0917\u0924\u093e\u0928 \u090f\u0917\u094d\u0930\u0940\u0917\u0947\u091f\u0930 - \u092d\u094c\u0924\u093f\u0915 (POS)",
        "CCO": "\u092e\u0941\u0916\u094d\u092f \u0905\u0928\u0941\u092a\u093e\u0932\u0928 \u0905\u0927\u093f\u0915\u093e\u0930\u0940",
        "KYC": "\u0905\u092a\u0928\u0947 \u0917\u094d\u0930\u093e\u0939\u0915 \u0915\u094b \u091c\u093e\u0928\u0947\u0902",
        "AML": "\u0927\u0928 \u0936\u094b\u0927\u0928 \u0928\u093f\u0930\u094b\u0927\u0915",
        "PMLA": "\u0927\u0928 \u0936\u094b\u0927\u0928 \u0928\u093f\u0935\u093e\u0930\u0923 \u0905\u0927\u093f\u0928\u093f\u092f\u092e",
    }
}


class I18nService:
    """Provides translation and glossary lookup for multilingual support."""

    def __init__(self, db=None):
        self.db = db
        self.supported_languages = ["en", "hi"]
        self.default_language = "en"

    def translate(self, key: str, language: str = "en") -> str:
        """Get translation for a key in the specified language."""
        lang = language if language in self.supported_languages else self.default_language
        translations = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
        return translations.get(key, TRANSLATIONS["en"].get(key, key))

    def get_all_translations(self, language: str = "en") -> Dict[str, str]:
        """Get all translations for a language."""
        lang = language if language in self.supported_languages else self.default_language
        return TRANSLATIONS.get(lang, TRANSLATIONS["en"])

    def get_glossary(self, language: str = "en") -> Dict[str, str]:
        """Get compliance glossary in the specified language."""
        lang = language if language in self.supported_languages else self.default_language
        return GLOSSARY.get(lang, GLOSSARY["en"])

    def get_supported_languages(self):
        """Return list of supported languages."""
        return [
            {"code": "en", "name": "English", "native_name": "English"},
            {"code": "hi", "name": "Hindi", "native_name": "\u0939\u093f\u0928\u094d\u0926\u0940"},
        ]

    async def get_user_language(self, user_id: str) -> str:
        """Get user's preferred language."""
        if not self.db:
            return self.default_language
        user = await self.db.users.find_one({"id": user_id}, {"language": 1, "_id": 0})
        return (user or {}).get("language", self.default_language)

    async def set_user_language(self, user_id: str, language: str) -> Dict[str, Any]:
        """Set user's preferred language."""
        if language not in self.supported_languages:
            return {"error": f"Unsupported language: {language}"}
        await self.db.users.update_one({"id": user_id}, {"$set": {"language": language}})
        return {"language": language, "status": "updated"}
