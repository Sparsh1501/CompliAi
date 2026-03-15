#!/usr/bin/env python3
"""
Analyze gap analysis data to understand clause matching issues.

KEY INVESTIGATION:
1. Are clauses being matched based on semantic relevance?
2. Are keywords/categories being used for pre-filtering?
3. Why is compliance score so low (14.6%)?
4. Are 'missing' gaps actually missing or just not semantically matched?
"""

from pymongo import MongoClient
from collections import defaultdict

def compute_keyword_overlap(keywords1, keywords2):
    """Compute overlap between two keyword lists."""
    if not keywords1 or not keywords2:
        return 0, set()
    set1 = set(k.lower().strip() for k in keywords1)
    set2 = set(k.lower().strip() for k in keywords2)
    overlap = set1 & set2
    return len(overlap), overlap

def compute_category_match(cat1, cat2):
    """Check if categories are related."""
    cat1 = (cat1 or 'general').lower()
    cat2 = (cat2 or 'general').lower()
    
    if cat1 == cat2:
        return 1.0
    
    # Define related categories
    related = {
        'kyc_aml': ['customer_due_diligence', 'aml_cft', 'risk_management'],
        'customer_due_diligence': ['kyc_aml', 'aml_cft', 'operational_procedures'],
        'aml_cft': ['kyc_aml', 'customer_due_diligence', 'risk_management', 'reporting'],
        'risk_management': ['kyc_aml', 'aml_cft', 'governance'],
        'governance': ['risk_management', 'operational_procedures'],
        'operational_procedures': ['governance', 'customer_due_diligence'],
        'reporting': ['aml_cft', 'governance'],
    }
    
    if cat2 in related.get(cat1, []) or cat1 in related.get(cat2, []):
        return 0.5
    
    return 0.0

