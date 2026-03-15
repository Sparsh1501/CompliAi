"""Test the new Semantic Gap Analysis Service"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from services.semantic_gap_analysis_service import SemanticGapAnalysisService

async def test_semantic_gap_analysis():
    """Test the semantic gap analysis with real data."""
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['compli-ai']
    
    # Get policy and regulation
    policy = await db.policies.find_one({})
    regulation = await db.regulations.find_one({})
    
    if not policy or not regulation:
        print("ERROR: No policy or regulation found in database")
        return
    
    policy_clauses = policy.get('clauses', [])
    regulation_clauses = regulation.get('clauses', [])
    
    print(f"\n=== TEST DATA ===")
    print(f"Policy: {policy.get('title')}")
    print(f"Policy Clauses: {len(policy_clauses)}")
    print(f"Regulation: {regulation.get('title')}")
    print(f"Regulation Clauses: {len(regulation_clauses)}")
    print()
    
    # Test with first 5 regulation clauses only (faster test)
    service = SemanticGapAnalysisService(db=db)
    
    print("Running SEMANTIC gap analysis on first 5 regulation clauses...")
    print("(This uses LLM-First matching approach)")
    print()
    
    try:
        report = await service.analyze(
            policy_clauses=policy_clauses,
            regulation_clauses=regulation_clauses[:5],  # Just first 5 for quick test
            policy_id=policy.get('id'),
            policy_title=policy.get('title', 'Test Policy'),
            regulation_id=regulation.get('id'),
            regulation_title=regulation.get('title', 'Test Regulation')
        )
        
        print()
        print("=" * 60)
        print("=== SEMANTIC GAP ANALYSIS RESULTS ===")
        print("=" * 60)
        print(f"Compliance Score: {report.compliance_score}%")
        print(f"Fully Compliant: {report.fully_compliant_count}")
        print(f"Partially Compliant: {report.partially_compliant_count}")
        print(f"Non-Compliant: {report.non_compliant_count}")
        print()
        print(f"Critical Gaps: {report.critical_gaps}")
        print(f"High Gaps: {report.high_gaps}")
        print(f"Medium Gaps: {report.medium_gaps}")
        print(f"Low Gaps: {report.low_gaps}")
        print()
        
        print("=" * 60)
        print("=== INDIVIDUAL RESULTS ===")
        print("=" * 60)
        
        for i, result in enumerate(report.gap_results, 1):
            print(f"\n[{i}] Regulation: {result.regulation_title[:60]}...")
            print(f"    Gap Type: {result.gap_type.value}")
            print(f"    Severity: {result.severity.value}")
            print(f"    Confidence: {result.confidence_score:.2f}")
            print(f"    Matched Policies: {len(result.matched_policy_clauses)}")
            if result.primary_policy_match:
                print(f"    Primary Match: {result.primary_policy_match.get('title', 'N/A')[:50]}")
            if result.gap_description:
                print(f"    Description: {result.gap_description[:100]}...")
            if result.covered_elements:
                print(f"    Covered: {result.covered_elements[:2]}")
            if result.missing_elements:
                print(f"    Missing: {result.missing_elements[:2]}")
        
        print()
        print("=" * 60)
        print("=== EXECUTIVE SUMMARY ===")
        print("=" * 60)
        print(report.executive_summary[:500])
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_semantic_gap_analysis())
