import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.multi_llm_service_new import MultiLLMService
from typing import Dict, Any, Optional
import logging
import hashlib
import anthropic
import base64
import PyPDF2
from pdf2image import convert_from_path
from PIL import Image
import io

logger = logging.getLogger(__name__)

class EvidenceService:
    def __init__(self):
        self.llm_service = MultiLLMService()
        # Initialize Anthropic client - temporarily unset proxy env vars to avoid SOCKS issues
        # Save original proxy settings
        http_proxy_backup = os.environ.get('HTTP_PROXY')
        https_proxy_backup = os.environ.get('HTTPS_PROXY')
        all_proxy_backup = os.environ.get('ALL_PROXY')

        # Temporarily unset proxies
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('ALL_PROXY', None)
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)
        os.environ.pop('all_proxy', None)

        try:
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.getenv('ANTHROPIC_API_KEY')
            )
        finally:
            # Restore proxy settings
            if http_proxy_backup:
                os.environ['HTTP_PROXY'] = http_proxy_backup
            if https_proxy_backup:
                os.environ['HTTPS_PROXY'] = https_proxy_backup
            if all_proxy_backup:
                os.environ['ALL_PROXY'] = all_proxy_backup
    
    async def evaluate_evidence(self, file_path: str, requirement: str) -> Dict[str, Any]:
        """Evaluate evidence file and provide AI scoring"""
        result = await self.llm_service.evaluate_evidence_gemini(file_path, requirement)
        
        return {
            "compliance_score": result.get('score', 0),
            "validation_status": self._determine_status(result.get('score', 0)),
            "feedback_good": result.get('strengths', []),
            "feedback_improvements": result.get('gaps', []),
            "ai_validation_notes": result.get('assessment', ''),
            "suggestions": result.get('suggestions', [])
        }
    
    def _determine_status(self, score: float) -> str:
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Acceptable"
        elif score >= 40:
            return "Needs Improvement"
        else:
            return "Inadequate"

    def compute_sha256(self, file_content: bytes) -> str:
        """Compute SHA-256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()

    async def extract_fields_with_ocr(self, file_path: str, file_content: bytes, mime_type: str) -> Dict[str, Any]:
        """
        Extract structured fields from document using Claude Vision OCR.
        Returns: {
            'ocr_text': str,
            'extracted_fields': {
                'dates': [...],
                'names': [...],
                'amounts': [...],
                'signatures_present': bool
            }
        }
        """
        try:
            # Prepare document for Claude Vision
            image_data = None

            if mime_type == 'application/pdf':
                # Convert first page of PDF to image
                images = convert_from_path(file_path, first_page=1, last_page=1)
                if images:
                    # Convert PIL image to bytes
                    img_byte_arr = io.BytesIO()
                    images[0].save(img_byte_arr, format='PNG')
                    image_data = base64.standard_b64encode(img_byte_arr.getvalue()).decode('utf-8')
            elif mime_type.startswith('image/'):
                # Use image directly
                image_data = base64.standard_b64encode(file_content).decode('utf-8')

            if not image_data:
                logger.warning(f"Could not convert file to image for OCR: {file_path}")
                return {
                    'ocr_text': '',
                    'extracted_fields': {
                        'dates': [],
                        'names': [],
                        'amounts': [],
                        'signatures_present': False
                    }
                }

            # Use Claude Vision to extract text and structured fields
            prompt = """Analyze this document image and extract:

1. Full OCR text (all visible text in the document)
2. Structured fields:
   - All dates mentioned (format: list of dates)
   - All person/organization names (format: list of names)
   - All monetary amounts (format: list of amounts with currency)
   - Whether signatures are present (yes/no)

