"""Test Sonnet Vision OCR - 3 page batch"""
import os, time, base64
from dotenv import load_dotenv
load_dotenv('/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend/.env')

import anthropic
from pdf2image import convert_from_path
from io import BytesIO
from PIL import Image

pdf_path = '/tmp/claude/uploads/d02857b6-000e-458b-9080-519926aa7355.pdf'

# Convert pages 1-3
images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=3)
content = []
for idx, img in enumerate(images):
    if img.size[0] > 1568 or img.size[1] > 1568:
        img.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    content.append({"type": "text", "text": f"--- PAGE {idx+1} ---"})
    content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buffer.getvalue()).decode('utf-8')}})

content.append({"type": "text", "text": "Extract ALL text from these pages. Mark each page with [PAGE_N]. Output raw text only."})

client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

print(f"Testing Sonnet Vision (3 pages, {len(content)} content blocks)...")
start = time.time()
r = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=8192,
    messages=[{"role": "user", "content": content}]
)
elapsed = time.time() - start
print(f"Response: {elapsed:.1f}s, {len(r.content[0].text)} chars")
print(f"Tokens: in={r.usage.input_tokens} out={r.usage.output_tokens}")
print(f"First 500 chars:\n{r.content[0].text[:500]}")

# Estimate total
batches = (40 + 2) // 3
est = elapsed * batches
print(f"\nEstimate for 40 pages ({batches} batches): {est:.0f}s ({est/60:.1f} min)")
