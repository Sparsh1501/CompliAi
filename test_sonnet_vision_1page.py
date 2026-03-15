"""Test Sonnet Vision OCR - single page"""
import os, time, base64
from dotenv import load_dotenv
load_dotenv('/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend/.env')

import anthropic
from pdf2image import convert_from_path
from io import BytesIO
from PIL import Image

pdf_path = '/tmp/claude/uploads/d02857b6-000e-458b-9080-519926aa7355.pdf'

# Convert just page 1
images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)
img = images[0]
if img.size[0] > 1568 or img.size[1] > 1568:
    img.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
buffer = BytesIO()
img.save(buffer, format='JPEG', quality=85)
img_bytes = buffer.getvalue()
print(f"Image: {len(img_bytes)} bytes, size: {img.size}")

client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

print("Testing Sonnet Vision (1 page)...")
start = time.time()
r = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode('utf-8')}},
        {"type": "text", "text": "Extract ALL text from this page. Output raw text only."}
    ]}]
)
elapsed = time.time() - start
print(f"Response: {elapsed:.1f}s, {len(r.content[0].text)} chars")
print(f"Tokens: in={r.usage.input_tokens} out={r.usage.output_tokens}")
print(f"Text: {r.content[0].text[:300]}")
