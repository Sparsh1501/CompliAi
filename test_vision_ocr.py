"""Quick test: convert first page of the PDF and try Claude Vision OCR on just 1 page"""
import os, time, base64, asyncio
from dotenv import load_dotenv
load_dotenv('/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend/.env')

import anthropic
from pdf2image import convert_from_path
from io import BytesIO
from PIL import Image

# Find the uploaded PDF
upload_dir = '/tmp/claude/uploads'
pdfs = [f for f in os.listdir(upload_dir) if f.endswith('.pdf')]
print(f"PDFs in upload dir: {pdfs}")

if pdfs:
    # Use the 3.3MB KYC policy PDF specifically
    pdf_path = os.path.join(upload_dir, 'd02857b6-000e-458b-9080-519926aa7355.pdf')
    print(f"Using: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
    
    # Convert just first page
    print("Converting page 1 to image...")
    start = time.time()
    images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)
    print(f"  Conversion took: {time.time() - start:.2f}s")
    
    # Resize
    img = images[0]
    print(f"  Image size: {img.size}")
    if img.size[0] > 1568 or img.size[1] > 1568:
        img.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
        print(f"  Resized to: {img.size}")
    
    # To JPEG
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    img_bytes = buffer.getvalue()
    print(f"  JPEG size: {len(img_bytes)} bytes")
    
    # Try Claude Vision
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    
    print("Calling Claude Vision OCR on page 1...")
    start = time.time()
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "--- PAGE 1 ---"},
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(img_bytes).decode('utf-8')
                }},
                {"type": "text", "text": "Extract ALL text from this page. Output the raw extracted text only."}
            ]
        }]
    )
    elapsed = time.time() - start
    text = response.content[0].text
    print(f"  Response time: {elapsed:.2f}s")
    print(f"  Extracted {len(text)} chars")
    print(f"  First 300 chars: {text[:300]}")
    print(f"  Input tokens: {response.usage.input_tokens}")
    print(f"  Output tokens: {response.usage.output_tokens}")
else:
    print("No PDFs found in upload directory")
