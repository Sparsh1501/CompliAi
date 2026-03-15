"""Analyze why so many gaps are classified as missing."""
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['compli-ai']
ga = db.gap_analyses.find_one({})

# Get the policy to see what clauses exist
policy_id = ga.get('policy_id')
policy = db.policies.find_one({'id': policy_id})
policy_clauses = policy.get('clauses', [])

print('=== POLICY ANALYSIS ===')
print(f'Policy Title: {policy.get("title")}')
print(f'Total Policy Clauses: {len(policy_clauses)}')

print('\n=== POLICY CLAUSE CATEGORIES ===')
policy_categories = {}
for c in policy_clauses:
    cat = c.get('subject_category', 'general')
    policy_categories[cat] = policy_categories.get(cat, 0) + 1
for cat, count in sorted(policy_categories.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')

print('\n=== SAMPLE POLICY CLAUSE TITLES ===')
for i, c in enumerate(policy_clauses[:20]):
    title = c.get('title', 'N/A')
    category = c.get('subject_category', 'N/A')
    print(f'{i+1}. [{category}] {title[:70]}')

# Get regulation to compare
reg_id = ga.get('regulation_id')
reg = db.regulations.find_one({'id': reg_id})
reg_clauses = reg.get('clauses', [])

print('\n=== REGULATION ANALYSIS ===')
print(f'Regulation Title: {reg.get("title")}')
print(f'Total Regulation Clauses: {len(reg_clauses)}')

print('\n=== REGULATION CLAUSE CATEGORIES ===')
reg_categories = {}
for c in reg_clauses:
    cat = c.get('subject_category', 'general')
    reg_categories[cat] = reg_categories.get(cat, 0) + 1
for cat, count in sorted(reg_categories.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')

# Analyze missing gaps
missing_gaps = [g for g in ga.get('gaps', []) if g.get('gap_type') == 'missing']
print(f'\n=== MISSING GAPS CATEGORY BREAKDOWN ===')
missing_categories = {}
for g in missing_gaps:
    cat = g.get('metadata', {}).get('subject_category', 'unknown')
    missing_categories[cat] = missing_categories.get(cat, 0) + 1
for cat, count in sorted(missing_categories.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')

# Check for patterns in regulation titles that are missing
print('\n=== COMMON PATTERNS IN MISSING REGULATION TITLES ===')
title_keywords = {}
for g in missing_gaps:
    rc = g.get('regulation_clause', {}) or {}
    title = rc.get('title', '')
    words = title.lower().replace('-', ' ').replace('_', ' ').split()
    for word in words:
        if len(word) > 4:  # Skip short words
            title_keywords[word] = title_keywords.get(word, 0) + 1

print('Top keywords in missing regulation titles:')
for kw, count in sorted(title_keywords.items(), key=lambda x: -x[1])[:20]:
    print(f'  {kw}: {count}')

# Check if policy has keywords field populated
print('\n=== POLICY KEYWORD COVERAGE ===')
policies_with_keywords = sum(1 for c in policy_clauses if c.get('keywords'))
print(f'Policies with keywords: {policies_with_keywords}/{len(policy_clauses)}')

# Sample keywords
if policies_with_keywords > 0:
    sample = next((c for c in policy_clauses if c.get('keywords')), None)
    if sample:
        print(f'Sample policy keywords: {sample.get("keywords", [])[:10]}')

regs_with_keywords = sum(1 for c in reg_clauses if c.get('keywords'))
print(f'Regulations with keywords: {regs_with_keywords}/{len(reg_clauses)}')

client.close()
print('\n=== DONE ===')
