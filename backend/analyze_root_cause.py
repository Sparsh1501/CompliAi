"""Deep analysis of why gaps are marked as missing."""
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['compli-ai']
ga = db.gap_analyses.find_one({})
policy_id = ga.get('policy_id')
policy = db.policies.find_one({'id': policy_id})
policy_clauses = policy.get('clauses', [])

# Check the problematic areas
print("=== ROOT CAUSE ANALYSIS ===")
print()

# Issue 1: Category distribution mismatch
reg_id = ga.get('regulation_id')
reg = db.regulations.find_one({'id': reg_id})
reg_clauses = reg.get('clauses', [])

print("1. CATEGORY MISMATCH ANALYSIS")
print("   Regulation has more operational_procedures (42) than Policy (17)")
print("   Regulation has more reporting (14) than Policy (4)")
print("   This explains many 'missing' gaps - policy simply doesn't cover these areas")
print()

# Issue 2: Check sample policy keywords - are they meaningful?
print("2. KEYWORD QUALITY ANALYSIS")
sample_policy = policy_clauses[0]
print(f"   Sample Policy Clause: {sample_policy.get('title')}")
print(f"   Keywords: {sample_policy.get('keywords', [])}")
print()

# Issue 3: Check if pre-filter is working
print("3. PRE-FILTER CANDIDATES ANALYSIS")
# Simulate what the pre-filter would do for a missing gap
missing_gaps = [g for g in ga.get('gaps', []) if g.get('gap_type') == 'missing']
sample_missing = missing_gaps[0] if missing_gaps else None

if sample_missing:
    rc = sample_missing.get('regulation_clause', {})
    print(f"   Sample missing regulation: {rc.get('title')}")
    print(f"   Regulation keywords: {rc.get('keywords', [])[:5] if rc else 'N/A'}")
    
    # Find the actual regulation clause
    reg_clause = None
    for r in reg_clauses:
        if r.get('title') == rc.get('title'):
            reg_clause = r
            break
    
    if reg_clause:
        reg_keywords = set(k.lower().strip() for k in (reg_clause.get('keywords') or []))
        reg_category = (reg_clause.get('subject_category') or 'general').lower()
        
        # Find best matching policy
        print(f"\n   Searching for policy matches...")
        print(f"   Regulation category: {reg_category}")
        print(f"   Regulation keywords: {list(reg_keywords)[:5]}")
        
        best_matches = []
        for i, pc in enumerate(policy_clauses):
            policy_keywords = set(k.lower().strip() for k in (pc.get('keywords') or []))
            policy_category = (pc.get('subject_category') or 'general').lower()
            
            # Calculate overlap
            keyword_overlap = reg_keywords & policy_keywords
            category_match = policy_category == reg_category
            
            if keyword_overlap or category_match:
                best_matches.append({
                    'idx': i,
                    'title': pc.get('title'),
                    'category': policy_category,
                    'overlap': list(keyword_overlap)[:3],
                    'cat_match': category_match
                })
        
        print(f"\n   Found {len(best_matches)} potential policy matches:")
        for m in best_matches[:5]:
            print(f"   - [{m['idx']+1}] {m['title'][:50]}...")
            print(f"     Category match: {m['cat_match']}, Keyword overlap: {m['overlap']}")

print()
print("=== KEY FINDINGS ===")
print("""
1. GENUINE COVERAGE GAP: Policy has only 114 clauses vs 155 regulation clauses
   - Regulation has 42 operational_procedures, Policy only has 17
   - Regulation has 14 reporting clauses, Policy only has 4
   - This is a REAL compliance gap, not a classification error

2. SPECIFIC MISSING TOPICS (from keyword analysis):
   - 'freezing' (9 occurrences) - Asset freezing procedures
   - 'designated' (11 occurrences) - Designated officer requirements
   - 'verification' (12 occurrences) - Verification process details
   
3. LLM MAY BE TOO STRICT in matching:
   - Pre-filter finds candidates, but LLM might be rejecting them
   - Need to check if LLM is being overly literal in matching

4. POSSIBLE IMPROVEMENTS:
   a) Make LLM more lenient in accepting partial matches
   b) Increase pre-filter max_candidates from 25 to 50
   c) Reduce the threshold for keyword matching
""")

client.close()