Provide the response in this exact JSON format:
{
  "ocr_text": "full extracted text here",
  "dates": ["date1", "date2"],
  "names": ["name1", "name2"],
  "amounts": ["amount1", "amount2"],
  "signatures_present": true/false
}"""

            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            # Parse Claude response
            import json
            response_text = message.content[0].text

            # Try to extract JSON from response
            try:
                # Look for JSON in the response
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end > start:
                    json_str = response_text[start:end]
                    result = json.loads(json_str)

                    return {
                        'ocr_text': result.get('ocr_text', ''),
                        'extracted_fields': {
                            'dates': result.get('dates', []),
                            'names': result.get('names', []),
                            'amounts': result.get('amounts', []),
                            'signatures_present': result.get('signatures_present', False)
                        }
                    }
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON from Claude response: {response_text}")

            # Fallback: return raw text as OCR
            return {
                'ocr_text': response_text,
                'extracted_fields': {
                    'dates': [],
                    'names': [],
                    'amounts': [],
                    'signatures_present': False
                }
            }

        except Exception as e:
            logger.error(f"Error in OCR extraction: {str(e)}")
            return {
                'ocr_text': '',
                'extracted_fields': {
                    'dates': [],
                    'names': [],
                    'amounts': [],
                    'signatures_present': False
                }
            }

    async def validate_evidence_with_confidence(
        self,
        evidence_doc: Dict[str, Any],
        requirement: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Feature #55: AI validation with confidence-based routing.
        Returns: {
            'validation_status': 'auto_approved' | 'pending_human_review' | 'failed',
            'confidence': float (0.0-1.0),
            'explanation': str,
            'ai_score': float (0-100),
            'pass': bool
        }
        """
        try:
            # Use OCR text if available, otherwise use file path
            ocr_text = evidence_doc.get('ocr_text', '')
            file_path = evidence_doc.get('file_url', '')

            # Default requirement if not provided
            if not requirement:
                requirement = "Verify that this document provides valid evidence of compliance."

            # Build prompt for Claude to validate evidence
            prompt = f"""You are a compliance validation AI. Analyze this evidence document and provide:

1. A pass/fail decision (does this evidence satisfy the requirement?)
2. A confidence score (0.0-1.0) indicating how certain you are
3. A compliance score (0-100) indicating quality of evidence
4. An explanation of your decision
5. **Audit notes** - A concise summary for auditors (2-3 sentences) describing:
   - What evidence was provided
   - How it addresses the clause requirement
   - Key findings or observations

Requirement: {requirement}

Document OCR Text:
{ocr_text[:2000] if ocr_text else '[No OCR text available]'}

Extracted Fields: {evidence_doc.get('extracted_fields', {})}

Provide response in JSON format:
{{
  "pass": true/false,
  "confidence": 0.0-1.0,
  "compliance_score": 0-100,
  "explanation": "detailed explanation here",
  "audit_notes": "Concise 2-3 sentence summary for auditor review",
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"]
}}"""

            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            import json
            response_text = message.content[0].text

            # Extract JSON
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                result = json.loads(json_str)

                confidence = float(result.get('confidence', 0.5))
                ai_pass = result.get('pass', False)
                compliance_score = int(result.get('compliance_score', 0))
                explanation = result.get('explanation', '')
                audit_notes = result.get('audit_notes', '')  # Feature #172

                # Confidence-based routing (Feature #55)
                if confidence >= 0.85 and ai_pass:
                    validation_status = 'auto_approved'
                elif confidence >= 0.50:
                    validation_status = 'pending_human_review'
                else:
                    validation_status = 'failed'

                return {
                    'validation_status': validation_status,
                    'confidence': confidence,
                    'ai_score': compliance_score,
                    'pass': ai_pass,
                    'explanation': explanation,
                    'audit_notes': audit_notes,  # Feature #172
                    'strengths': result.get('strengths', []),
                    'weaknesses': result.get('weaknesses', [])
                }

            # Fallback if JSON parsing fails
            logger.warning(f"Could not parse validation JSON: {response_text}")
            return {
                'validation_status': 'pending_human_review',
                'confidence': 0.5,
                'ai_score': 50,
                'pass': False,
                'explanation': 'AI validation incomplete - requires human review',
                'strengths': [],
                'weaknesses': []
            }

        except Exception as e:
            logger.error(f"Error in AI validation: {str(e)}")
            return {
                'validation_status': 'failed',
                'confidence': 0.0,
                'ai_score': 0,
                'pass': False,
                'explanation': f'Validation error: {str(e)}',
                'strengths': [],
                'weaknesses': []
            }
