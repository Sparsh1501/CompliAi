// Connect to database
use("compli-ai");

// Insert gap analysis with compliance score
const gapAnalysis = {
  id: UUID().toString(),
  organization: "Test NBFC Ltd",
  policy_id: UUID().toString(),
  regulation_id: UUID().toString(),
  compliance_score: 75.5,
  gaps: [
    {
      gap_id: "gap_1",
      policy_clause_id: "clause_1",
      regulation_clause_id: "reg_clause_1",
      gap_description: "KYC process needs enhancement",
      severity: "High",
      recommendation: "Implement video KYC"
    },
    {
      gap_id: "gap_2",
      policy_clause_id: "clause_2",
      regulation_clause_id: "reg_clause_2",
      gap_description: "Transaction monitoring frequency insufficient",
      severity: "Critical",
      recommendation: "Increase monitoring to daily"
    },
    {
      gap_id: "gap_3",
      policy_clause_id: "clause_3",
      regulation_clause_id: "reg_clause_3",
      gap_description: "Customer data retention period unclear",
      severity: "Medium",
      recommendation: "Define 10-year retention policy"
    }
  ],
  created_at: new Date(),
  updated_at: new Date(),
  status: "completed"
};

db.gap_analyses.insertOne(gapAnalysis);
print("✓ Created gap analysis with compliance score: " + gapAnalysis.compliance_score + "%");
print("✓ Total gaps: " + gapAnalysis.gaps.length);
print("✓ Critical gaps: 1");

// Insert regulation to show in regulator overview
const regulation = {
  id: UUID().toString(),
  organization: "Test NBFC Ltd",
  regulatory_body: "RBI",
  name: "RBI Master Direction on KYC",
  circular_number: "RBI/2023/KYC/001",
  created_at: new Date(),
  updated_at: new Date()
};

db.regulations.insertOne(regulation);
print("✓ Created regulation: " + regulation.name);

// Insert another regulation for SEBI
const regulation2 = {
  id: UUID().toString(),
  organization: "Test NBFC Ltd",
  regulatory_body: "SEBI",
  name: "SEBI Compliance Framework",
  circular_number: "SEBI/2023/CF/002",
  created_at: new Date(),
  updated_at: new Date()
};

db.regulations.insertOne(regulation2);
print("✓ Created regulation: " + regulation2.name);
