"""Test new OCR settings: 3 pages per batch, Claude Sonnet"""
import os, time, base64, asyncio
from dotenv import load_dotenv
load_dotenv('/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend/.env')

import anthropic
from pdf2image import convert_from_path
from io import BytesIO
from PIL import Image

pdf_path = '/tmp/claude/uploads/d02857b6-000e-458b-9080-519926aa7355.pdf'
print(f"PDF: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")

# Convert first 3 pages (mimicking batch size 3)
print("Converting pages 1-3 to images...")
start = time.time()
images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=3)
print(f"  Conversion took: {time.time() - start:.2f}s")

# Build content with 3 images
content = []
total_img_size = 0
for idx, img in enumerate(images):
    if img.size[0] > 1568 or img.size[1] > 1568:
        img.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    img_bytes = buffer.getvalue()
    total_img_size += len(img_bytes)
    
    content.append({"type": "text", "text": f"--- PAGE {idx + 1} ---"})
    content.append({"type": "image", "source": {
        "type": "base64", "media_type": "image/jpeg",
        "data": base64.b64encode(img_bytes).decode('utf-8')
    }})

content.append({"type": "text", "text": """Extract ALL text from the document pages above. 
Instructions:
1. Preserve the exact text content from each page
2. Maintain paragraph structure and line breaks  
3. Keep section headers on their own lines
4. Mark each page's content with [PAGE_N]
5. Include ALL text - do not summarize or skip any content
Output the raw extracted text only, no commentary."""})

print(f"  Total image data: {total_img_size / 1024:.0f} KB")

client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

print("Calling Claude Sonnet Vision OCR (3 pages)...")
start = time.time()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=8192,
    messages=[{"role": "user", "content": content}]
)
elapsed = time.time() - start
text = response.content[0].text
print(f"  Response time: {elapsed:.2f}s")
print(f"  Extracted {len(text)} chars")
print(f"  Input tokens: {response.usage.input_tokens}")
print(f"  Output tokens: {response.usage.output_tokens}")
print(f"  First 500 chars:\n{text[:500]}")

# Estimate total time for 40 pages
total_pages = 40
batches = (total_pages + 2) // 3  # ceiling division
est_total = elapsed * batches
print(f"\n  Estimated total for {total_pages} pages ({batches} batches): {est_total:.0f}s ({est_total/60:.1f} min)")
