// MongoDB script to insert test regulatory updates
db = db.getSiblingDB('compli-ai');

// Clear existing test data
db.regulation_updates.deleteMany({
  id: {
    $in: ['reg_update_001', 'reg_update_002', 'reg_update_003', 'reg_update_004']
  }
});

// Insert regulatory updates
const updates = [
  {
    id: 'reg_update_001',
    regulation_id: 'reg_rbi_kyc_2023',
    organization: 'system',
    crawl_date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    source_url: 'https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12345',
    change_type: 'new',
    ai_summary: 'RBI introduces enhanced KYC norms for digital lending platforms. All NBFCs must implement video-based KYC within 90 days. New requirements include biometric verification and real-time address validation.',
    impact_analysis: 'High impact - affects 15 existing policies. Requires immediate implementation of video KYC infrastructure and process updates.',
    affected_policies: ['pol_kyc_001', 'pol_digital_lending_001'],
    affected_clauses: ['clause_kyc_video_001', 'clause_biometric_001'],
    affected_tasks: [],
    compliance_posture_comparison: 'Current KYC policy covers basic video KYC but lacks biometric requirements. Gap identified in real-time address validation procedures.',
    remediation_effort_estimate: 'Medium effort (4-6 weeks). Requires vendor integration for biometric system and policy updates across 3 departments.',
    priority_recommendation: 'high',
    auto_created_tasks: ['task_kyc_update_001', 'task_vendor_selection_001'],
    status: 'pending_review',
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
  },
  {
    id: 'reg_update_002',
    regulation_id: 'reg_fiu_aml_2024',
    organization: 'system',
    crawl_date: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    source_url: 'https://fiuindia.gov.in/circular/2024/AML-01',
    change_type: 'amendment',
    ai_summary: 'FIU-IND updates AML reporting thresholds for digital transactions. New threshold reduced from ₹10 lakhs to ₹5 lakhs for suspicious transaction reporting.',
    impact_analysis: 'Medium impact - affects transaction monitoring systems and 8 compliance policies. Requires recalibration of automated alerts.',
    affected_policies: ['pol_aml_001', 'pol_transaction_monitoring_001'],
    affected_clauses: ['clause_str_threshold_001'],
    affected_tasks: [],
    compliance_posture_comparison: 'Current STR threshold is ₹10 lakhs. System needs parameter update but overall framework is compliant.',
    remediation_effort_estimate: 'Low effort (1-2 weeks). Configuration change in transaction monitoring system and policy documentation update.',
    priority_recommendation: 'medium',
    auto_created_tasks: ['task_aml_threshold_update_001'],
    status: 'reviewed',
    reviewed_by: 'user_001',
    reviewed_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString()
  },
  {
    id: 'reg_update_003',
    regulation_id: 'reg_npci_upi_2024',
    organization: 'system',
    crawl_date: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    source_url: 'https://npci.org.in/PDF/npci/upi/circular/2024/UPI-Security-01.pdf',
    change_type: 'new',
    ai_summary: 'NPCI mandates additional security layer for UPI transactions above ₹2000. Two-factor authentication required for all merchant transactions.',
    impact_analysis: 'Critical impact - affects all UPI payment flows. Immediate action required to maintain UPI license compliance.',
    affected_policies: ['pol_upi_001', 'pol_payment_security_001'],
    affected_clauses: ['clause_upi_2fa_001', 'clause_merchant_txn_001'],
    affected_tasks: [],
    compliance_posture_comparison: 'Current UPI implementation has single-factor auth for small transactions. Non-compliant with new circular - deadline is 30 days from issue date.',
    remediation_effort_estimate: 'High effort (6-8 weeks). Requires app updates, testing across platforms, and user communication campaign.',
    priority_recommendation: 'critical',
    auto_created_tasks: ['task_upi_2fa_implementation_001', 'task_upi_testing_001', 'task_user_communication_001'],
    status: 'pending_review',
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString()
  },
  {
    id: 'reg_update_004',
    regulation_id: 'reg_rbi_cyber_security_2024',
    organization: 'system',
    crawl_date: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    source_url: 'https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12367',
    change_type: 'amendment',
    ai_summary: 'RBI updates cyber security framework for NBFCs. Mandatory quarterly security audits and real-time threat intelligence sharing with CERT-In.',
    impact_analysis: 'Medium impact - affects IT security policies and audit procedures. Quarterly compliance overhead increases.',
    affected_policies: ['pol_cyber_security_001', 'pol_it_audit_001'],
    affected_clauses: ['clause_security_audit_001', 'clause_threat_sharing_001'],
    affected_tasks: [],
    compliance_posture_comparison: 'Current policy requires bi-annual audits. Need to increase frequency and establish CERT-In integration.',
    remediation_effort_estimate: 'Medium effort (3-4 weeks). Vendor engagement for audit services and API integration with CERT-In portal.',
    priority_recommendation: 'medium',
    auto_created_tasks: ['task_cert_in_integration_001'],
    status: 'reviewed',
    reviewed_by: 'user_001',
    reviewed_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString()
  }
];

db.regulation_updates.insertMany(updates);
print('✓ Inserted ' + updates.length + ' regulatory updates');

// Insert matching regulations
const regulations = [
  {
    id: 'reg_rbi_kyc_2023',
    user_id: 'system',
    organization: 'system',
    title: 'RBI Master Direction - KYC Norms',
    regulatory_body: 'RBI',
    circular_number: 'RBI/2023-24/123',
    issued_date: '2023-12-01',
    effective_date: '2024-01-01',
    created_at: new Date()
  },
  {
    id: 'reg_fiu_aml_2024',
    user_id: 'system',
    organization: 'system',
    title: 'FIU-IND AML Reporting Guidelines',
    regulatory_body: 'FIU-IND',
    circular_number: 'FIU/2024/AML-01',
    issued_date: '2024-01-15',
    effective_date: '2024-02-01',
    created_at: new Date()
  },
  {
    id: 'reg_npci_upi_2024',
    user_id: 'system',
    organization: 'system',
    title: 'NPCI UPI Security Framework',
    regulatory_body: 'NPCI',
    circular_number: 'NPCI/UPI/2024/SEC-01',
    issued_date: '2024-02-01',
    effective_date: '2024-03-01',
    created_at: new Date()
  },
  {
    id: 'reg_rbi_cyber_security_2024',
    user_id: 'system',
    organization: 'system',
    title: 'RBI Cyber Security Framework for NBFCs',
    regulatory_body: 'RBI',
    circular_number: 'RBI/2024/CYBER-01',
    issued_date: '2024-01-20',
    effective_date: '2024-04-01',
    created_at: new Date()
  }
];

regulations.forEach(reg => {
  db.regulations.updateOne(
    { id: reg.id },
    { $setOnInsert: reg },
    { upsert: true }
  );
});

print('✓ Created/updated ' + regulations.length + ' regulations');
print('\nTest data created successfully!');
