import pymongo
db = pymongo.MongoClient('mongodb://localhost:27017')['compli-ai']
latest = db.gap_analyses.find_one({}, {'_id':0, 'id':1, 'gaps': {'$slice': 1}, 'policy_id': 1, 'regulation_id': 1}, sort=[('created_at', -1)])
if latest:
    print(f"Analysis id: {latest.get('id', 'NONE')}")
    print(f"policy_id: {latest.get('policy_id', 'NONE')}")
    print(f"regulation_id: {latest.get('regulation_id', 'NONE')}")
    if latest.get('gaps'):
        g = latest['gaps'][0]
        print(f"\nGap keys: {list(g.keys())}")
        pc = g.get('policy_clause')
        rc = g.get('regulation_clause')
        print(f"\npolicy_clause: {pc}")
        print(f"\nregulation_clause keys: {list(rc.keys()) if rc else 'None'}")
        if rc:
            print(f"  regulation_clause.id: {rc.get('id', 'NONE')}")
            print(f"  regulation_clause.text: {(rc.get('text') or '')[:80]}")
    else:
        print("No gaps found")
    
    # Check policy file_url
    policy = db.policies.find_one({'id': latest.get('policy_id')}, {'_id': 0, 'file_url': 1, 'title': 1})
    regulation = db.regulations.find_one({'id': latest.get('regulation_id')}, {'_id': 0, 'file_url': 1, 'title': 1})
    print(f"\nPolicy: {policy}")
    print(f"Regulation: {regulation}")
else:
    print('No gap analyses found')
