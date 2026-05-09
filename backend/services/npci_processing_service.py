"""
NPCI Circular PDF Text Extraction and Clause Analysis Service
Feature #216: Processing pipeline for NPCI circulars.

Pipeline: download PDF -> extract text (PyPDF2 + Claude Vision fallback) ->
LLM clause extraction -> store clauses in MongoDB + Qdrant embeddings.

Uses llm_provider.py abstraction to respect global LLM toggle (USE_LOCAL_LLM).
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file using PyPDF2.
    Falls back to basic text if extraction fails.

    Args:
        pdf_path: Local filesystem path to PDF

    Returns:
        Extracted text content
    """
    if not pdf_path or not os.path.exists(pdf_path):
        logger.warning(f"PDF not found at path: {pdf_path}")
        return ""

    try:
        import PyPDF2
        text_parts = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(page_text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")

        full_text = "\n\n".join(text_parts)

        if full_text.strip():
            logger.info(f"Extracted {len(full_text)} chars from PDF: {pdf_path}")
            return full_text
        else:
            logger.warning(f"No text extracted from PDF (may be scanned): {pdf_path}")
            return ""

    except Exception as e:
        logger.error(f"PyPDF2 extraction failed for {pdf_path}: {e}")
        return ""


async def extract_text_with_vision_fallback(pdf_path: str, db=None) -> str:
    """
    Extract text from PDF using PyPDF2 first, then fallback to LLM
    (local or Claude Vision) for scanned/empty PDFs.

    Args:
        pdf_path: Local filesystem path to PDF
        db: Optional MongoDB database for cost logging

    Returns:
        Extracted text content
    """
    # Try PyPDF2 first
    text = extract_text_from_pdf(pdf_path)
    if text and len(text.strip()) > 100:
        return text

    logger.info(f"PDF text extraction insufficient, attempting LLM fallback for: {pdf_path}")
    try:
        from services.llm_provider import get_llm_provider, is_using_local_llm, log_llm_cost
        import base64

        if not os.path.exists(pdf_path):
            return text or ""

        # Read PDF bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        if is_using_local_llm():
            # Local LLM fallback: try harder with PyPDF2 (extract all pages raw),
            # then ask local LLM to clean up / interpret the raw content
            logger.info("Using local LLM fallback for PDF text extraction")

            raw_fragments = _extract_raw_pdf_fragments(pdf_path)

            if raw_fragments and len(raw_fragments.strip()) > 30:
                # We got some raw text — ask local LLM to clean it up
                provider = get_llm_provider()
                try:
                    cleaned = await provider.generate(
                        system="You are a document text extraction assistant. Given raw/garbled text extracted from a scanned NPCI (National Payments Corporation of India) circular PDF, clean it up and reconstruct the readable content. Preserve the original meaning and structure. Return ONLY the cleaned text, no commentary.",
                        prompt=f"Clean up and reconstruct this raw PDF text:\n\n{raw_fragments[:6000]}",
                        max_tokens=4096,
                        temperature=0.2,
                    )
                    if cleaned and len(cleaned.strip()) > 50:
                        logger.info(f"Local LLM cleaned {len(cleaned)} chars from raw PDF fragments")
                        if db is not None:
                            await log_llm_cost(db=db, provider="ollama", operation="npci_pdf_text_cleanup")
                        return cleaned
                except Exception as e:
                    logger.warning(f"Local LLM text cleanup failed: {e}")

            # If no raw text at all, try OCR-like extraction with different strategies
            ocr_text = _extract_pdf_with_alternate_methods(pdf_path)
            if ocr_text and len(ocr_text.strip()) > 50:
                provider = get_llm_provider()
                try:
                    cleaned = await provider.generate(
                        system="You are a document text extraction assistant. Given raw text extracted from an NPCI circular PDF, clean it up into readable content. Return ONLY the cleaned text.",
                        prompt=f"Clean up this extracted text:\n\n{ocr_text[:6000]}",
                        max_tokens=4096,
                        temperature=0.2,
                    )
                    if cleaned and len(cleaned.strip()) > 50:
                        logger.info(f"Local LLM cleaned alternate extraction: {len(cleaned)} chars")
                        if db is not None:
                            await log_llm_cost(db=db, provider="ollama", operation="npci_pdf_ocr_cleanup")
                        return cleaned
                except Exception as e:
                    logger.warning(f"Local LLM alternate cleanup failed: {e}")

            return raw_fragments or text or ""

        else:
            # Cloud LLM: Use Claude Vision API for scanned PDFs
            from anthropic import AsyncAnthropic
            api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('EMERGENT_LLM_KEY')
            if not api_key:
                return text or ""

            client = AsyncAnthropic(api_key=api_key)
            pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all text from this NPCI circular PDF. Return the complete text content preserving the structure and formatting as much as possible."
                    }
                ]
            }],
        )

        vision_text = response.content[0].text if response.content else ""
        if vision_text and len(vision_text.strip()) > 50:
            logger.info(f"Vision API extracted {len(vision_text)} chars from scanned PDF")

            # Log cost
            if db is not None:
                await log_llm_cost(
                    db=db,
                    provider="claude",
                    operation="npci_pdf_vision_extraction",
                    input_tokens=response.usage.input_tokens if hasattr(response, 'usage') else 0,
                    output_tokens=response.usage.output_tokens if hasattr(response, 'usage') else 0,
                    model="claude-sonnet-4-20250514",
                )

            return vision_text

    except Exception as e:
        logger.warning(f"LLM fallback failed: {e}")

    return text or ""


