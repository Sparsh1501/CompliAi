from PyPDF2 import PdfReader
import os
import re
import uuid
from typing import List, Dict, Any, Tuple
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Clause
import logging

# Import python-docx for DOCX support
try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Import Anthropic Document Service (primary OCR using Claude Vision)
try:
    from services.anthropic_document_service import AnthropicDocumentService, get_anthropic_document_service
    ANTHROPIC_OCR_AVAILABLE = True
except ImportError:
    ANTHROPIC_OCR_AVAILABLE = False

# Import Mistral OCR Service (fallback OCR for scanned PDFs)
try:
    from services.mistral_ocr_service import MistralOCRService, get_mistral_ocr_service
    MISTRAL_OCR_AVAILABLE = True
except ImportError:
    MISTRAL_OCR_AVAILABLE = False

# Fallback: Try to import pdf2image for local processing
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self, upload_dir: str = "/tmp/claude/uploads"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
        
        # Patterns for identifying clause headers and section markers
        self.section_patterns = [
            # Numbered sections: 1., 1.1, 1.1.1, etc.
            r'^(\d+(?:\.\d+)*)\s*[.:\-]?\s+(.+)',
            # Roman numerals: I., II., III., etc.
            r'^([IVXLCDM]+)\s*[.:\-]?\s+(.+)',
            # Letter sections: a., b., A., B., etc.
            r'^([a-zA-Z])\s*[.:\)]\s+(.+)',
            # Article/Section/Clause headers
            r'^(Article|Section|Clause|Part|Chapter)\s+(\d+(?:\.\d+)*)[:\-]?\s*(.*)',
            # Policy specific patterns
            r'^(\d+(?:\.\d+)*)\s+(Purpose|Scope|Objective|Policy|Procedure|Responsibility|Definition|Compliance|Monitoring|Review|Appendix|Annexure)\b',
        ]
        
        # Keywords that typically start a new clause
        self.clause_starters = [
            'shall', 'must', 'should', 'will', 'may', 'is required to',
            'is responsible for', 'the bank', 'the company', 'the organization',
            'all employees', 'management', 'compliance officer'
        ]
    
    async def save_file(self, file_content: bytes, filename: str) -> str:
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(filename)[1]
        new_filename = f"{file_id}{file_extension}"
        filepath = os.path.join(self.upload_dir, new_filename)

        with open(filepath, 'wb') as f:
            f.write(file_content)

        return filepath

    async def extract_text(self, filepath: str) -> str:
        """
        Universal text extraction method that detects file type and calls appropriate extractor.
        Supports: PDF, DOCX, TXT
        """
        file_extension = os.path.splitext(filepath)[1].lower()

        if file_extension == '.pdf':
            return await self.extract_text_from_pdf(filepath)
        elif file_extension in ['.docx', '.doc']:
            if file_extension == '.doc':
                logger.warning("Legacy .doc format detected. Only .docx is fully supported. Results may vary.")
            return await self.extract_text_from_docx(filepath)
        elif file_extension == '.txt':
            return await self.extract_text_from_txt(filepath)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}. Supported formats: PDF, DOCX, TXT")
    
    async def extract_text_from_pdf(self, filepath: str) -> str:
        import time
        start_time = time.time()
        
        try:
            logger.info("="*60)
            logger.info("[PDF TEXT EXTRACTION - START]")
            logger.info(f"  File: {filepath}")
            logger.info(f"  File Size: {os.path.getsize(filepath)} bytes")
            
            reader = PdfReader(filepath)
            total_pages = len(reader.pages)
            logger.info(f"  Total Pages: {total_pages}")
            
            # Primary: Use Anthropic Claude Vision for ALL PDFs (handles both digital & scanned)
            if ANTHROPIC_OCR_AVAILABLE:
                logger.info("  Using Anthropic Claude Vision as primary text extractor...")
                try:
                    text = await self._extract_text_with_anthropic(filepath)
                    if text and len(re.sub(r'\s+', '', text)) > 100:
                        total_time = time.time() - start_time
                        logger.info(f"  Anthropic extracted {len(text)} chars in {total_time:.2f}s")
                        logger.info(f"[PDF TEXT EXTRACTION - COMPLETE] Total time: {total_time:.2f}s")
                        logger.info("="*60)
                        return text
                    else:
                        logger.warning(f"  Anthropic returned insufficient text, falling back to PyPDF2...")
                except Exception as e:
                    logger.error(f"  Anthropic extraction failed: {e}, falling back to PyPDF2...")
            
            # Fallback: PyPDF2 for digital PDFs (free, no API cost)
            logger.info("  Falling back to PyPDF2 extraction...")
            text = ""
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n[PAGE_{page_num}]\n{page_text}\n"
                    logger.info(f"  Page {page_num}: Extracted {len(page_text)} chars")
                else:
                    logger.info(f"  Page {page_num}: No text extracted (possibly scanned)")
            
            elapsed_time = time.time() - start_time
            logger.info(f"  PyPDF2 Total Extracted: {len(text)} chars in {elapsed_time:.2f}s")
            
            # Check if PyPDF2 got meaningful text
            clean_text = re.sub(r'\s+', '', text)
            logger.info(f"  Clean Text Length (no whitespace): {len(clean_text)} chars")
            
            if len(clean_text) < 100:
                logger.warning(f"  PyPDF2 extracted little/no text ({len(clean_text)} chars). PDF might be scanned.")
                # Last resort: Mistral OCR
                if MISTRAL_OCR_AVAILABLE:
                    logger.info("  Attempting Mistral OCR as last resort...")
                    text = await self._extract_text_with_mistral(filepath)
                else:
                    logger.warning("  No fallback OCR available.")
            
            total_time = time.time() - start_time
            logger.info(f"[PDF TEXT EXTRACTION - COMPLETE] Total time: {total_time:.2f}s")
            logger.info("="*60)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            raise
    
    async def _extract_text_with_anthropic(self, filepath: str) -> str:
        """Extract text from scanned PDF using Anthropic Claude Vision API (primary OCR).
        
        Uses Claude Vision to read document images with full context understanding.
        Same vendor as clause extraction for consistent quality.
        """
        try:
            anthropic_service = get_anthropic_document_service()
            text = await anthropic_service.extract_text_from_pdf(filepath)
            logger.info(f"Anthropic Claude Vision OCR extracted {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"Anthropic Claude Vision OCR failed: {str(e)}")
            # Fall back to Mistral OCR if Anthropic fails
            if MISTRAL_OCR_AVAILABLE:
                logger.info("Falling back to Mistral OCR after Anthropic failure...")
                return await self._extract_text_with_mistral(filepath)
            return ""

    async def _extract_text_with_mistral(self, filepath: str) -> str:
        """Extract text from scanned PDF using Mistral OCR API (fallback)"""
        try:
            mistral_service = get_mistral_ocr_service()
            text = await mistral_service.extract_text_from_pdf(filepath)
            logger.info(f"Mistral OCR extracted {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"Mistral OCR extraction failed: {str(e)}")
            return ""

    async def extract_text_from_docx(self, filepath: str) -> str:
        """Extract text from DOCX file"""
        import time
        start_time = time.time()

        try:
            logger.info("="*60)
            logger.info("[DOCX TEXT EXTRACTION - START]")
            logger.info(f"  File: {filepath}")
            logger.info(f"  File Size: {os.path.getsize(filepath)} bytes")

            if not DOCX_AVAILABLE:
                raise ImportError("python-docx library not available. Install with: pip install python-docx")

            doc = DocxDocument(filepath)

            text = ""
            page_num = 1  # DOCX doesn't have page numbers, but we'll simulate them
            para_count = 0

            for para in doc.paragraphs:
                para_text = para.text.strip()
                if para_text:
                    # Add simulated page marker every ~50 paragraphs
                    if para_count % 50 == 0 and para_count > 0:
                        page_num += 1
                        text += f"\n[PAGE_{page_num}]\n"

                    text += para_text + "\n"
                    para_count += 1

            # Extract text from tables as well
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        text += row_text + "\n"

            elapsed_time = time.time() - start_time
            logger.info(f"  Total Paragraphs: {para_count}")
            logger.info(f"  Total Tables: {len(doc.tables)}")
            logger.info(f"  Total Extracted: {len(text)} chars in {elapsed_time:.2f}s")
            logger.info("[DOCX TEXT EXTRACTION - COMPLETE]")
            logger.info("="*60)

            return text
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {str(e)}")
            raise

    async def extract_text_from_txt(self, filepath: str) -> str:
        """Extract text from TXT file"""
        import time
        start_time = time.time()

        try:
            logger.info("="*60)
            logger.info("[TXT TEXT EXTRACTION - START]")
            logger.info(f"  File: {filepath}")
            logger.info(f"  File Size: {os.path.getsize(filepath)} bytes")

            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            text = None

            for encoding in encodings:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        text = f.read()
                    logger.info(f"  Successfully read with encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue

            if text is None:
                raise ValueError("Could not decode text file with any supported encoding")

            # Add page markers every ~2000 characters to simulate pages
            lines = text.split('\n')
            formatted_text = ""
            char_count = 0
            page_num = 1

            for line in lines:
                if char_count > 2000 and page_num < 100:  # Add page markers
                    formatted_text += f"\n[PAGE_{page_num}]\n"
                    page_num += 1
                    char_count = 0
                formatted_text += line + "\n"
                char_count += len(line)

            elapsed_time = time.time() - start_time
            logger.info(f"  Total Lines: {len(lines)}")
            logger.info(f"  Total Extracted: {len(formatted_text)} chars in {elapsed_time:.2f}s")
            logger.info("[TXT TEXT EXTRACTION - COMPLETE]")
            logger.info("="*60)

            return formatted_text
        except Exception as e:
            logger.error(f"Error extracting TXT text: {str(e)}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace while preserving paragraph breaks
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _is_section_header(self, line: str) -> Tuple[bool, str, str]:
        """Check if a line is a section header and extract section info"""
        line = line.strip()
        if not line or len(line) > 200:  # Headers are usually short
            return False, "", ""
        
        for pattern in self.section_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                section_id = groups[0] if groups else ""
                section_title = groups[-1] if len(groups) > 1 else line
                return True, section_id, section_title.strip()
        
        # Check for all-caps headers (common in policy documents)
        if line.isupper() and len(line) > 3 and len(line) < 100:
            return True, "", line
        
        return False, "", ""
    
    def _is_clause_content(self, text: str) -> bool:
        """Check if text contains substantive clause content"""
        if not text or len(text) < 30:
            return False
        
        # Check for clause starter keywords
        text_lower = text.lower()
        for starter in self.clause_starters:
            if starter in text_lower:
                return True
        
        # Check for policy language patterns
        policy_patterns = [
            r'\b(comply|compliance|requirement|mandatory|prohibited)\b',
            r'\b(ensure|maintain|establish|implement|monitor)\b',
            r'\b(policy|procedure|guideline|standard|control)\b',
            r'\b(risk|audit|review|approval|authorization)\b',
        ]
        for pattern in policy_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return len(text) > 100  # Accept longer paragraphs as potential clauses
    
    def _extract_page_number(self, text_before: str) -> int:
        """Extract page number from preceding text"""
        matches = re.findall(r'\[PAGE_(\d+)\]', text_before)
        return int(matches[-1]) if matches else 1
    
    async def extract_clauses_simple(self, text: str, document_type: str = "policy") -> List[Dict[str, Any]]:
        """Extract clauses from document text with improved logic for proper clause identification"""
        if not text or len(text.strip()) < 50:
            logger.warning("Text too short for clause extraction")
            return []
        
        text = self._clean_text(text)
        lines = text.split('\n')
        
        clauses = []
        current_section = "Introduction"
        current_section_id = ""
        current_clause_text = []
        current_page = 1
        clause_start_page = 1
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Track page numbers
            page_match = re.match(r'\[PAGE_(\d+)\]', line)
            if page_match:
                current_page = int(page_match.group(1))
                continue
            
            # Skip empty lines but use them as potential clause boundaries
            if not line:
                if current_clause_text:
                    clause_text = ' '.join(current_clause_text).strip()
                    if self._is_clause_content(clause_text):
                        clause = self._create_clause(
                            clause_text, 
                            current_section, 
                            current_section_id,
                            clause_start_page,
                            document_type,
                            len(clauses) + 1
                        )
                        clauses.append(clause)
                    current_clause_text = []
                    clause_start_page = current_page
                continue
            
            # Check for section headers
            is_header, section_id, section_title = self._is_section_header(line)
            if is_header:
                # Save previous clause if exists
                if current_clause_text:
                    clause_text = ' '.join(current_clause_text).strip()
                    if self._is_clause_content(clause_text):
                        clause = self._create_clause(
                            clause_text,
                            current_section,
                            current_section_id,
                            clause_start_page,
                            document_type,
                            len(clauses) + 1
                        )
                        clauses.append(clause)
                    current_clause_text = []
                
                # Update current section
                current_section = section_title if section_title else line
                current_section_id = section_id
                clause_start_page = current_page
                continue
            
            # Check if this line starts a new clause (numbered sub-items)
            sub_item_match = re.match(r'^([a-z]|[ivx]+|\d+)\s*[.)\]]\s+(.+)', line, re.IGNORECASE)
            if sub_item_match and current_clause_text:
                # Save previous clause
                clause_text = ' '.join(current_clause_text).strip()
                if self._is_clause_content(clause_text):
                    clause = self._create_clause(
                        clause_text,
                        current_section,
                        current_section_id,
                        clause_start_page,
                        document_type,
                        len(clauses) + 1
                    )
                    clauses.append(clause)
                current_clause_text = [line]
                clause_start_page = current_page
            else:
                # Accumulate clause text
                current_clause_text.append(line)
        
        # Don't forget the last clause
        if current_clause_text:
            clause_text = ' '.join(current_clause_text).strip()
            if self._is_clause_content(clause_text):
                clause = self._create_clause(
                    clause_text,
                    current_section,
                    current_section_id,
                    clause_start_page,
                    document_type,
                    len(clauses) + 1
                )
                clauses.append(clause)
        
        # If we extracted too few clauses, fall back to paragraph-based extraction
        if len(clauses) < 3:
            logger.info("Few clauses found with structure-based extraction, using paragraph fallback")
            clauses = await self._extract_clauses_by_paragraphs(text, document_type)
        
        logger.info(f"Extracted {len(clauses)} clauses from {document_type}")
        return clauses[:150]  # Limit to 150 clauses
    
    def _create_clause(self, text: str, section: str, section_id: str, page: int, doc_type: str, index: int) -> Dict[str, Any]:
        """Create a clause dictionary with proper structure"""
        # Clean the text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Determine clause type based on content
        clause_type = self._determine_clause_type(text)
        
        return {
            "clause_id": str(uuid.uuid4()),
            "text": text[:3000],  # Allow up to 3000 chars per clause
            "section": f"{section_id} {section}".strip() if section_id else section,
            "page_number": page,
            "metadata": {
                "type": doc_type,
                "clause_type": clause_type,
                "length": len(text),
                "index": index,
                "has_requirements": any(kw in text.lower() for kw in ['shall', 'must', 'required'])
            }
        }
    
    def _determine_clause_type(self, text: str) -> str:
        """Determine the type of clause based on its content"""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ['purpose', 'objective', 'aim']):
            return "purpose"
        elif any(kw in text_lower for kw in ['scope', 'applicability', 'applies to']):
            return "scope"
        elif any(kw in text_lower for kw in ['definition', 'means', 'refers to']):
            return "definition"
        elif any(kw in text_lower for kw in ['responsibility', 'responsible', 'accountable']):
            return "responsibility"
        elif any(kw in text_lower for kw in ['procedure', 'process', 'steps']):
            return "procedure"
        elif any(kw in text_lower for kw in ['shall', 'must', 'mandatory', 'required']):
            return "requirement"
        elif any(kw in text_lower for kw in ['prohibited', 'not allowed', 'forbidden']):
            return "prohibition"
        elif any(kw in text_lower for kw in ['review', 'monitor', 'audit']):
            return "review"
        elif any(kw in text_lower for kw in ['exception', 'exemption', 'waiver']):
            return "exception"
        else:
            return "general"
    
    async def _extract_clauses_by_paragraphs(self, text: str, document_type: str) -> List[Dict[str, Any]]:
        """Fallback method: extract clauses based on paragraph breaks"""
        # Remove page markers for cleaner splitting
        clean_text = re.sub(r'\[PAGE_\d+\]', '', text)
        
        # Split by double newlines
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', clean_text) if p.strip()]
        
        # If that doesn't work well, try single newlines with sentence detection
        if len(paragraphs) < 5:
            # Split by sentences that end with period and start with capital
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', clean_text)
            paragraphs = []
            current_para = []
            for sent in sentences:
                current_para.append(sent)
                if len(' '.join(current_para)) > 200:
                    paragraphs.append(' '.join(current_para))
                    current_para = []
            if current_para:
                paragraphs.append(' '.join(current_para))
        
        clauses = []
        for idx, para in enumerate(paragraphs):
            if len(para) > 50 and self._is_clause_content(para):
                clause = self._create_clause(
                    para,
                    f"Section {idx + 1}",
                    str(idx + 1),
                    1,
                    document_type,
                    idx + 1
                )
                clauses.append(clause)
        
        return clauses
