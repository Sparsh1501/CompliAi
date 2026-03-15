#!/usr/bin/env python3
"""
NBFC Regulations Processor

This script processes ONLY Non-Banking Financial Company (NBFC) PDFs 
from the 'unprocessed_regulations' MongoDB collection:
1. Filters for NBFC-related documents only
2. Reads PDF binary data from MongoDB
3. Extracts text from PDF
4. Runs LLM analysis (summary, impact assessment)
5. Extracts clauses using LLM
6. Saves processed regulation to 'regulations' collection
7. Updates status in 'unprocessed_regulations'

Usage:
    python process_nbfc_regulations.py [--limit N] [--retry-failed] [--dry-run]

Requirements:
    pip install pymongo motor python-dotenv
"""

import os
import sys
import asyncio
import argparse
import uuid
import tempfile
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'nbfc_processing.log', mode='a')
    ]
)
logger = logging.getLogger('NBFCProcessor')

# Create logs directory if it doesn't exist
(Path(__file__).parent.parent / 'logs').mkdir(exist_ok=True)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
except ImportError:
    print("Error: motor and dotenv are required. Install with: pip install motor python-dotenv")
    sys.exit(1)

# Import backend services
try:
    from models import Regulation, Clause
    from services.document_service import DocumentService
    from services.multi_llm_service_new import MultiLLMService
    from services.clause_extraction_service import ClauseExtractionService
except ImportError as e:
    print(f"Error importing backend services: {e}")
    print("Make sure you're running from the backend directory")
    sys.exit(1)

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')


# NBFC filter query - matches documents with "Non-Banking Financial Companies" in title
NBFC_FILTER = {
    "title": {"$regex": "Non-Banking Financial Companies", "$options": "i"}
}