def _extract_raw_pdf_fragments(pdf_path: str) -> str:
    """
    Extract raw text fragments from PDF using multiple PyPDF2 strategies.
    Tries to get any text possible, even if garbled.
    """
    fragments = []
    try:
        import PyPDF2
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    # Standard extraction
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        fragments.append(page_text)
                except Exception:
                    pass
                # Try extracting annotations/form fields
                try:
                    if page.get("/Annots"):
                        for annot in page["/Annots"]:
                            annot_obj = annot.get_object()
                            if "/Contents" in annot_obj:
                                fragments.append(str(annot_obj["/Contents"]))
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Raw PDF fragment extraction failed: {e}")

    return "\n\n".join(fragments)


def _extract_pdf_with_alternate_methods(pdf_path: str) -> str:
    """
    Try alternate PDF text extraction methods (pdfminer, pdfplumber if available).
    """
    text = ""

    # Try pdfplumber (often better for tables/scanned text)
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            parts = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    parts.append(page_text)
            text = "\n\n".join(parts)
            if text.strip():
                logger.info(f"pdfplumber extracted {len(text)} chars")
                return text
    except ImportError:
        logger.debug("pdfplumber not available, skipping")
    except Exception as e:
        logger.debug(f"pdfplumber failed: {e}")

    # Try pdfminer
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(pdf_path)
        if text and len(text.strip()) > 50:
            logger.info(f"pdfminer extracted {len(text)} chars")
            return text
    except ImportError:
        logger.debug("pdfminer not available, skipping")
    except Exception as e:
        logger.debug(f"pdfminer failed: {e}")

    return text


def parse_circular_title(title: str) -> Dict[str, str]:
    """
    Parse NPCI circular title to extract OC number, FY year, and description.

    Examples:
        "OC-163/2024-25: Guidelines for UPI Transaction Limits"
        -> {"oc_number": "OC-163", "fy_year": "2024-25", "description": "Guidelines for UPI Transaction Limits"}

    Args:
        title: Circular title string

    Returns:
        Dict with oc_number, fy_year, description
    """
    result = {"oc_number": "", "fy_year": "", "description": title}

    if not title:
        return result

    # Try to extract OC number (e.g., "OC-163" or "OC No. 163")
    oc_match = re.search(r'(OC[\s-]*(?:No\.?\s*)?[\d]+)', title, re.IGNORECASE)
    if oc_match:
        result["oc_number"] = oc_match.group(1).strip()

    # Try to extract FY year (e.g., "2024-25" or "FY 2024-25")
    fy_match = re.search(r'(\d{4}[-/]\d{2,4})', title)
    if fy_match:
        result["fy_year"] = fy_match.group(1)

    # Extract description (everything after the OC/FY prefix)
    desc_match = re.search(r'(?:OC[\s-]*(?:No\.?\s*)?[\d]+[/\s]*\d{4}[-/]\d{2,4}\s*:?\s*)(.*)', title, re.IGNORECASE)
    if desc_match:
        result["description"] = desc_match.group(1).strip()
    elif ":" in title:
        result["description"] = title.split(":", 1)[1].strip()

    return result


