"""Analyze existing gap analysis data to understand issues."""
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['compli-ai']

# Get the problematic gap analysis
ga = db.gap_analyses.find_one({'id': '34088f21-02ca-4328-b2e9-9d45892f538a'})

print('=== ANALYSIS OF EXISTING GAP ANALYSIS ===')
print(f'Score: {ga.get("compliance_score")}%')
print(f'Total Gaps: {len(ga.get("gaps", []))}')

gaps = ga.get('gaps', [])

# Count gap types
gap_types = {}
for g in gaps:
    gt = g.get('gap_type', 'unknown')
    gap_types[gt] = gap_types.get(gt, 0) + 1
print(f'\nGap Type Breakdown:')
for k, v in sorted(gap_types.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')

# Check for problematic patterns
has_reg = len([g for g in gaps if g.get('regulation_clause') and g['regulation_clause'].get('title')])
has_policy = len([g for g in gaps if g.get('policy_clause') and g['policy_clause'].get('title')])
no_reg = len([g for g in gaps if not g.get('regulation_clause') or not g['regulation_clause'].get('title')])

print(f'\n=== STRUCTURE ANALYSIS ===')
print(f'Gaps with regulation: {has_reg}')
print(f'Gaps with policy: {has_policy}')
print(f'Gaps WITHOUT regulation: {no_reg}')

# Sample problematic gaps
print(f'\n=== SAMPLE GAPS (showing policy-first issue) ===')
for i, g in enumerate(gaps[:3]):
    print(f'\n--- Gap {i+1} ---')
    print(f'Type: {g.get("gap_type")}')
    print(f'Severity: {g.get("severity")}')
    pc = g.get('policy_clause', {})
    rc = g.get('regulation_clause', {})
    print(f'Policy: {pc.get("title", "N/A")[:50] if pc else "N/A"}')
    print(f'Regulation: {rc.get("title", "NULL")[:50] if rc else "NULL - NO MATCH!"}')
    desc = g.get("description", "")
    print(f'Description: {desc[:100] if desc else "N/A"}...')

# Check for "missing" gaps specifically
print(f'\n=== MISSING GAPS ANALYSIS ===')
missing = [g for g in gaps if g.get('gap_type') == 'missing']
print(f'Total missing: {len(missing)}')
if missing:
    m = missing[0]
    print(f'Sample missing gap:')
    print(f'  Policy: {m.get("policy_clause", {}).get("title", "N/A")[:60]}')
    print(f'  Regulation: {m.get("regulation_clause", {}).get("title", "NONE") if m.get("regulation_clause") else "NONE"}')

client.close()
print("\n=== DONE ===")
