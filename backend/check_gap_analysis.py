"""Analyze gap analysis data to understand compliance score and task generation issues."""
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['compli-ai']

# Get latest gap analysis
ga = db.gap_analyses.find_one({}, sort=[('created_at', -1)])
print('=== LATEST GAP ANALYSIS ===')
print(f'ID: {ga.get("id")}')
print(f'Stored Compliance Score: {ga.get("compliance_score")}%')
print(f'fully_compliant_count: {ga.get("fully_compliant_count")}')
print(f'partially_compliant_count: {ga.get("partially_compliant_count")}')
print(f'non_compliant_count: {ga.get("non_compliant_count")}')
print(f'total_clauses_analyzed: {ga.get("total_clauses_analyzed")}')

gaps = ga.get('gaps', [])
print(f'\nTotal Gaps in DB: {len(gaps)}')

# Gap type breakdown
gap_types = {}
criticality_count = {}
for g in gaps:
    gt = g.get('gap_type', 'unknown')
    gap_types[gt] = gap_types.get(gt, 0) + 1
    
    pc = g.get('policy_clause') or {}
    rc = g.get('regulation_clause') or {}
    crit = pc.get('criticality') or rc.get('criticality') or 'medium'
    criticality_count[crit] = criticality_count.get(crit, 0) + 1

print(f'\nGap Types: {gap_types}')
print(f'Criticality Distribution: {criticality_count}')

# Manual compliance score calculation
score_map = {'compliant': 100, 'exceeds': 100, 'partial': 60, 'weak': 75, 'missing': 0, 'conflicting': 0}
weight_map = {'high': 3, 'medium': 2, 'low': 1}

weighted_sum = 0
max_weighted_sum = 0
for g in gaps:
    pc = g.get('policy_clause') or {}
    rc = g.get('regulation_clause') or {}
    crit = pc.get('criticality') or rc.get('criticality') or 'medium'
    weight = weight_map.get(crit, 2)
    score = score_map.get(g.get('gap_type'), 50)
    weighted_sum += score * weight
    max_weighted_sum += 100 * weight

expected = (weighted_sum / max_weighted_sum) * 100 if max_weighted_sum > 0 else 0
print(f'\n=== COMPLIANCE SCORE VERIFICATION ===')
print(f'weighted_sum: {weighted_sum}')
print(f'max_weighted_sum: {max_weighted_sum}')
print(f'Expected Score: {expected:.1f}%')
print(f'Stored Score: {ga.get("compliance_score")}%')
print(f'Score Matches: {abs(expected - ga.get("compliance_score", 0)) < 0.5}')

# Check tasks
print(f'\n=== TASK GENERATION CHECK ===')
tasks_count = db.tasks.count_documents({})
print(f'Total Tasks in DB: {tasks_count}')

# Check if any tasks linked to this gap analysis
tasks_for_ga = list(db.tasks.find({'gap_analysis_id': ga.get('id')}))
print(f'Tasks linked to this analysis: {len(tasks_for_ga)}')

# Check if policy_id was used
policy_id = ga.get('policy_id')
tasks_for_policy = list(db.tasks.find({'policy_id': policy_id}))
print(f'Tasks for policy {policy_id}: {len(tasks_for_policy)}')

# Check Critical/High gaps that should generate tasks
critical_high_gaps = [g for g in gaps if g.get('gap_type') != 'compliant' and g.get('severity') in ['Critical', 'High']]
print(f'\nCritical/High Non-Compliant Gaps: {len(critical_high_gaps)}')
print(f'(These should have generated tasks)')

# Sample gap for debugging
print(f'\n=== SAMPLE CRITICAL GAP ===')
for g in critical_high_gaps[:2]:
    print(f'  gap_type: {g.get("gap_type")}')
    print(f'  severity: {g.get("severity")}')
    print(f'  description: {g.get("description", "N/A")[:100]}...')
    print()

client.close()
print('\n=== ANALYSIS COMPLETE ===')
