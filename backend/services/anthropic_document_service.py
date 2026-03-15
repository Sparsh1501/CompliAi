"""
Anthropic Document Service

Uses Claude Vision API for high-quality OCR and document understanding.
Replaces Nanonets OCR with a unified Anthropic-based approach.

Benefits:
- Single vendor (Anthropic) for OCR + clause extraction
- No external OCR dependencies
- Better context understanding - Claude "reads" the document, not just OCR
- Handles scanned PDFs, images, and complex layouts
"""

import anthropic
import os
import base64
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from pdf2image import convert_from_path
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)


class AnthropicDocumentService:
    """
    Document processing service using Claude Vision API.
    
    Capabilities:
    - OCR for scanned PDFs via image conversion
    - Direct text extraction with structure preservation
    - Section and clause detection during OCR
    - Multi-page document handling
    """
    
    # Optimal settings for document OCR
    DEFAULT_DPI = 200  # Balance between quality and file size
    MAX_IMAGE_SIZE = (1568, 1568)  # Claude's optimal image size
    JPEG_QUALITY = 85
    MAX_PAGES_PER_BATCH = 3  # Small batches for reliable processing
    OCR_MODEL = "claude-sonnet-4-20250514"  # Sonnet is faster and sufficient for OCR
    BATCH_TIMEOUT = 180  # 3 minutes per page timeout
    MAX_CONCURRENT_OCR = 5  # Max concurrent API calls for parallel OCR
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured")
            self.client = None
            self.async_client = None
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
    
    def _pdf_to_images(self, file_path: str) -> List[bytes]:
        """
        Convert PDF pages to optimized JPEG images for Claude Vision.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of JPEG image bytes
        """
        try:
            images = convert_from_path(file_path, dpi=self.DEFAULT_DPI)
            image_bytes_list = []
            
            for idx, image in enumerate(images):
                # Resize if too large
                if image.size[0] > self.MAX_IMAGE_SIZE[0] or image.size[1] > self.MAX_IMAGE_SIZE[1]:
                    image.thumbnail(self.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
                
                # Convert to JPEG bytes
                buffer = BytesIO()
                image.save(buffer, format='JPEG', quality=self.JPEG_QUALITY)
                image_bytes_list.append(buffer.getvalue())
                
                logger.debug(f"Converted page {idx + 1} to image ({len(buffer.getvalue())} bytes)")
            
            return image_bytes_list
            
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {str(e)}")
            raise
    
    async def _ocr_single_page(self, img_bytes: bytes, page_num: int, total_pages: int, semaphore: asyncio.Semaphore) -> tuple:
        """OCR a single page with concurrency control. Returns (page_num, text)."""
        async with semaphore:
            try:
                page_start = time.time()
                content = [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": base64.b64encode(img_bytes).decode('utf-8')
                    }},
                    {"type": "text", "text": "Extract ALL text from this page exactly as written. Preserve paragraph structure, headers, and line breaks. Output the raw extracted text only."}
                ]
                
                response = await asyncio.wait_for(
                    self.async_client.messages.create(
                        model=self.OCR_MODEL,
                        max_tokens=4096,
                        messages=[{"role": "user", "content": content}]
                    ),
                    timeout=self.BATCH_TIMEOUT
                )
                text = response.content[0].text
                elapsed = time.time() - page_start
                logger.info(f"  [OCR] Page {page_num}/{total_pages}: {len(text)} chars in {elapsed:.1f}s")
                return (page_num, f"[PAGE_{page_num}]\n{text}")
            except asyncio.TimeoutError:
                logger.warning(f"  [OCR] Page {page_num}/{total_pages}: TIMEOUT after {self.BATCH_TIMEOUT}s")
                return (page_num, f"[PAGE_{page_num}]\n[OCR timed out for page {page_num}]")
            except Exception as e:
                logger.error(f"  [OCR] Page {page_num}/{total_pages}: FAILED - {e}")
                return (page_num, f"[PAGE_{page_num}]\n[OCR failed for page {page_num}: {str(e)}]")

    async def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF using Claude Vision API with parallel page processing.
        """
        if not self.async_client:
            raise ValueError("Anthropic API key not configured")
        
        try:
            ocr_start = time.time()
            logger.info("="*60)
            logger.info("[OCR START] Claude Vision (Sonnet 4)")
            logger.info(f"  File: {os.path.basename(file_path)}")
            logger.info(f"  Size: {os.path.getsize(file_path)} bytes")
            
            # Convert PDF to images
            image_bytes_list = await asyncio.to_thread(self._pdf_to_images, file_path)
            total_pages = len(image_bytes_list)
            convert_time = time.time() - ocr_start
            logger.info(f"  Pages: {total_pages} (converted in {convert_time:.1f}s)")
            logger.info(f"  Concurrency: {self.MAX_CONCURRENT_OCR} parallel requests")
            logger.info("-"*40)
            
            # Process all pages in parallel with concurrency limit
            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_OCR)
            tasks = [
                self._ocr_single_page(img_bytes, page_num, total_pages, semaphore)
                for page_num, img_bytes in enumerate(image_bytes_list, 1)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Sort by page number and combine
            results.sort(key=lambda x: x[0])
            full_text = "\n\n".join(text for _, text in results)
            
            total_time = time.time() - ocr_start
            logger.info("-"*40)
            logger.info(f"[OCR COMPLETE] {len(full_text)} chars from {total_pages} pages in {total_time:.1f}s ({total_time/total_pages:.1f}s/page)")
            logger.info("="*60)
            
            return full_text
            
        except Exception as e:
            logger.error(f"Claude Vision OCR failed: {str(e)}")
            raise
    
    async def extract_text_with_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text with structural analysis in a single Claude call.
        
        This method performs OCR and initial structure detection together,
        identifying sections, headers, and document organization.
        
        Returns:
            Dictionary with:
            - text: Full extracted text
            - sections: Detected sections with titles and content
            - metadata: Document metadata (page count, etc.)
        """
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        try:
            logger.info(f"Starting structured Claude Vision OCR for: {file_path}")
            
            # Convert PDF to images
            image_bytes_list = await asyncio.to_thread(self._pdf_to_images, file_path)
            total_pages = len(image_bytes_list)
            
            all_sections = []
            full_text_parts = []
            
            # Process in batches
            for batch_start in range(0, total_pages, self.MAX_PAGES_PER_BATCH):
                batch_end = min(batch_start + self.MAX_PAGES_PER_BATCH, total_pages)
                batch_images = image_bytes_list[batch_start:batch_end]
                
                content = []
                for idx, img_bytes in enumerate(batch_images):
                    page_num = batch_start + idx + 1
                    content.append({
                        "type": "text",
                        "text": f"--- PAGE {page_num} ---"
                    })
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.b64encode(img_bytes).decode('utf-8')
                        }
                    })
                
                content.append({
                    "type": "text",
                    "text": """Extract text and identify document structure from the pages above.

Output a JSON object with this structure:
{
    "raw_text": "Full extracted text with [PAGE_N] markers",
    "sections": [
        {
            "title": "Section title (from CAPITAL LETTER headers or numbered sections)",
            "content": "Section content text",
            "page_start": 1,
            "section_type": "header|clause|paragraph|table|list"
        }
    ]
}

Rules:
1. Extract ALL text completely - do not summarize
2. Identify CAPITAL LETTER lines as section headers
3. Numbered sections (1., 1.1, Article 1) are also section headers
4. Group content under the nearest preceding header
5. Mark page boundaries in raw_text with [PAGE_N]

Return valid JSON only."""
                })
                
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.OCR_MODEL,
                    max_tokens=8192,
                    messages=[
                        {"role": "user", "content": content}
                    ]
                )
                
                response_text = response.content[0].text
                
                # Parse JSON response
                try:
                    # Handle potential markdown code blocks
                    if "```json" in response_text:
                        response_text = response_text.split("```json")[1].split("```")[0]
                    elif "```" in response_text:
                        response_text = response_text.split("```")[1].split("```")[0]
                    
                    batch_data = __import__('json').loads(response_text)
                    full_text_parts.append(batch_data.get('raw_text', ''))
                    all_sections.extend(batch_data.get('sections', []))
                except __import__('json').JSONDecodeError:
                    logger.warning(f"Failed to parse structured response for pages {batch_start + 1}-{batch_end}")
                    full_text_parts.append(response_text)
            
            return {
                "text": "\n\n".join(full_text_parts),
                "sections": all_sections,
                "metadata": {
                    "total_pages": total_pages,
                    "section_count": len(all_sections)
                }
            }
            
        except Exception as e:
            logger.error(f"Structured Claude Vision OCR failed: {str(e)}")
            raise
    
    async def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from a single image file.
        
        Args:
            image_path: Path to image file (PNG, JPG, etc.)
            
        Returns:
            Extracted text
        """
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        try:
            # Read and optimize image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large
                if img.size[0] > self.MAX_IMAGE_SIZE[0] or img.size[1] > self.MAX_IMAGE_SIZE[1]:
                    img.thumbnail(self.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
                
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=self.JPEG_QUALITY)
                image_bytes = buffer.getvalue()
            
            # Determine media type
            media_type = "image/jpeg"
            
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.OCR_MODEL,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64.b64encode(image_bytes).decode('utf-8')
                                }
                            },
                            {
                                "type": "text",
                                "text": "Extract ALL text from this image exactly as it appears. Preserve formatting and structure. Output only the extracted text."
                            }
                        ]
                    }
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Image text extraction failed: {str(e)}")
            raise


# Singleton instance
_anthropic_doc_service: Optional[AnthropicDocumentService] = None


def get_anthropic_document_service() -> AnthropicDocumentService:
    """Get singleton instance of Anthropic document service."""
    global _anthropic_doc_service
    if _anthropic_doc_service is None:
        _anthropic_doc_service = AnthropicDocumentService()
    return _anthropic_doc_service