class NPCIProcessingService:
    """
    Service for processing NPCI circular PDFs with text extraction
    and LLM-based clause analysis.
    """

    def __init__(self, db, qdrant_client=None):
        """
        Initialize the processing service.

        Args:
            db: MongoDB database instance
            qdrant_client: Optional Qdrant client for embeddings
        """
        self.db = db
        self.qdrant_client = qdrant_client
        self.circulars_collection = db["npci_circulars"]
        self.clauses_collection = db["npci_circular_clauses"]

    async def ensure_indexes(self):
        """Create MongoDB indexes for the clauses collection."""
        try:
            await self.clauses_collection.create_index("circular_id")
            await self.clauses_collection.create_index([("circular_id", 1), ("clause_id", 1)], unique=True, sparse=True)
            await self.clauses_collection.create_index("product")
            await self.clauses_collection.create_index("clause_type")
            await self.clauses_collection.create_index([("clause_text", "text")])
            logger.info("NPCI circular clauses indexes created")
        except Exception as e:
            logger.warning(f"Error creating NPCI clause indexes: {e}")

    async def process_circular(self, circular_id: str) -> Dict[str, Any]:
        """
        Full processing pipeline for a single circular:
        1. Download PDF if needed
        2. Extract text (PyPDF2 + Vision fallback)
        3. LLM clause extraction
        4. Store clauses in MongoDB
        5. Generate Qdrant embeddings (if available)
        6. Update circular status

        Args:
            circular_id: MongoDB _id of the circular

        Returns:
            Processing result dict
        """
        from bson import ObjectId

        # Get circular
        circular = await self.circulars_collection.find_one({"_id": ObjectId(circular_id)})
        if not circular:
            return {"success": False, "error": "Circular not found"}

        result = {
            "circular_id": circular_id,
            "npci_id": circular.get("npci_id"),
            "title": circular.get("title", ""),
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        # Update status to processing
        await self.circulars_collection.update_one(
            {"_id": ObjectId(circular_id)},
            {"$set": {"processing_status": "processing"}}
        )

        try:
            # Step 1: Download PDF if not already downloaded
            if not circular.get("pdf_downloaded") and circular.get("pdf_url"):
                from services.npci_scraper_service import NPCIScraper
                pdf_path = await self._download_pdf(circular["pdf_url"], circular.get("npci_id"))
                if pdf_path:
                    circular["local_pdf_path"] = pdf_path
                    circular["pdf_downloaded"] = True
                    await self.circulars_collection.update_one(
                        {"_id": ObjectId(circular_id)},
                        {"$set": {"pdf_downloaded": True, "local_pdf_path": pdf_path}}
                    )

            # Step 2: Extract text from PDF
            raw_text = ""
            if circular.get("local_pdf_path"):
                raw_text = await extract_text_with_vision_fallback(
                    circular["local_pdf_path"], db=self.db
                )

            if not raw_text:
                raw_text = circular.get("title", "No text available")

            result["text_length"] = len(raw_text)

            # Step 3: Parse circular title
            title_info = parse_circular_title(circular.get("title", ""))
            result["parsed_title"] = title_info

            # Step 4: LLM clause extraction
            clauses = await self._extract_clauses_with_llm(
                raw_text, circular.get("title", ""),
                circular.get("product", ""), circular.get("year", "")
            )
            result["clauses_extracted"] = len(clauses)

            # Step 5: Store clauses in MongoDB
            stored_clause_ids = await self._store_clauses(
                clauses, circular_id, circular
            )
            result["clauses_stored"] = len(stored_clause_ids)

            # Step 6: Generate Qdrant embeddings (if available)
            embeddings_stored = 0
            if self.qdrant_client and clauses:
                embeddings_stored = await self._store_embeddings(clauses, circular)
            result["embeddings_stored"] = embeddings_stored

            # Step 7: Update circular document
            await self.circulars_collection.update_one(
                {"_id": ObjectId(circular_id)},
                {"$set": {
                    "raw_text": raw_text,
                    "clauses": clauses,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "processing_status": "completed",
                    "parsed_title": title_info,
                    "clause_count": len(clauses),
                }}
            )

            # Step 8: Auto-convert to Regulation with full intelligence pipeline
            try:
                reg_result = await self._convert_circular_to_regulation(
                    circular=circular,
                    circular_id=circular_id,
                    raw_text=raw_text,
                    title_info=title_info,
                )
                result["regulation_id"] = reg_result.get("regulation_id")
                result["regulation_clauses"] = reg_result.get("clauses_count", 0)
                logger.info(f"[NPCI→REG] Converted circular {circular_id} to regulation {reg_result.get('regulation_id')}")
            except Exception as e:
                logger.error(f"[NPCI→REG] Failed to convert circular {circular_id} to regulation: {e}", exc_info=True)
                # Don't fail the whole processing — circular is still saved

            result["status"] = "completed"
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            result["success"] = True

        except Exception as e:
            logger.error(f"Processing failed for circular {circular_id}: {e}", exc_info=True)
            result["status"] = "failed"
            result["error"] = str(e)
            result["success"] = False

            await self.circulars_collection.update_one(
                {"_id": ObjectId(circular_id)},
                {"$set": {
                    "processing_status": "failed",
                    "processing_error": str(e),
                }}
            )

        return result

    async def _download_pdf(self, pdf_url: str, npci_id: int = None) -> Optional[str]:
        """Download a PDF from NPCI."""
        import httpx

        upload_dir = "/tmp/uploads/npci"
        os.makedirs(upload_dir, exist_ok=True)

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(pdf_url, headers={
                    "User-Agent": "CompliAI/1.0",
                    "Referer": "https://www.npci.org.in/",
                })
                response.raise_for_status()

                filename = f"npci_circular_{npci_id or uuid.uuid4().hex[:8]}.pdf"
                filepath = os.path.join(upload_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(response.content)

                return filepath
        except Exception as e:
            logger.error(f"Failed to download PDF from {pdf_url}: {e}")
            return None

    async def _extract_clauses_with_llm(
        self, text: str, title: str, product: str, year: str,
        allow_fallback: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to extract structured clauses from circular text.
        Respects the global LLM toggle (USE_LOCAL_LLM).

        Args:
            text: Extracted PDF text
            title: Circular title
            product: NPCI product slug
            year: Circular year
            allow_fallback: If True, falls back to text-splitting heuristic on
                LLM failure. Default False so that an LLM outage surfaces as
                a real failure (status="failed") instead of silently producing
                placeholder clauses that pretend AI ran.

        Returns:
            List of structured clause dicts

        Raises:
            RuntimeError: If LLM extraction fails and allow_fallback is False.
        """
        from services.llm_provider import get_llm_provider, is_using_local_llm, log_llm_cost

        system_prompt = """You are a regulatory compliance analyst specializing in NPCI (National Payments Corporation of India) circulars.
Extract all compliance-relevant clauses from the given circular text.

For each clause, provide a JSON object with these fields:
- clause_id: Short identifier (e.g., "NPCI-C1", "NPCI-C2")
- clause_text: The full text of the clause
- clause_type: One of "requirement", "prohibition", "guideline", "procedure"
- key_requirements: List of key requirements/actions described (array of strings)
- entities: List of entities/parties involved (array of strings, e.g., "banks", "payment aggregators")
- category: Category (e.g., "Transaction Limits", "Security", "KYC", "Reporting", "Technical", "Operational", "Dispute Resolution", "Settlement")
- compliance_impact: "high", "medium", or "low"
- effective_date: If an effective date is mentioned in the clause, extract it (ISO format or null)

Return ONLY a JSON array of clause objects. No other text."""

        user_prompt = f"""Extract compliance clauses from this NPCI circular:

Title: {title}
Product: {product}
Year: {year}

Text (first 8000 chars):
{text[:8000]}"""

        try:
            provider = get_llm_provider()
            provider_name = provider.get_provider_name()

            response = await provider.generate(
                system=system_prompt,
                prompt=user_prompt,
                max_tokens=4096,
                temperature=0.3,
            )

            # Parse JSON from response
            clauses = self._parse_clauses_response(response)

            if not clauses:
                # LLM returned a response but we couldn't parse any clauses.
                # That's still a failure — don't silently fall back.
                raise RuntimeError(
                    f"LLM ({provider_name}) returned an unparseable response "
                    f"({len(response)} chars); no clauses extracted"
                )

            # Enrich clauses with circular metadata
            for clause in clauses:
                clause["product"] = product
                clause["circular_reference"] = title
                if not clause.get("effective_date"):
                    clause["effective_date"] = None

            # Log cost
            await log_llm_cost(
                db=self.db,
                provider=provider_name,
                operation="npci_clause_extraction",
                model=provider.model if hasattr(provider, 'model') else "",
            )

            logger.info(f"LLM extracted {len(clauses)} clauses using {provider_name}")
            return clauses

        except Exception as e:
            if allow_fallback:
                logger.warning(
                    f"LLM clause extraction failed ({e}); allow_fallback=True so "
                    f"using heuristic text split."
                )
                return self._fallback_clause_extraction(text, title, product)
            # No fallback: propagate so process_circular marks the row as failed.
            logger.error(f"LLM clause extraction failed: {e}")
            raise RuntimeError(f"LLM clause extraction failed: {e}") from e

    def _parse_clauses_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into clause list."""
        try:
            # Try to extract JSON array from response
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                clauses = json.loads(json_match.group())
                if isinstance(clauses, list):
                    return clauses
        except json.JSONDecodeError:
            pass

        # Try parsing the entire response as JSON
        try:
            result = json.loads(response.strip())
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "clauses" in result:
                return result["clauses"]
        except json.JSONDecodeError:
            pass

        logger.warning("Could not parse LLM clause response as JSON")
        return []

    def _fallback_clause_extraction(
        self, text: str, title: str, product: str
    ) -> List[Dict[str, Any]]:
        """
        Fallback clause extraction when LLM is not available.
        Creates basic clauses from the text by splitting on paragraphs.
        """
        clauses = []

        if not text or len(text.strip()) < 20:
            return [{
                "clause_id": "NPCI-C1",
                "clause_text": title[:2000],
                "clause_type": "guideline",
                "key_requirements": [],
                "entities": [],
                "category": "General",
                "compliance_impact": "medium",
                "product": product,
                "circular_reference": title,
                "effective_date": None,
            }]

        # Split text into paragraphs and create clauses
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 50]

        for idx, para in enumerate(paragraphs[:20]):  # Max 20 clauses
            clauses.append({
                "clause_id": f"NPCI-C{idx + 1}",
                "clause_text": para[:2000],
                "clause_type": "guideline",
                "key_requirements": [],
                "entities": [],
                "category": "General",
                "compliance_impact": "medium",
                "product": product,
                "circular_reference": title,
                "effective_date": None,
            })

        return clauses if clauses else [{
            "clause_id": "NPCI-C1",
            "clause_text": text[:2000],
            "clause_type": "guideline",
            "key_requirements": [],
            "entities": [],
            "category": "General",
            "compliance_impact": "medium",
            "product": product,
            "circular_reference": title,
            "effective_date": None,
        }]

    async def _store_clauses(
        self, clauses: List[Dict], circular_id: str, circular: Dict
    ) -> List[str]:
        """
        Store extracted clauses in the npci_circular_clauses MongoDB collection.

        Args:
            clauses: List of clause dicts
            circular_id: Circular _id
            circular: Full circular document

        Returns:
            List of stored clause document IDs
        """
        stored_ids = []

        for clause in clauses:
            clause_doc = {
                "clause_id": clause.get("clause_id", f"NPCI-C{uuid.uuid4().hex[:6]}"),
                "circular_id": circular_id,
                "npci_id": circular.get("npci_id"),
                "clause_text": clause.get("clause_text", ""),
                "clause_type": clause.get("clause_type", "guideline"),
                "key_requirements": clause.get("key_requirements", []),
                "entities": clause.get("entities", []),
                "category": clause.get("category", "General"),
                "compliance_impact": clause.get("compliance_impact", "medium"),
                "product": clause.get("product", circular.get("product", "")),
                "product_label": circular.get("product_label", ""),
                "circular_reference": clause.get("circular_reference", circular.get("title", "")),
                "effective_date": clause.get("effective_date"),
                "year": circular.get("year", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                # Upsert by clause_id to avoid duplicates
                result = await self.clauses_collection.update_one(
                    {
                        "circular_id": circular_id,
                        "clause_id": clause_doc["clause_id"],
                    },
                    {"$set": clause_doc},
                    upsert=True,
                )
                stored_ids.append(clause_doc["clause_id"])
            except Exception as e:
                logger.error(f"Failed to store clause {clause_doc['clause_id']}: {e}")

        return stored_ids

    async def _store_embeddings(
        self, clauses: List[Dict], circular: Dict
    ) -> int:
        """
        Generate and store clause embeddings in Qdrant.

        Args:
            clauses: List of clause dicts
            circular: Circular document

        Returns:
            Number of embeddings stored
        """
        if not self.qdrant_client:
            return 0

        stored = 0
        collection_name = "npci_circular_clauses"

        try:
            # Ensure collection exists
            from qdrant_client.models import VectorParams, Distance
            existing = [c.name for c in self.qdrant_client.get_collections().collections]
            if collection_name not in existing:
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {collection_name}")

            # Generate simple embeddings (hash-based for now, production would use OpenAI/sentence-transformers)
            from qdrant_client.models import PointStruct
            import hashlib

            points = []
            for idx, clause in enumerate(clauses):
                text = clause.get("clause_text", "")
                if not text:
                    continue

                # Simple hash-based embedding (384 dimensions)
                # In production, use sentence-transformers or OpenAI embeddings
                hash_bytes = hashlib.sha384(text.encode()).digest()
                embedding = [float(b) / 255.0 for b in hash_bytes]

                point_id = abs(hash(f"{circular.get('npci_id', '')}_{clause.get('clause_id', idx)}")) % (2**63)

                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "clause_id": clause.get("clause_id", ""),
                        "clause_text": text[:1000],
                        "clause_type": clause.get("clause_type", ""),
                        "category": clause.get("category", ""),
                        "compliance_impact": clause.get("compliance_impact", ""),
                        "product": clause.get("product", ""),
                        "circular_reference": clause.get("circular_reference", ""),
                        "npci_id": circular.get("npci_id"),
                        "year": circular.get("year", ""),
                    },
                ))

            if points:
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points,
                )
                stored = len(points)
                logger.info(f"Stored {stored} embeddings in Qdrant {collection_name}")

        except Exception as e:
            logger.error(f"Failed to store Qdrant embeddings: {e}")

        return stored

    async def batch_process_all(self, progress_callback=None) -> Dict[str, Any]:
        """
        Process all unprocessed circulars in batch.

        Args:
            progress_callback: Optional async callback(message: str)

        Returns:
            Batch processing result dict
        """
        cursor = self.circulars_collection.find({
            "$or": [
                {"processing_status": {"$exists": False}},
                {"processing_status": {"$nin": ["completed", "processing"]}},
            ]
        })

        unprocessed = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            unprocessed.append(doc)

        total = len(unprocessed)
        result = {
            "total": total,
            "processed": 0,
            "failed": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        if progress_callback:
            await progress_callback(f"Starting batch processing of {total} circulars...")

        for idx, doc in enumerate(unprocessed):
            try:
                proc_result = await self.process_circular(doc["_id"])

                if proc_result.get("success"):
                    result["processed"] += 1
                else:
                    result["failed"] += 1

                if progress_callback:
                    await progress_callback(
                        f"Processed {idx + 1}/{total}: {doc.get('title', '')[:60]}"
                    )

            except Exception as e:
                result["failed"] += 1
                logger.error(f"Batch process error for {doc['_id']}: {e}")

            # Rate limiting
            await asyncio.sleep(0.2)

        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        return result

    async def _convert_circular_to_regulation(
        self,
        circular: Dict,
        circular_id: str,
        raw_text: str,
        title_info: Dict,
    ) -> Dict[str, Any]:
        """
        Convert a processed NPCI circular into a full Regulation document
        using the same intelligence pipeline as RBI regulation uploads:
        1. ClauseExtractionService for rich semantic clause extraction
        2. LLM impact analysis (summary, org/technical/operational impact)
        3. Store in `regulations` MongoDB collection
        4. Store embeddings in `regulation_clauses` + `policy_clauses` Qdrant collections
        5. Auto-generate compliance tasks

        Args:
            circular: The NPCI circular document
            circular_id: MongoDB _id of the circular
            raw_text: Extracted text from the circular PDF
            title_info: Parsed title info (oc_number, fy_year, description)

        Returns:
            Dict with regulation_id, clauses_count, etc.
        """
        from services.npci_scraper_service import NPCI_PRODUCT_LABELS

        product = circular.get("product", "")
        product_label = NPCI_PRODUCT_LABELS.get(product, product.upper())
        npci_id = circular.get("npci_id", "")
        circular_title = circular.get("title", "Unknown NPCI Circular")

        # Build a regulation-style title
        reg_title = f"[NPCI {product_label}] {circular_title}"

        # Deduplicate: check if a regulation already exists for this circular
        existing = await self.db.regulations.find_one({
            "source": "npci_circular",
            "source_circular_id": str(npci_id),
        })
        if existing:
            logger.info(f"[NPCI→REG] Regulation already exists for NPCI circular {npci_id}, updating...")
            regulation_id = existing.get("id", str(uuid.uuid4()))
        else:
            regulation_id = str(uuid.uuid4())

        result = {"regulation_id": regulation_id, "clauses_count": 0}

        # --- Step 1: Full clause extraction using ClauseExtractionService ---
        try:
            from services.clause_extraction_service import ClauseExtractionService
            clause_extractor = ClauseExtractionService()

            clauses_data = await asyncio.wait_for(
                clause_extractor.extract_clauses_from_document(
                    text=raw_text,
                    document_type="regulation",
                    document_id=regulation_id,
                    document_title=reg_title
                ),
                timeout=300  # 5-minute timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"[NPCI→REG] Clause extraction timed out for circular {npci_id}, using fallback")
            from services.clause_extraction_service import ClauseExtractionService
            clause_extractor = ClauseExtractionService()
            clauses_data = clause_extractor._fallback_clause_extraction_with_enrichment(
                clause_extractor._split_into_chunks(raw_text),
                "regulation", regulation_id
            )
        except Exception as e:
            logger.error(f"[NPCI→REG] Clause extraction failed for circular {npci_id}: {e}")
            clauses_data = []

        # --- Step 2: LLM impact analysis ---
        analysis = {}
        try:
            from services.multi_llm_service_new import MultiLLMService
            llm_svc = MultiLLMService()
            analysis = await llm_svc.analyze_regulatory_circular_claude(raw_text, reg_title)
        except Exception as e:
            logger.warning(f"[NPCI→REG] Impact analysis failed for circular {npci_id}: {e}")

        # --- Step 3: Build Clause model objects ---
        from models import Clause, Regulation, Task, SeverityLevel

        clauses = []
        for clause_data in clauses_data:
            clause = Clause(
                clause_id=clause_data.get('clause_id', str(uuid.uuid4())),
                text=clause_data.get('original_text', clause_data.get('text', '')),
                original_text=clause_data.get('original_text', clause_data.get('text', '')),
                section=clause_data.get('section', f"NPCI {product_label}"),
                page_number=clause_data.get('page_number'),
                title=clause_data.get('title'),
                content=clause_data.get('content'),
                tags=clause_data.get('tags', [product, 'npci']),
                requirement_type=clause_data.get('requirement_type', 'mandatory'),
                subject_category=clause_data.get('subject_category', 'general'),
                key_obligations=clause_data.get('key_obligations', []),
                semantic_summary=clause_data.get('semantic_summary'),
                entities_involved=clause_data.get('entities_involved', []),
                keywords=clause_data.get('keywords', []),
                compliance_indicators=clause_data.get('compliance_indicators', []),
                criticality=clause_data.get('criticality', 'high'),
            )
            clauses.append(clause)

        result["clauses_count"] = len(clauses)

        # --- Step 4: Build and store Regulation document ---
        # Ensure impact fields are strings (LLM may return dicts)
        def _ensure_str(val):
            if val is None:
                return None
            if isinstance(val, dict):
                import json as json_mod
                return json_mod.dumps(val)
            return str(val)

        regulation = Regulation(
            id=regulation_id,
            title=reg_title,
            regulatory_body="NPCI",
            circular_number=str(npci_id) if npci_id else title_info.get("oc_number", ""),
            issued_date=None,
            effective_date=None,
            file_url=circular.get("pdf_url", ""),
            file_name=circular.get("title", ""),
            clauses=clauses,
            summary=_ensure_str(analysis.get('summary')),
            impact_organization=_ensure_str(analysis.get('org_impact')),
            impact_technical=_ensure_str(analysis.get('technical_impact')),
            impact_operational=_ensure_str(analysis.get('operational_impact')),
            user_id="system",
            organization="system",
            is_master_circular=False,
        )

        reg_dict = regulation.model_dump()
        reg_dict['created_at'] = reg_dict['created_at'].isoformat()
        for date_field in ['issued_date', 'effective_date', 'due_date']:
            if reg_dict.get(date_field):
                reg_dict[date_field] = reg_dict[date_field].isoformat()

        # Add NPCI-specific metadata
        reg_dict['source'] = 'npci_circular'
        reg_dict['source_circular_id'] = str(npci_id)
        reg_dict['npci_product'] = product
        reg_dict['npci_product_label'] = product_label

        if existing:
            await self.db.regulations.replace_one(
                {"id": regulation_id}, reg_dict
            )
        else:
            await self.db.regulations.insert_one(reg_dict)

        # --- Step 5: Auto-generate tasks ---
        if analysis.get('departments_affected'):
            for dept in analysis['departments_affected'][:3]:
                task = Task(
                    title=f"Review {reg_title} impact on {dept}",
                    description=f"Assess and implement changes required by NPCI circular {npci_id or circular_title}",
                    department=dept,
                    priority=SeverityLevel.HIGH,
                    circular_id=regulation_id,
                    user_id="system",
                    organization="system",
                    auto_assigned=True,
                )
                task_dict = task.model_dump()
                task_dict['created_at'] = task_dict['created_at'].isoformat()
                task_dict['updated_at'] = task_dict['updated_at'].isoformat()
                if task_dict.get('due_date'):
                    task_dict['due_date'] = task_dict['due_date'].isoformat()
                # Avoid duplicate tasks
                existing_task = await self.db.tasks.find_one({
                    "circular_id": regulation_id,
                    "department": dept,
                })
                if not existing_task:
                    await self.db.tasks.insert_one(task_dict)

        # --- Step 6: Store embeddings in regulation_clauses + policy_clauses Qdrant ---
        try:
            # Get vector_service from server module
            import sys
            srv = sys.modules.get('__main__') or sys.modules.get('server')
            vector_service = getattr(srv, 'vector_service', None) if srv else None

            if vector_service:
                clauses_for_vector = []
                for clause in clauses:
                    clauses_for_vector.append({
                        'clause_id': clause.clause_id,
                        'text': clause.text,
                        'original_text': clause.original_text,
                        'section': clause.section,
                        'page_number': clause.page_number,
                        'title': clause.title,
                        'requirement_type': clause.requirement_type,
                        'subject_category': clause.subject_category,
                        'criticality': clause.criticality,
                        'tags': clause.tags,
                        'keywords': clause.keywords,
                    })

                stored_count = await vector_service.store_regulation_clauses(
                    regulation_id=regulation_id,
                    clauses=clauses_for_vector,
                    organization="system",
                    user_id="system",
                )
                logger.info(f"[NPCI→REG] Stored {stored_count} clause embeddings in regulation_clauses")

                stored_count_policy = await vector_service.store_policy_clauses(
                    policy_id=f"regulation_{regulation_id}",
                    clauses=clauses_for_vector,
                    organization="system",
                    user_id="system",
                )
                logger.info(f"[NPCI→REG] Stored {stored_count_policy} embeddings in policy_clauses for gap analysis")
        except Exception as e:
            logger.warning(f"[NPCI→REG] Qdrant embedding storage failed: {e}")

        return result

    async def get_clauses_for_circular(self, circular_id: str) -> List[Dict]:
        """Get all extracted clauses for a circular."""
        clauses = []
        cursor = self.clauses_collection.find({"circular_id": circular_id})
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            clauses.append(doc)
        return clauses

    async def get_clause_stats(self) -> Dict[str, Any]:
        """Get clause extraction statistics."""
        try:
            total_clauses = await self.clauses_collection.count_documents({})

            # Count by product
            pipeline = [
                {"$group": {"_id": "$product", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            by_product = {}
            async for doc in self.clauses_collection.aggregate(pipeline):
                by_product[doc["_id"]] = doc["count"]

            # Count by type
            pipeline = [
                {"$group": {"_id": "$clause_type", "count": {"$sum": 1}}},
            ]
            by_type = {}
            async for doc in self.clauses_collection.aggregate(pipeline):
                by_type[doc["_id"]] = doc["count"]

            # Count by impact
            pipeline = [
                {"$group": {"_id": "$compliance_impact", "count": {"$sum": 1}}},
            ]
            by_impact = {}
            async for doc in self.clauses_collection.aggregate(pipeline):
                by_impact[doc["_id"]] = doc["count"]

            return {
                "total_clauses": total_clauses,
                "by_product": by_product,
                "by_type": by_type,
                "by_impact": by_impact,
            }
        except Exception as e:
            logger.error(f"Error getting clause stats: {e}")
            return {"total_clauses": 0, "by_product": {}, "by_type": {}, "by_impact": {}}
