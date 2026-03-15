import anthropic
import os
import time

# Load env
from dotenv import load_dotenv
load_dotenv('/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend/.env')

api_key = os.environ.get('ANTHROPIC_API_KEY')
print(f"API Key present: {bool(api_key)}")
print(f"API Key prefix: {api_key[:20]}..." if api_key else "No key")

try:
    client = anthropic.Anthropic(api_key=api_key)
    start = time.time()
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": "Say hello in one word."}]
    )
    elapsed = time.time() - start
    print(f"API Response: {response.content[0].text}")
    print(f"Response time: {elapsed:.2f}s")
    print("Anthropic API is WORKING")
except Exception as e:
    print(f"API Error: {type(e).__name__}: {e}")
