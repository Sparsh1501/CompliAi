"""
Mistral OCR Service

Uses Mistral's OCR API for cost-effective document text extraction.
Mistral OCR is significantly cheaper than Claude Vision while maintaining good quality.

Pricing comparison (as of 2025):
- Mistral OCR: ~$0.001 per page
- Claude Vision: ~$0.01-0.03 per page (10-30x more expensive)
"""

import os
import base64
import logging
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MistralOCRService:
    """
    Document processing service using Mistral OCR API.
    
    Capabilities:
    - OCR for scanned PDFs (direct PDF upload)
    - Image-based OCR
    - Multi-page document handling
    - Cost-effective alternative to Claude Vision
    """
    
    OCR_API_URL = "https://api.mistral.ai/v1/ocr"
    CHAT_API_URL = "https://api.mistral.ai/v1/chat/completions"
    
    def __init__(self, api_key: str = None):
        """
        Initialize the Mistral OCR service.
        
        Args:
            api_key: Mistral API key. Falls back to env vars.
        """
        self.api_key = api_key or os.environ.get('MISTRAL_API_KEY')
        if not self.api_key:
            logger.warning("MISTRAL_API_KEY not configured")
        
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF using Mistral OCR API.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text with page markers
        """
        if not self.api_key:
            raise ValueError("Mistral API key not configured. Set MISTRAL_API_KEY environment variable.")
        
        try:
            logger.info(f"Starting Mistral OCR for: {file_path}")
            
            # Read the PDF file
            with open(file_path, 'rb') as f:
                pdf_bytes = f.read()
            
            # Encode as base64
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            # Prepare the OCR request
            payload = {
                "model": "mistral-ocr-latest",
                "document": {
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{pdf_base64}"
                }
            }
            
            import time
            start_time = time.time()
            
            # Log OCR Request
            logger.info("="*60)
            logger.info("[MISTRAL OCR REQUEST]")
            logger.info(f"  API URL: {self.OCR_API_URL}")
            logger.info(f"  Model: mistral-ocr-latest")
            logger.info(f"  PDF Size: {len(pdf_bytes)} bytes")
            logger.info(f"  Base64 Size: {len(pdf_base64)} chars")
            logger.info("="*60)
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    self.OCR_API_URL,
                    headers=self._get_headers(),
                    json=payload
                )
                
                elapsed_time = time.time() - start_time
                
                # Log OCR Response
                logger.info("="*60)
                logger.info("[MISTRAL OCR RESPONSE]")
                logger.info(f"  Time Elapsed: {elapsed_time:.2f} seconds")
                logger.info(f"  Status Code: {response.status_code}")
                logger.info(f"  Response Size: {len(response.text)} chars")
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"  Error: {error_text}")
                    logger.info("="*60)
                    raise Exception(f"Mistral OCR API error: {response.status_code} - {error_text}")
                
                result = response.json()
                logger.info(f"  Response Keys: {list(result.keys())}")
                logger.info(f"  Response Preview: {str(result)[:500]}...")
                logger.info("="*60)
            
            # Process the OCR result
            extracted_text = self._process_ocr_result(result)
            
            logger.info(f"Mistral OCR extracted {len(extracted_text)} characters")
            return extracted_text
            
        except Exception as e:
            logger.error(f"Mistral OCR failed: {str(e)}")
            raise
    
    def _process_ocr_result(self, result: Dict[str, Any]) -> str:
        """
        Process Mistral OCR API response and extract text.
        
        Args:
            result: OCR API response
            
        Returns:
            Formatted text with page markers
        """
        all_text = []
        
        # Mistral OCR returns pages with markdown content
        pages = result.get("pages", [])
        
        for page in pages:
            page_num = page.get("index", 0) + 1
            page_markdown = page.get("markdown", "")
            
            # Add page marker
            all_text.append(f"\n[PAGE_{page_num}]\n{page_markdown}")
        
        return "\n".join(all_text)
    
    async def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from a single image file.
        
        Args:
            image_path: Path to image file (PNG, JPG, etc.)
            
        Returns:
            Extracted text
        """
        if not self.api_key:
            raise ValueError("Mistral API key not configured")
        
        try:
            # Read the image file
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            # Determine media type
            ext = Path(image_path).suffix.lower()
            media_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            media_type = media_types.get(ext, 'image/jpeg')
            
            # Encode as base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Use chat completions with vision for single images
            payload = {
                "model": "pixtral-12b-2409",  # Mistral's vision model
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "Extract ALL text from this image exactly as it appears. Preserve formatting and structure. Output only the extracted text."
                            }
                        ]
                    }
                ],
                "max_tokens": 4096
            }
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.CHAT_API_URL,
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"Mistral Vision API error: {response.status_code} - {error_text}")
                    raise Exception(f"Mistral Vision API error: {response.status_code}")
                
                result = response.json()
            
            # Extract text from chat response
            text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            logger.info(f"Mistral Vision extracted {len(text)} characters from image")
            return text
            
        except Exception as e:
            logger.error(f"Mistral image text extraction failed: {str(e)}")
            raise
    
    async def extract_text_with_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text with structural analysis.
        
        Returns:
            Dictionary with:
            - text: Full extracted text
            - pages: List of page content
            - metadata: Document metadata
        """
        if not self.api_key:
            raise ValueError("Mistral API key not configured")
        
        try:
            logger.info(f"Starting structured Mistral OCR for: {file_path}")
            
            # Read and encode PDF
            with open(file_path, 'rb') as f:
                pdf_bytes = f.read()
            
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            payload = {
                "model": "mistral-ocr-latest",
                "document": {
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{pdf_base64}"
                },
                "include_image_base64": False  # Don't need images back
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    self.OCR_API_URL,
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code != 200:
                    raise Exception(f"Mistral OCR API error: {response.status_code}")
                
                result = response.json()
            
            pages = result.get("pages", [])
            total_pages = len(pages)
            
            # Build structured response
            all_text = []
            page_contents = []
            
            for page in pages:
                page_num = page.get("index", 0) + 1
                page_markdown = page.get("markdown", "")
                
                all_text.append(f"[PAGE_{page_num}]\n{page_markdown}")
                page_contents.append({
                    "page_number": page_num,
                    "content": page_markdown,
                    "dimensions": page.get("dimensions", {})
                })
            
            return {
                "text": "\n\n".join(all_text),
                "pages": page_contents,
                "metadata": {
                    "total_pages": total_pages,
                    "model": result.get("model", "mistral-ocr-latest")
                }
            }
            
        except Exception as e:
            logger.error(f"Structured Mistral OCR failed: {str(e)}")
            raise


# Singleton instance
_mistral_ocr_service: Optional[MistralOCRService] = None


def get_mistral_ocr_service() -> MistralOCRService:
    """Get singleton instance of Mistral OCR service."""
    global _mistral_ocr_service
    if _mistral_ocr_service is None:
        _mistral_ocr_service = MistralOCRService()
    return _mistral_ocr_service
