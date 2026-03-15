import base64

with open('test-policy-kyc.pdf', 'rb') as f:
    pdf_content = f.read()
    b64 = base64.b64encode(pdf_content).decode()
    print(b64)
