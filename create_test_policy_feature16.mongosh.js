// MongoDB shell script to create test policy for Feature #16
// Run with: mongosh compli-ai create_test_policy_feature16.mongosh.js

const user = db.users.findOne({ email: 'feature16test@test.com' });

if (!user) {
    print('ERROR: Test user not found');
    quit(1);
}

const userId = user.id;
const organization = user.organization;
const policyId = `policy_${Date.now()}`;
const timestamp = new Date().toISOString();

print(`Found user: ${user.full_name} (${organization})`);

const policy = {
    id: policyId,
    title: 'KYC Policy 2024 - Feature 16 Test',
    policy_type: 'KYC',
    description: 'Know Your Customer policy document - test upload',
    version: '1.0',
    department: 'Compliance',
    organization: organization,
    created_by: userId,
    status: 'active',
    file_name: 'test-policy-kyc.pdf',
    file_size: 3907,
    file_path: '/tmp/uploads/test-policy-kyc.pdf',
    upload_date: timestamp,
    last_modified: timestamp,
    clauses: [
        {
            id: `clause_${Date.now()}_1`,
            policy_id: policyId,
            text: 'All customers must provide valid government-issued photo identification before account opening.',
            section: 'Customer Identification',
            clause_number: '1',
            category: 'identity_verification',
            keywords: ['identification', 'photo ID', 'government-issued'],
            created_at: timestamp
        },
        {
            id: `clause_${Date.now()}_2`,
            policy_id: policyId,
            text: 'Proof of address must be submitted within 30 days of account opening through utility bills or bank statements.',
            section: 'Address Verification',
            clause_number: '2',
            category: 'address_verification',
            keywords: ['address', 'utility bills', 'bank statements'],
            created_at: timestamp
        },
        {
            id: `clause_${Date.now()}_3`,
            policy_id: policyId,
            text: 'Enhanced due diligence is required for high-risk customers including PEPs and those from high-risk jurisdictions.',
            section: 'Enhanced Due Diligence',
            clause_number: '3',
            category: 'risk_assessment',
            keywords: ['enhanced due diligence', 'PEPs', 'high-risk'],
            created_at: timestamp
        },
        {
            id: `clause_${Date.now()}_4`,
            policy_id: policyId,
            text: 'Customer information must be updated and reverified annually to maintain current records.',
            section: 'Annual Updates',
            clause_number: '4',
            category: 'record_maintenance',
            keywords: ['annual update', 'reverification', 'current records'],
            created_at: timestamp
        },
        {
            id: `clause_${Date.now()}_5`,
            policy_id: policyId,
            text: 'Any suspicious activity must be reported immediately to the compliance officer within 24 hours of detection.',
            section: 'Suspicious Activity Reporting',
            clause_number: '5',
            category: 'reporting',
            keywords: ['suspicious activity', 'compliance officer', '24 hours'],
            created_at: timestamp
        }
    ],
    metadata: {
        total_clauses: 5,
        extraction_method: 'AI-powered (test data)',
        processing_status: 'completed'
    }
};

db.policies.insertOne(policy);
print(`Created policy: ${policyId}`);
print(`  - Title: ${policy.title}`);
print(`  - Type: ${policy.policy_type}`);
print(`  - Clauses: ${policy.clauses.length}`);

// Create upload job
const jobId = `job_${Date.now()}`;
const job = {
    id: jobId,
    user_id: userId,
    organization: organization,
    job_type: 'policy',
    file_name: 'test-policy-kyc.pdf',
    file_size: 3907,
    status: 'completed',
    progress_percent: 100,
    entity_id: policyId,
    entity_type: 'policy',
    started_at: timestamp,
    completed_at: timestamp,
    metadata: {
        title: policy.title,
        policy_type: policy.policy_type,
        clauses_extracted: 5
    }
};

db.upload_jobs.insertOne(job);
print(`Created upload job: ${jobId}`);
print(`\nSUCCESS: Policy ID = ${policyId}`);