class NBFCRegulationsProcessor:
    """Processes NBFC regulations from MongoDB."""
    
    def __init__(self):
        logger.info("="*70)
        logger.info("Initializing NBFC Regulations Processor")
        logger.info("="*70)
        
        # Initialize database connection
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'compli-ai')
        logger.info(f"Connecting to MongoDB: {mongo_url.split('@')[-1] if '@' in mongo_url else mongo_url}")
        logger.info(f"Database: {db_name}")
        
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        
        # Collections
        self.unprocessed_collection = self.db['unprocessed_regulations']
        self.regulations_collection = self.db['regulations']
        logger.info("MongoDB connection established")
        
        # Initialize services
        logger.info("Initializing services...")
        self.doc_service = DocumentService()
        logger.info("  ✓ DocumentService initialized")
        self.llm_service = MultiLLMService()
        logger.info("  ✓ MultiLLMService initialized")
        self.clause_extractor = ClauseExtractionService()
        logger.info("  ✓ ClauseExtractionService initialized")
        
        # Stats
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.start_time = datetime.now()
        logger.info("Processor initialized successfully\n")
        
    async def run(self, limit: Optional[int] = None, retry_failed: bool = False, dry_run: bool = False):
        """Main entry point to process NBFC regulations."""
        print("\n" + "="*70)
        print("  NBFC Regulations Processor")
        print("="*70)
        
        # Build query - combine NBFC filter with status filter
        status_query = {'status': 'unprocessed'}
        if retry_failed:
            status_query = {'$or': [{'status': 'unprocessed'}, {'status': 'failed'}]}
        
        # Combine NBFC filter with status filter
        query = {"$and": [NBFC_FILTER, status_query]}
        
        # Get count
        total_nbfc = await self.unprocessed_collection.count_documents(NBFC_FILTER)
        to_process = await self.unprocessed_collection.count_documents(query)
        
        print(f"\n📊 NBFC Documents Summary:")
        print(f"   Total NBFC documents: {total_nbfc}")
        print(f"   Ready to process: {to_process}")
        
        if limit:
            print(f"   📌 Limiting to {limit} regulations")
        
        if dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made\n")
            await self._list_documents(query, limit)
            self.client.close()
            return
        
        # Get documents to process
        cursor = self.unprocessed_collection.find(query)
        if limit:
            cursor = cursor.limit(limit)
        
        documents = await cursor.to_list(length=limit or 100)
        
        if not documents:
            print("\n✅ No NBFC regulations to process!")
            self.client.close()
            return
        
        print(f"\n🔄 Processing {len(documents)} NBFC regulations...\n")
        
        for i, doc in enumerate(documents, 1):
            await self._process_one(doc, i, len(documents))
            
            # Add delay between API calls to avoid rate limiting
            if i < len(documents):
                print("   ⏳ Waiting 5s before next document (rate limit protection)...")
                await asyncio.sleep(5)
        
        await self._print_summary()
        self.client.close()
    
    async def _list_documents(self, query: dict, limit: Optional[int]):
        """List documents that would be processed (dry run)."""
        cursor = self.unprocessed_collection.find(query, {'title': 1, 'status': 1})
        if limit:
            cursor = cursor.limit(limit)
        
        docs = await cursor.to_list(length=limit or 100)
        
        print("Documents that would be processed:")
        print("-" * 70)
        for i, doc in enumerate(docs, 1):
            title = doc.get('title', 'Unknown')[:65]
            status = doc.get('status', 'unknown')
            print(f"{i:2}. [{status}] {title}")
        print("-" * 70)
    
    async def _process_one(self, doc: dict, index: int, total: int):
        """Process a single NBFC regulation document."""
        title = doc.get('title', 'Unknown')[:60]
        full_title = doc.get('title', 'Unknown')
        doc_id = doc['_id']
        source_url = doc.get('source_url', 'N/A')
        
        logger.info("")
        logger.info("-"*70)
        logger.info(f"[{index}/{total}] PROCESSING DOCUMENT")
        logger.info(f"  Title: {full_title}")
        logger.info(f"  Doc ID: {doc_id}")
        logger.info(f"  Source: {source_url[:80]}..." if len(source_url) > 80 else f"  Source: {source_url}")
        logger.info("-"*70)
        
        try:
            import time
            total_start = time.time()
            
            # Step 1: Extract PDF data and save to temp file
            logger.info("STEP 1: Extracting PDF data...")
            pdf_data = doc.get('pdf_data')
            if not pdf_data:
                logger.error("No PDF data found in document")
                raise ValueError("No PDF data found")
            
            pdf_size_kb = len(pdf_data) / 1024
            logger.info(f"  PDF size: {pdf_size_kb:.1f} KB")
            
            # Create temp file for PDF processing
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_data)
                tmp_path = tmp_file.name
            
            try:
                # Step 2: Extract text from PDF
                logger.info("STEP 2: Extracting text from PDF...")
                step_start = time.time()
                text = await self.doc_service.extract_text_from_pdf(tmp_path)
                text_time = time.time() - step_start
                logger.info(f"  ✓ Text extracted: {len(text):,} characters in {text_time:.2f}s")
                logger.debug(f"  First 200 chars: {text[:200]}...")
                
                if len(text) < 100:
                    logger.error(f"Extracted text too short: {len(text)} chars")
                    raise ValueError(f"Extracted text too short: {len(text)} chars")
                
                # Step 3: LLM Analysis (summary + impact)
                logger.info("STEP 3: Running LLM analysis (Claude)...")
                step_start = time.time()
                analysis = await self.llm_service.analyze_regulatory_circular_claude(text, doc.get('title', 'Regulation'))
                analysis_time = time.time() - step_start
                logger.info(f"  ✓ LLM analysis completed in {analysis_time:.2f}s")
                if isinstance(analysis, dict):
                    logger.info(f"  Summary length: {len(analysis.get('summary', ''))} chars")
                
                # Step 4: Extract clauses
                logger.info("STEP 4: Extracting clauses via LLM...")
                step_start = time.time()
                document_id = str(uuid.uuid4())
                clauses_data = await self.clause_extractor.extract_clauses_from_document(
                    text=text,
                    document_type="regulation",
                    document_id=document_id,
                    document_title=doc.get('title', 'Regulation')
                )
                clause_time = time.time() - step_start
                logger.info(f"  ✓ Extracted {len(clauses_data)} clauses in {clause_time:.2f}s")
                
                # Step 5: Create Clause objects
                clauses = []
                for clause_data in clauses_data:
                    clause = Clause(
                        clause_id=clause_data.get('clause_id', str(uuid.uuid4())),
                        text=clause_data.get('original_text', ''),
                        original_text=clause_data.get('original_text', ''),
                        section=clause_data.get('section'),
                        page_number=clause_data.get('page_number'),
                        title=clause_data.get('title'),
                        content=clause_data.get('content'),
                        tags=clause_data.get('tags', []),
                        requirement_type=clause_data.get('requirement_type', 'mandatory'),
                        subject_category=clause_data.get('subject_category', 'general'),
                        key_obligations=clause_data.get('key_obligations', []),
                        semantic_summary=clause_data.get('semantic_summary'),
                        entities_involved=clause_data.get('entities_involved', []),
                        keywords=clause_data.get('keywords', []),
                        compliance_indicators=clause_data.get('compliance_indicators', []),
                        criticality=clause_data.get('criticality', 'high')
                    )
                    clauses.append(clause)
                
                # Step 6: Create and save Regulation
                step_start = time.time()
                
                # Helper function to convert impact fields to string
                def to_impact_string(impact_val):
                    """Convert impact value to string, handling dict/list/None cases"""
                    if impact_val is None:
                        return ''
                    if isinstance(impact_val, str):
                        return impact_val
                    if isinstance(impact_val, dict):
                        # Convert dict to readable string
                        return '; '.join(f"{k}: {v}" for k, v in impact_val.items())
                    if isinstance(impact_val, list):
                        return '; '.join(str(item) for item in impact_val)
                    return str(impact_val)
                
                regulation = Regulation(
                    title=doc.get('title', 'Unknown Regulation'),
                    regulatory_body=doc.get('regulatory_body', 'RBI'),
                    circular_number=doc.get('circular_number'),
                    file_url=doc.get('source_url'),
                    file_name=doc.get('file_name'),
                    clauses=clauses,
                    summary=analysis.get('summary') if isinstance(analysis, dict) else str(analysis),
                    impact_organization=to_impact_string(analysis.get('org_impact') if isinstance(analysis, dict) else ''),
                    impact_technical=to_impact_string(analysis.get('technical_impact') if isinstance(analysis, dict) else ''),
                    impact_operational=to_impact_string(analysis.get('operational_impact') if isinstance(analysis, dict) else ''),
                    user_id='system',
                    organization='Default',
                    is_master_circular=True,
                    # Tag as NBFC regulation
                    tags=['NBFC', 'Non-Banking Financial Company', 'RBI Master Direction']
                )
                
                reg_dict = regulation.model_dump()
                reg_dict['created_at'] = reg_dict['created_at'].isoformat()
                for date_field in ['issued_date', 'effective_date', 'due_date']:
                    if reg_dict.get(date_field):
                        reg_dict[date_field] = reg_dict[date_field].isoformat()
                
                # Add reference to original unprocessed document
                reg_dict['unprocessed_regulation_id'] = str(doc_id)
                reg_dict['category'] = 'NBFC'
                
                logger.info("STEP 6: Saving to MongoDB...")
                await self.regulations_collection.insert_one(reg_dict)
                save_time = time.time() - step_start
                logger.info(f"  ✓ Saved to 'regulations' collection in {save_time:.2f}s")
                
                # Update unprocessed_regulations status
                logger.info("  Updating source document status...")
                await self.unprocessed_collection.update_one(
                    {'_id': doc_id},
                    {
                        '$set': {
                            'status': 'processed',
                            'processed_at': datetime.utcnow(),
                            'regulation_id': regulation.id,
                            'clause_count': len(clauses),
                            'error': None
                        }
                    }
                )
                
                total_time = time.time() - total_start
                logger.info("")
                logger.info(f"✅ SUCCESS: Document processed in {total_time:.2f}s")
                logger.info(f"   Clauses: {len(clauses)} | Text: {len(text):,} chars | PDF: {pdf_size_kb:.1f} KB")
                logger.info(f"   Timings: Text={text_time:.1f}s, LLM={analysis_time:.1f}s, Clauses={clause_time:.1f}s, Save={save_time:.1f}s")
                
                self.processed_count += 1
                
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
                
        except Exception as e:
            error_msg = str(e)[:500]
            logger.error("")
            logger.error(f"❌ FAILED: {title}")
            logger.error(f"   Error: {error_msg}")
            logger.error(f"   Full traceback:")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    logger.error(f"     {line}")
            
            # Update status to failed
            await self.unprocessed_collection.update_one(
                {'_id': doc_id},
                {
                    '$set': {
                        'status': 'failed',
                        'processed_at': datetime.utcnow(),
                        'error': error_msg
                    }
                }
            )
            
            self.failed_count += 1
            logger.info(f"   Document marked as 'failed' in database")
    
    async def _print_summary(self):
        """Print final summary."""
        elapsed = datetime.now() - self.start_time
        
        logger.info("")
        logger.info("="*70)
        logger.info("  NBFC PROCESSING SUMMARY")
        logger.info("="*70)
        
        # Get counts from MongoDB - NBFC specific
        total_nbfc = await self.unprocessed_collection.count_documents(NBFC_FILTER)
        nbfc_processed = await self.unprocessed_collection.count_documents(
            {"$and": [NBFC_FILTER, {'status': 'processed'}]}
        )
        nbfc_failed = await self.unprocessed_collection.count_documents(
            {"$and": [NBFC_FILTER, {'status': 'failed'}]}
        )
        nbfc_pending = await self.unprocessed_collection.count_documents(
            {"$and": [NBFC_FILTER, {'status': 'unprocessed'}]}
        )
        
        total_regulations = await self.regulations_collection.count_documents({'category': 'NBFC'})
        
        logger.info(f"")
        logger.info(f"⏱️  Total Runtime: {elapsed}")
        logger.info(f"")
        logger.info(f"📊 This Session:")
        logger.info(f"   ✅ Processed: {self.processed_count}")
        logger.info(f"   ❌ Failed: {self.failed_count}")
        if self.processed_count > 0:
            avg_time = elapsed.total_seconds() / self.processed_count
            logger.info(f"   ⏱️  Avg per doc: {avg_time:.1f}s")
        
        logger.info(f"")
        logger.info(f"📊 NBFC Documents Status (in unprocessed_regulations):")
        logger.info(f"   Total NBFC: {total_nbfc}")
        logger.info(f"   ✅ Processed: {nbfc_processed}")
        logger.info(f"   ❌ Failed: {nbfc_failed}")
        logger.info(f"   ⏳ Pending: {nbfc_pending}")
        
        logger.info(f"")
        logger.info(f"📊 NBFC Regulations in Database:")
        logger.info(f"   Total: {total_regulations}")
        logger.info("")
        logger.info("="*70)
        logger.info(f"Log file: {Path(__file__).parent.parent / 'logs' / 'nbfc_processing.log'}")
        logger.info("="*70)


async def main():
    parser = argparse.ArgumentParser(
        description="Process NBFC regulations from MongoDB"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of regulations to process (default: all)'
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='Also retry previously failed regulations'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='List documents that would be processed without making changes'
    )
    
    args = parser.parse_args()
    
    processor = NBFCRegulationsProcessor()
    await processor.run(limit=args.limit, retry_failed=args.retry_failed, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
