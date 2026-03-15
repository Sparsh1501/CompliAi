"""
CompliAI Backend Configuration Module

This module provides centralized configuration for:
- Compliance context and prompts
- Domain taxonomies
- LLM settings
"""

from config.compliance_context import (
    ComplianceContext,
    CompliancePrompts,
    SUBJECT_CATEGORIES,
    OBLIGATION_PATTERNS,
    ENTITY_TYPES,
    DocumentType,
    RequirementType,
    CriticalityLevel,
    Regulator,
    SubjectCategory,
    get_default_context,
    get_all_subject_categories,
    get_all_requirement_types,
    get_all_regulators,
    EXTRACTION_OUTPUT_SCHEMA,
    ENRICHMENT_OUTPUT_SCHEMA,
    GAP_ANALYSIS_OUTPUT_SCHEMA,
)

__all__ = [
    "ComplianceContext",
    "CompliancePrompts",
    "SUBJECT_CATEGORIES",
    "OBLIGATION_PATTERNS", 
    "ENTITY_TYPES",
    "DocumentType",
    "RequirementType",
    "CriticalityLevel",
    "Regulator",
    "SubjectCategory",
    "get_default_context",
    "get_all_subject_categories",
    "get_all_requirement_types",
    "get_all_regulators",
    "EXTRACTION_OUTPUT_SCHEMA",
    "ENRICHMENT_OUTPUT_SCHEMA",
    "GAP_ANALYSIS_OUTPUT_SCHEMA",
]
