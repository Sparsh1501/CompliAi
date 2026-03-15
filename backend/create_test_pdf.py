#!/usr/bin/env python3
import os

# Create a minimal valid PDF
pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 4 0 R
>>
>>
/MediaBox [0 0 612 792]
/Contents 5 0 R
>>
endobj
4 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
5 0 obj
<<
/Length 200
>>
stream
BT
/F1 12 Tf
50 750 Td
(KYC Policy Document - Test Version) Tj
0 -20 Td
(Section 1: Customer Identification) Tj
0 -20 Td
(All customers must provide valid ID.) Tj
0 -20 Td
(Section 2: Verification Process) Tj
0 -20 Td
(Identity verification required.) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000262 00000 n
0000000341 00000 n
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
593
%%EOF
"""

os.makedirs('/tmp/claude', exist_ok=True)
with open('/tmp/claude/test_kyc_policy.pdf', 'wb') as f:
    f.write(pdf_content)

print("PDF created successfully")
print(f"Size: {len(pdf_content)} bytes")
