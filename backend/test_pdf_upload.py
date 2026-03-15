"""Test script to verify PDF extraction and clause extraction for scanned PDFs."""
import asyncio
import os
import json
import time
from dotenv import load_dotenv
load_dotenv('.env')

from services.document_service import DocumentService
from services.clause_extraction_service import ClauseExtractionService
from config.compliance_context import get_default_context

PDF_PATH = '/Users/shivamchandrs/Downloads/2. Know Your Customer (KYC) and AML) Policy_Version 4.0_30.09.2025.pdf'

async def test_extraction():
    ds = DocumentService()
    
    print('Step 1: Extracting text from PDF...')
    start = time.time()
    text = await ds.extract_text(PDF_PATH)
    print(f'  Extracted {len(text)} chars in {time.time()-start:.1f}s')
    
    if len(text) < 100:
        print('  ERROR: No text extracted! PDF might be scanned with no OCR available.')
        return
    
    print(f'\nStep 2: Splitting into chunks...')
    ctx = get_default_context()
    ce = ClauseExtractionService(ctx)
    
    MAX_CHUNK = 12000
    chunks = ce._split_into_mega_chunks(text, MAX_CHUNK)
    print(f'  Split into {len(chunks)} mega-chunks')
    for i, chunk in enumerate(chunks):
        print(f'    Chunk {i+1}: {len(chunk["text"])} chars, section: {chunk["section"][:50]}')
    
    print(f'\nStep 3: Extracting clauses from first chunk (with LLM)...')
    start = time.time()
    try:
        clauses = await asyncio.wait_for(
            ce._extract_and_enrich_single_call(
                chunks[0]['text'], 'policy', 'test-doc-id', 'KYC and AML Policy',
                section_context=chunks[0].get('section', 'General')
            ),
            timeout=120
        )
        elapsed = time.time() - start
        print(f'  SUCCESS: Extracted {len(clauses)} clauses in {elapsed:.1f}s')
        if clauses:
            print(f'  Sample clause:')
            print(f'    Title: {clauses[0].get("title", "N/A")}')
            print(f'    Type: {clauses[0].get("requirement_type", "N/A")}')
            print(f'    Category: {clauses[0].get("subject_category", "N/A")}')
            print(f'    Text preview: {clauses[0].get("text", "")[:100]}...')
    except asyncio.TimeoutError:
        print(f'  TIMEOUT after {time.time()-start:.1f}s')
    except Exception as e:
        print(f'  ERROR: {type(e).__name__}: {e}')

if __name__ == '__main__':
    asyncio.run(test_extraction())
