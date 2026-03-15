import anthropic, os
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
try:
    resp = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=50,
        messages=[{'role': 'user', 'content': 'Say "ok" in JSON: {"status":"ok"}'}]
    )
    print(f'Response: {resp.content[0].text}')
    print('API: OK')
except anthropic.APIStatusError as e:
    print(f'API Error: {e.status_code} - {e.message}')
    print(f'Body: {e.body}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
