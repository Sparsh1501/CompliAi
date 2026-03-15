#!/usr/bin/env python3
"""
Test the new keyword-based pre-filtering logic.
This demonstrates how the pre-filter reduces 114 policies to ~25 relevant candidates.
"""

from pymongo import MongoClient
from services.semantic_gap_analysis_service import SemanticGapAnalysisService

def main():
    client = MongoClient('mongodb://localhost:27017')
    db = client['compli-ai']
    
    # Get the data
    ga = db.gap_analyses.find_one()
    policy = db.policies.find_one({'id': ga['policy_id']})
    regulation = db.regulations.find_one({'id': ga['regulation_id']})
    
    policy_clauses = policy.get('clauses', [])
    reg_clauses = regulation.get('clauses', [])
    
    print("=" * 70)
    print("TESTING PRE-FILTER LOGIC")
    print("=" * 70)
    print(f"Policy: {policy['title'][:60]}...")
    print(f"Total Policy Clauses: {len(policy_clauses)}")
    print(f"Total Regulation Clauses: {len(reg_clauses)}")
    
    # Create service instance
    service = SemanticGapAnalysisService(db=db)
    
    # Test pre-filtering on a few regulation clauses
    print("\n" + "=" * 70)
    print("PRE-FILTERING SAMPLES")
    print("=" * 70)
    
    test_cases = [
        # Find regulation clauses with different characteristics
        next((c for c in reg_clauses if 'Digital KYC' in c.get('title', '')), reg_clauses[0]),
        next((c for c in reg_clauses if 'customer' in c.get('title', '').lower()), reg_clauses[1]),
        next((c for c in reg_clauses if c.get('subject_category') == 'aml_cft'), reg_clauses[2]),
        next((c for c in reg_clauses if c.get('subject_category') == 'governance'), reg_clauses[3]),
        next((c for c in reg_clauses if 'verification' in c.get('title', '').lower()), reg_clauses[4]),
    ]
    
    for i, reg_clause in enumerate(test_cases[:5]):
        print(f"\n--- Test Case {i+1} ---")
        print(f"Regulation: {reg_clause.get('title', 'N/A')}")
        print(f"Category: {reg_clause.get('subject_category', 'N/A')}")
        print(f"Keywords: {reg_clause.get('keywords', [])[:5]}")
        
        # Run pre-filter
        filtered, indices = service._prefilter_policy_candidates(
            reg_clause, policy_clauses, max_candidates=15
        )
        
        print(f"\nFiltered: {len(policy_clauses)} → {len(filtered)} candidates")
        
        if filtered:
            print("Top 5 candidates:")
            for j, (pol, idx) in enumerate(zip(filtered[:5], indices[:5])):
                print(f"  [{idx}] {pol.get('title', 'N/A')[:50]}")
                print(f"       Cat: {pol.get('subject_category', 'N/A')}, KW: {pol.get('keywords', [])[:3]}")
    
    # Summary
    print("\n" + "=" * 70)
    print("IMPROVEMENT SUMMARY")
    print("=" * 70)
    print(f"""
BEFORE (old logic):
- Sent ALL {len(policy_clauses)} policy summaries to LLM
- LLM had to search through unrelated policies
- Token limit (8000 chars) truncated the list
- Result: 77.4% marked as "missing" due to no match found

AFTER (new logic with pre-filtering):
- First filter by keywords + category → ~15-25 candidates
- LLM only sees RELEVANT policies
- Better context = better matching
- Expected: Significantly fewer false "missing" gaps

To test the full gap analysis with the new logic:
1. Delete the existing gap analysis from MongoDB
2. Re-run gap analysis from the UI
3. Compare the new compliance score
""")

if __name__ == '__main__':
    main()
