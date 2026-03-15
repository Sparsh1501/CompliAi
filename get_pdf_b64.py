import base64
with open('test-policy-kyc.pdf', 'rb') as f:
    print(base64.b64encode(f.read()).decode())
