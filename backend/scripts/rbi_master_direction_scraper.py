#!/usr/bin/env python3
"""
RBI Master Directions Scraper (v2 - Full Page Scroll)

This script:
1. Opens the RBI Master Directions page
2. Waits for CAPTCHA completion
3. SCROLLS ENTIRE PAGE to load all PDFs (handles lazy loading)
4. Extracts ALL PDF links from the page
5. Stores PDF binary data in MongoDB collection "unprocessed_regulations"

Usage:
    python rbi_master_direction_scraper.py

Requirements:
    pip install playwright aiohttp pymongo motor python-dotenv
    playwright install chromium
"""

import os
import sys
import asyncio
import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import aiohttp

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: playwright is required. Install with: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
except ImportError:
    print("Error: motor and dotenv are required. Install with: pip install motor python-dotenv")
    sys.exit(1)

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
DOWNLOAD_DIR = BASE_DIR / "data" / "rbi_regulations" / "downloads"
RBI_URL = "https://rbi.org.in/scripts/bs_viewmasterdirections.aspx"

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')


class RBIMasterDirectionScraper:
    """Scraper for RBI Master Directions website - stores raw PDF data in MongoDB."""
    
    def __init__(self):
        self.download_dir = DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_pdfs: List[Dict] = []
        self.skipped_pdfs: List[Dict] = []
        self.failed_pdfs: List[Dict] = []
        
        # Initialize database connection
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[os.environ.get('DB_NAME', 'compliance_db')]
        
        # Collection for unprocessed regulations (raw PDF data)
        self.unprocessed_collection = self.db['unprocessed_regulations']
        
    async def run(self):
        """Main entry point to run the scraper."""
        print("\n" + "="*70)
        print("  RBI Master Directions Scraper v2 (Full Page Scroll)")
        print("="*70)
        print(f"\n📁 Download directory: {self.download_dir}")
        
        # Ensure unique index exists
        await self._ensure_indexes()
        
        # Step 1: Scrape and download PDFs
        await self._scrape_and_store()
        
        # Step 2: Print summary
        await self._print_summary()
        
        # Close database connection
        self.client.close()
    
    async def _ensure_indexes(self):
        """Ensure unique index on source_url for idempotency."""
        try:
            await self.unprocessed_collection.create_index('source_url', unique=True)
            print("✅ Unique index on source_url confirmed")
        except Exception as e:
            print(f"Index already exists or error: {e}")
    
    async def _scrape_and_store(self):
        """Open browser, scroll page, download PDFs and store in MongoDB."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=['--start-maximized']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True
            )
            
            page = await context.new_page()
            
            print(f"\n🌐 Opening RBI website: {RBI_URL}")
            print("\n" + "="*70)
            print("  ⚠️  ACTION REQUIRED: Please complete the CAPTCHA")
            print("="*70)
            
            try:
                await page.goto(RBI_URL, wait_until="networkidle", timeout=60000)
            except Exception as e:
                print(f"Initial navigation: {e}")
            
            print("\n⏳ Waiting for CAPTCHA completion (timeout: 5 minutes)...")
            
            try:
                # Wait for content to appear after CAPTCHA
                # Note: RBI uses both .pdf and .PDF (case matters in selectors)
                await page.wait_for_selector("a[href*='.pdf'], a[href*='.PDF']", timeout=300000)
                print("\n✅ CAPTCHA completed! Page loaded successfully.")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"\n❌ Timeout waiting for page: {e}")
                await browser.close()
                return
            
            # CRITICAL: Scroll entire page to load all lazy-loaded content
            print("\n📜 Scrolling page to load all PDFs...")
            await self._scroll_entire_page(page)
            
            # Get cookies for download requests
            cookies = await context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            
            # Extract ALL PDF links after scrolling
            pdf_links = await self._extract_all_pdf_links(page)
            
            if not pdf_links:
                print("\n❌ No PDF links found.")
                await browser.close()
                return
                
            print(f"\n📄 Found {len(pdf_links)} unique regulation PDFs")
            
            # Download PDFs and store in MongoDB
            await self._download_and_store(pdf_links, cookie_dict)
            
            await browser.close()
    
    async def _scroll_entire_page(self, page):
        """Scroll the entire page to trigger lazy loading of all content."""
        
        # Get initial page info
        viewport_height = await page.evaluate("window.innerHeight")
        total_height = await page.evaluate("document.body.scrollHeight")
        print(f"   Viewport height: {viewport_height}px, Total page height: {total_height}px")
        
        # Scroll incrementally through the entire page
        current_position = 0
        scroll_step = viewport_height - 100  # Overlap by 100px
        scroll_count = 0
        
        while current_position < total_height:
            # Scroll to next position
            await page.evaluate(f"window.scrollTo(0, {current_position})")
            await asyncio.sleep(0.5)
            
            # Count PDFs at this position (case-insensitive: .pdf and .PDF)
            pdf_count = await page.evaluate("document.querySelectorAll('a[href*=\".pdf\"], a[href*=\".PDF\"]').length")
            
            # Check for new content that might have loaded
            new_total_height = await page.evaluate("document.body.scrollHeight")
            if new_total_height > total_height:
                total_height = new_total_height
                print(f"   Page grew to {total_height}px")
            
            scroll_count += 1
            current_position += scroll_step
            
            if scroll_count % 5 == 0:
                print(f"   Scrolled {current_position}px / {total_height}px - Found {pdf_count} PDFs")
        
        # Final scroll to absolute bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
        
        # Save diagnostic screenshot and HTML
        print("\n📸 Saving diagnostic files...")
        screenshot_path = self.download_dir / "page_screenshot_bottom.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"   Screenshot saved: {screenshot_path}")
        
        html_path = self.download_dir / "page_content.html"
        html_content = await page.content()
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"   HTML saved: {html_path}")
        
        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        
        # Final PDF count (case-insensitive: .pdf and .PDF)
        final_count = await page.evaluate("document.querySelectorAll('a[href*=\".pdf\"], a[href*=\".PDF\"]').length")
        print(f"   ✅ Scrolling complete. Total PDF links found: {final_count}")
    
    async def _extract_all_pdf_links(self, page) -> List[Dict]:
        """Extract ALL PDF links from the fully loaded page."""
        print("\n🔍 Extracting all PDF links...")
        
        try:
            links = await page.evaluate("""
                () => {
                    const results = [];
                    const seenUrls = new Set();
                    
                    // Find ALL PDF links on the page (both .pdf and .PDF - case matters!)
                    const pdfLinks = document.querySelectorAll('a[href*=".pdf"], a[href*=".PDF"]');
                    console.log('Total PDF link elements found:', pdfLinks.length);
                    
                    for (const link of pdfLinks) {
                        const href = link.getAttribute('href');
                        if (!href) continue;
                        
                        // Build full URL
                        const fullUrl = href.startsWith('http') 
                            ? href 
                            : 'https://rbi.org.in' + (href.startsWith('/') ? href : '/' + href);
                        
                        // Skip duplicates (case-insensitive URL comparison)
                        const normalizedUrl = fullUrl.toLowerCase();
                        if (seenUrls.has(normalizedUrl)) continue;
                        seenUrls.add(normalizedUrl);
                        
                        // Try to get title from various sources
                        let title = '';
                        
                        // 1. Try the link text itself
                        title = link.textContent.trim();
                        
                        // 2. If link text is too short, try parent row/cell
                        if (!title || title.length < 10) {
                            const row = link.closest('tr');
                            if (row) {
                                const firstCell = row.querySelector('td:first-child');
                                if (firstCell) {
                                    title = firstCell.textContent.trim();
                                }
                            }
                        }
                        
                        // 3. Try parent element
                        if (!title || title.length < 10) {
                            const parent = link.parentElement;
                            if (parent) {
                                title = parent.textContent.trim().split('\\n')[0];
                            }
                        }
                        
                        // 4. Extract from URL as fallback
                        if (!title || title.length < 5) {
                            const urlMatch = href.match(/\\/([^\\/]+)\\.pdf$/i);
                            if (urlMatch) {
                                title = decodeURIComponent(urlMatch[1])
                                    .replace(/%20/g, ' ')
                                    .replace(/_/g, ' ');
                            }
                        }
                        
                        if (!title) title = 'Unknown Regulation';
                        
                        // Clean up title
                        title = title.replace(/\\s+/g, ' ').trim();
                        if (title.length > 300) title = title.substring(0, 300);
                        
                        // Try to extract circular number
                        let circularNumber = null;
                        const circularMatch = title.match(/No\\.?\\s*([A-Z0-9\\.\\-\\/]+)/i);
                        if (circularMatch) {
                            circularNumber = circularMatch[1];
                        }
                        
                        results.push({
                            url: fullUrl,
                            title: title,
                            circular_number: circularNumber
                        });
                    }
                    
                    return results;
                }
            """)
            
            print(f"   Extracted {len(links)} unique PDF links")
            return links
            
        except Exception as e:
            print(f"❌ Error extracting links: {e}")
            return []
    
    async def _download_and_store(self, pdf_links: List[Dict], cookies: dict):
        """Download PDFs and store directly in MongoDB."""
        print(f"\n📥 Downloading and storing {len(pdf_links)} PDFs in MongoDB...")
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/pdf,*/*',
                'Referer': RBI_URL,
            }
            
            for i, link in enumerate(pdf_links, 1):
                url = link['url']
                title = link['title']
                
                print(f"\n[{i}/{len(pdf_links)}] {title[:60]}...")
                
                try:
                    # Check if already exists in MongoDB (idempotency)
                    existing = await self.unprocessed_collection.find_one({'source_url': url})
                    if existing:
                        self.skipped_pdfs.append({'title': title, 'url': url, 'reason': 'already exists'})
                        print(f"  ⏭️  Already exists in database, skipping")
                        continue
                    
                    async with session.get(
                        url, 
                        headers=headers, 
                        cookies=cookies,
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            if content[:4] == b'%PDF':
                                # Create safe filename
                                safe_filename = re.sub(r'[^\w\s\-()]', '', title)[:100] + '.pdf'
                                
                                document = {
                                    'title': title,
                                    'circular_number': link.get('circular_number'),
                                    'source_url': url,
                                    'regulatory_body': 'RBI',
                                    'document_type': 'master_direction',
                                    'pdf_data': content,  # Store binary PDF data
                                    'pdf_size_bytes': len(content),
                                    'file_name': safe_filename,
                                    'status': 'unprocessed',
                                    'scraped_at': datetime.utcnow(),
                                    'processed_at': None,
                                    'error': None
                                }
                                
                                try:
                                    await self.unprocessed_collection.insert_one(document)
                                    
                                    self.scraped_pdfs.append({
                                        'title': title,
                                        'url': url,
                                        'size': len(content)
                                    })
                                    
                                    print(f"  ✅ Stored in MongoDB ({len(content)//1024} KB)")
                                    
                                    # Also save to disk as backup
                                    filepath = self.download_dir / safe_filename
                                    with open(filepath, 'wb') as f:
                                        f.write(content)
                                        
                                except Exception as db_error:
                                    if 'duplicate key' in str(db_error).lower():
                                        self.skipped_pdfs.append({'title': title, 'url': url, 'reason': 'duplicate'})
                                        print(f"  ⏭️  Duplicate (concurrent insert), skipping")
                                    else:
                                        raise db_error
                            else:
                                self.failed_pdfs.append({
                                    'title': title,
                                    'url': url,
                                    'error': 'Not a valid PDF'
                                })
                                print(f"  ⚠️  Not a valid PDF (got {content[:20]})")
                        else:
                            self.failed_pdfs.append({
                                'title': title,
                                'url': url,
                                'error': f'HTTP {response.status}'
                            })
                            print(f"  ❌ HTTP {response.status}")
                            
                except asyncio.TimeoutError:
                    self.failed_pdfs.append({
                        'title': title,
                        'url': url,
                        'error': 'Timeout'
                    })
                    print(f"  ❌ Timeout")
                except Exception as e:
                    self.failed_pdfs.append({
                        'title': title,
                        'url': url,
                        'error': str(e)[:100]
                    })
                    print(f"  ❌ Error: {str(e)[:50]}")
    
    async def _print_summary(self):
        """Print final summary."""
        print("\n" + "="*70)
        print("  SUMMARY")
        print("="*70)
        
        # Get total count from MongoDB
        total_in_db = await self.unprocessed_collection.count_documents({})
        unprocessed_count = await self.unprocessed_collection.count_documents({'status': 'unprocessed'})
        
        print(f"\n📊 This Session:")
        print(f"   ✅ New PDFs stored: {len(self.scraped_pdfs)}")
        print(f"   ⏭️  Skipped (already exist): {len(self.skipped_pdfs)}")
        print(f"   ❌ Failed: {len(self.failed_pdfs)}")
        
        print(f"\n📊 Total in 'unprocessed_regulations' collection: {total_in_db}")
        print(f"   - Unprocessed: {unprocessed_count}")
        print(f"   - Processed: {total_in_db - unprocessed_count}")
        
        # Save summary to file
        summary = {
            'timestamp': datetime.now().isoformat(),
            'new_scraped_count': len(self.scraped_pdfs),
            'skipped_count': len(self.skipped_pdfs),
            'failed_count': len(self.failed_pdfs),
            'total_in_db': total_in_db,
            'new_scraped_pdfs': self.scraped_pdfs,
            'skipped_pdfs': self.skipped_pdfs,
            'failed_pdfs': self.failed_pdfs
        }
        
        summary_file = self.download_dir / f"scrape_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"\n📄 Summary saved to: {summary_file}")
        
        if self.failed_pdfs:
            print("\n⚠️  Failed downloads:")
            for f in self.failed_pdfs[:10]:
                print(f"   - {f['title'][:50]}: {f['error']}")
            if len(self.failed_pdfs) > 10:
                print(f"   ... and {len(self.failed_pdfs) - 10} more")


async def main():
    parser = argparse.ArgumentParser(
        description="Scrape ALL RBI Master Directions and store PDF data in MongoDB"
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check current database status, do not scrape'
    )
    
    args = parser.parse_args()
    
    if args.check_only:
        # Just show database status
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        client = AsyncIOMotorClient(mongo_url)
        db = client[os.environ.get('DB_NAME', 'compliance_db')]
        
        total = await db.unprocessed_regulations.count_documents({})
        unprocessed = await db.unprocessed_regulations.count_documents({'status': 'unprocessed'})
        processed = await db.unprocessed_regulations.count_documents({'status': 'processed'})
        failed = await db.unprocessed_regulations.count_documents({'status': 'failed'})
        
        print(f"\n📊 Database Status:")
        print(f"   Total: {total}")
        print(f"   Unprocessed: {unprocessed}")
        print(f"   Processed: {processed}")
        print(f"   Failed: {failed}")
        
        client.close()
        return
    
    scraper = RBIMasterDirectionScraper()
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