def main():
    client = MongoClient('mongodb://localhost:27017')
    db = client['compli-ai']
    
    # Get gap analysis
    ga = db.gap_analyses.find_one()
    if not ga:
        print("No gap analysis found!")
        return
    
    policy = db.policies.find_one({'id': ga['policy_id']})
    regulation = db.regulations.find_one({'id': ga['regulation_id']})
    
    print("=" * 70)
    print("DEEP GAP ANALYSIS INVESTIGATION")
    print("=" * 70)
    print(f"Policy: {policy['title'][:60]}...")
    print(f"Policy Clauses: {len(policy.get('clauses', []))}")
    print(f"\nRegulation: {regulation['title'][:60]}...")
    print(f"Regulation Clauses: {len(regulation.get('clauses', []))}")
    print(f"\nTotal Gaps: {len(ga.get('gaps', []))}")
    print(f"Compliance Score: {ga.get('compliance_score')}%")
    
    # Gap type breakdown
    gaps = ga.get('gaps', [])
    gap_types = defaultdict(int)
    severities = defaultdict(int)
    for g in gaps:
        gap_types[g.get('gap_type', 'unknown')] += 1
        severities[g.get('severity', 'unknown')] += 1
    
    print(f"\n{'='*70}")
    print("GAP TYPE BREAKDOWN")
    print("=" * 70)
    for gt, count in sorted(gap_types.items(), key=lambda x: -x[1]):
        pct = (count / len(gaps)) * 100
        print(f"  {gt}: {count} ({pct:.1f}%)")
    
    print(f"\nSEVERITY BREAKDOWN")
    for sev, count in sorted(severities.items()):
        print(f"  {sev}: {count}")
    
    # Build policy clause index for lookup
    policy_clauses = {c.get('id', c.get('clause_id', '')): c for c in policy.get('clauses', [])}
    reg_clauses = {c.get('id', c.get('clause_id', '')): c for c in regulation.get('clauses', [])}
    
    print(f"\n{'='*70}")
    print("ANALYZING 'MISSING' GAPS - THE CORE PROBLEM")
    print("=" * 70)
    print(f"Total 'missing' gaps: {gap_types.get('missing', 0)}")
    print("These are regulation clauses where NO policy match was found.\n")
    
    missing_gaps = [g for g in gaps if g.get('gap_type') == 'missing']
    
    # For each missing gap, manually check if there SHOULD be a policy match
    potential_matches = []
    
    for i, g in enumerate(missing_gaps[:10]):
        reg_clause = g.get('regulation_clause', {})
        reg_title = reg_clause.get('title', 'N/A')
        reg_text = (reg_clause.get('text') or reg_clause.get('original_text', ''))[:200]
        reg_keywords = reg_clause.get('keywords', [])
        reg_cat = reg_clause.get('subject_category', 'general')
        
        print(f"\n--- MISSING GAP {i+1} ---")
        print(f"Regulation: {reg_title}")
        print(f"Category: {reg_cat}")
        print(f"Keywords: {reg_keywords[:5] if reg_keywords else 'NONE'}")
        print(f"Text: {reg_text}...")
        
        # Search for potential policy matches
        best_matches = []
        for pid, pcl in policy_clauses.items():
            p_keywords = pcl.get('keywords', [])
            p_cat = pcl.get('subject_category', 'general')
            p_title = pcl.get('title', '')
            
            # Score based on keyword overlap
            kw_count, kw_overlap = compute_keyword_overlap(reg_keywords, p_keywords)
            cat_score = compute_category_match(reg_cat, p_cat)
            
            # Also check title similarity (simple word overlap)
            reg_words = set(reg_title.lower().split())
            p_words = set(p_title.lower().split())
            title_overlap = reg_words & p_words
            
            score = kw_count * 2 + cat_score + len(title_overlap) * 0.5
            
            if score > 0:
                best_matches.append({
                    'policy_title': p_title,
                    'score': score,
                    'keyword_overlap': list(kw_overlap)[:3],
                    'cat_match': cat_score,
                    'title_overlap': list(title_overlap)[:3]
                })
        
        # Sort by score
        best_matches.sort(key=lambda x: -x['score'])
        
        if best_matches:
            print(f"\n  POTENTIAL MATCHES FOUND (but marked as MISSING):")
            for m in best_matches[:3]:
                print(f"    - {m['policy_title'][:50]}")
                print(f"      Score: {m['score']:.1f}, KW: {m['keyword_overlap']}, Cat: {m['cat_match']}, Title: {m['title_overlap']}")
            potential_matches.append({'reg_title': reg_title, 'matches': best_matches[:3]})
        else:
            print(f"  NO POTENTIAL MATCHES (truly missing)")
    
    print(f"\n{'='*70}")
    print("ANALYSIS SUMMARY")
    print("=" * 70)
    
    print(f"\n1. MISSING GAPS ISSUE:")
    print(f"   - {len(missing_gaps)} regulation clauses have NO policy match")
    print(f"   - This accounts for {(len(missing_gaps)/len(gaps))*100:.1f}% of all gaps")
    
    print(f"\n2. POTENTIAL ROOT CAUSES:")
    print(f"   a) LLM semantic matching may be too strict")
    print(f"   b) Policy summaries may not capture all relevant content")
    print(f"   c) Keywords are extracted but NOT used for pre-filtering/matching")
    print(f"   d) Subject categories could help narrow matching scope")
    
    print(f"\n3. RECOMMENDATION:")
    print(f"   Implement KEYWORD-BASED PRE-FILTERING before LLM matching:")
    print(f"   - Filter policies by subject_category first")
    print(f"   - Boost policies with overlapping keywords")
    print(f"   - Pass only relevant subset to LLM for semantic matching")
    
    # Check keyword coverage in the data
    print(f"\n{'='*70}")
    print("KEYWORD COVERAGE IN DATA")
    print("=" * 70)
    
    policy_list = list(policy_clauses.values())
    reg_list = list(reg_clauses.values())
    
    p_with_kw = len([c for c in policy_list if c.get('keywords') and len(c.get('keywords')) > 0])
    r_with_kw = len([c for c in reg_list if c.get('keywords') and len(c.get('keywords')) > 0])
    
    print(f"Policy clauses with keywords: {p_with_kw} of {len(policy_list)}")
    print(f"Regulation clauses with keywords: {r_with_kw} of {len(reg_list)}")
    
    # Sample keywords
    if policy_list:
        sample_p = next((c for c in policy_list if c.get('keywords')), None)
        if sample_p:
            print(f"\nSample Policy Keywords: {sample_p.get('keywords', [])[:8]}")
    
    if reg_list:
        sample_r = next((c for c in reg_list if c.get('keywords')), None)
        if sample_r:
            print(f"Sample Regulation Keywords: {sample_r.get('keywords', [])[:8]}")

if __name__ == '__main__':
    main()
