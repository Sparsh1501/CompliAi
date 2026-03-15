"""
RBI PA/PG Notification Scraper Service
Scrapes RBI circulars/notifications related to Payment Aggregators and Payment Gateways.

RBI publishes PA/PG related notifications at:
- Main circulars page: https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx
- Master Directions: https://www.rbi.org.in/Scripts/BS_MasterDirectionDisplay.aspx
- Notifications: https://www.rbi.org.in/Scripts/NotificationUser.aspx

This service scrapes and stores PA/PG related circulars in MongoDB 'rbi_papg_circulars' collection.
"""

import asyncio
import httpx
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# PA/PG related keywords for identifying relevant circulars
PAPG_KEYWORDS = [
    "payment aggregator", "payment gateway", "pa-p", "pa/pg",
    "online payment", "merchant aggregator", "escrow account",
    "nodal account", "settlement", "pravaah", "authorization",
    "payment systems", "pss act", "payment service provider",
    "digital payment", "merchant onboarding", "kyc", "aml",
    "fraud monitoring", "t+1 settlement", "net worth",
]

# RBI notification categories relevant to PA/PG
PAPG_CATEGORIES = [
    {"slug": "master_directions", "label": "Master Directions", "url_type": "master_direction"},
    {"slug": "circulars", "label": "Circulars", "url_type": "circular"},
    {"slug": "notifications", "label": "Notifications", "url_type": "notification"},
    {"slug": "faqs", "label": "FAQs & Clarifications", "url_type": "faq"},
    {"slug": "press_releases", "label": "Press Releases", "url_type": "press"},
]

PAPG_CATEGORY_LABELS = {cat["slug"]: cat["label"] for cat in PAPG_CATEGORIES}

RBI_BASE_URL = "https://www.rbi.org.in"
REQUEST_DELAY = 1.0  # seconds between requests to be respectful
UPLOAD_DIR = "/tmp/uploads/rbi_papg"


class PAPGScraper:
    """
    Scraper for RBI PA/PG related circulars and notifications.
    Stores scraped items in MongoDB 'rbi_papg_circulars' collection.
    """

    def __init__(self, db):
        """
        Initialize the PA/PG scraper service.

        Args:
            db: MongoDB database instance (Motor async driver)
        """
        self.db = db
        self.collection = db["rbi_papg_circulars"]
        self.base_url = RBI_BASE_URL
        self.headers = {
            "User-Agent": "CompliAI/1.0 (Compliance Monitoring System)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.rbi.org.in/",
        }
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    async def ensure_indexes(self):
        """Create MongoDB indexes for efficient querying."""
        try:
            await self.collection.create_index("circular_id", unique=True, sparse=True)
            await self.collection.create_index("category")
            await self.collection.create_index("date")
            await self.collection.create_index("processed")
            await self.collection.create_index([("title", "text"), ("description", "text")])
            logger.info("Created indexes for rbi_papg_circulars collection")
        except Exception as e:
            logger.warning(f"Error creating PA/PG circular indexes: {e}")

    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """
        Make an HTTP GET request with error handling and rate limiting.

        Args:
            url: Full URL to fetch
            params: Optional query parameters

        Returns:
            HTML content as string or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.text
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} fetching {url}: {e}")
            return None
        except httpx.RequestError as e:
            logger.warning(f"Request error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    async def _download_pdf(self, pdf_url: str, circular_id: str) -> Optional[str]:
        """
        Download a PDF file and save locally.

        Args:
            pdf_url: URL to the PDF
            circular_id: Unique ID for naming the file

        Returns:
            Local file path or None on error
        """
        try:
            if not pdf_url.startswith("http"):
                pdf_url = f"{self.base_url}{pdf_url}"

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(pdf_url, headers=self.headers)
                response.raise_for_status()

                # Generate safe filename
                safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', circular_id)
                file_path = os.path.join(UPLOAD_DIR, f"{safe_id}.pdf")

                with open(file_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"Downloaded PDF: {file_path}")
                return file_path

        except Exception as e:
            logger.warning(f"Failed to download PDF {pdf_url}: {e}")
            return None

    def _is_papg_related(self, title: str, description: str = "") -> bool:
        """
        Check if a circular/notification is related to PA/PG.

        Args:
            title: Title of the circular
            description: Description/summary of the circular

        Returns:
            True if PA/PG related, False otherwise
        """
        combined_text = f"{title} {description}".lower()
        return any(keyword.lower() in combined_text for keyword in PAPG_KEYWORDS)

    async def scrape_rbi_circulars(
        self,
        category: str = "circulars",
        year: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Scrape RBI circulars/notifications for PA/PG related content.

        Args:
            category: Category to scrape ('master_directions', 'circulars', 'notifications')
            year: Optional year filter (e.g., '2025')
            progress_callback: Optional async callback for progress updates

        Returns:
            Dict with scraping statistics
        """
        stats = {"total": 0, "new": 0, "duplicates": 0, "errors": 0, "category": category}

        if progress_callback:
            try:
                await progress_callback(f"Starting to scrape {category}...")
            except Exception:
                pass

        # Build URL based on category
        if category == "master_directions":
            # RBI Master Directions page
            url = f"{self.base_url}/Scripts/BS_ViewMasDirections.aspx"
            params = {"id": "11192"}  # Payment and Settlement Systems
        elif category == "circulars":
            # RBI Circulars page - filter for DPSS (Department of Payment & Settlement Systems)
            url = f"{self.base_url}/Scripts/BS_CircularIndexDisplay.aspx"
            params = {"Id": "12"}  # DPSS circulars
            if year:
                params["Year"] = year
        elif category == "notifications":
            url = f"{self.base_url}/Scripts/NotificationUser.aspx"
            params = {"Id": "12", "Mode": "0"}
            if year:
                params["Year"] = year
        else:
            # Default to circulars
            url = f"{self.base_url}/Scripts/BS_CircularIndexDisplay.aspx"
            params = {"Id": "12"}

        html = await self._make_request(url, params)
        if not html:
            stats["errors"] += 1
            return stats

        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find circular/notification links
        circulars = await self._parse_circulars_page(soup, category)

        for circular in circulars:
            stats["total"] += 1

            # Check if PA/PG related
            if not self._is_papg_related(circular.get("title", ""), circular.get("description", "")):
                continue

            # Check for duplicates
            existing = await self.collection.find_one({"circular_id": circular["circular_id"]})
            if existing:
                stats["duplicates"] += 1
                continue

            # Download PDF if available
            pdf_url = circular.get("pdf_url")
            if pdf_url:
                local_path = await self._download_pdf(pdf_url, circular["circular_id"])
                circular["local_pdf_path"] = local_path

            # Add metadata
            circular["category"] = category
            circular["scraped_at"] = datetime.now(timezone.utc)
            circular["processed"] = False
            circular["source"] = "RBI"

            # Insert into MongoDB
            try:
                await self.collection.insert_one(circular)
                stats["new"] += 1
                if progress_callback:
                    try:
                        await progress_callback(f"Saved: {circular['title'][:60]}...")
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Error inserting circular: {e}")
                stats["errors"] += 1

            # Rate limiting
            await asyncio.sleep(REQUEST_DELAY)

        return stats

    async def _parse_circulars_page(self, soup: BeautifulSoup, category: str) -> List[Dict[str, Any]]:
        """
        Parse a circulars/notifications HTML page.

        Args:
            soup: BeautifulSoup parsed HTML
            category: Category being parsed

        Returns:
            List of parsed circular dictionaries
        """
        circulars = []

        # Try different HTML structures used by RBI
        # Structure 1: Table-based listing
        tables = soup.find_all("table", {"class": "tablebg"}) or soup.find_all("table")
        
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    # Extract title and link
                    link = row.find("a")
                    if link:
                        title = link.get_text(strip=True)
                        href = link.get("href", "")
                        
                        # Extract date if available
                        date_text = ""
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            if re.match(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', cell_text):
                                date_text = cell_text
                                break

                        # Generate circular ID
                        circular_id = self._generate_circular_id(title, href, date_text)

                        # Check for PDF link
                        pdf_url = None
                        pdf_link = row.find("a", href=re.compile(r'\.pdf', re.IGNORECASE))
                        if pdf_link:
                            pdf_url = pdf_link.get("href", "")

                        circulars.append({
                            "circular_id": circular_id,
                            "title": title,
                            "url": href if href.startswith("http") else f"{self.base_url}{href}",
                            "pdf_url": pdf_url,
                            "date": self._parse_date(date_text),
                            "date_text": date_text,
                        })

        # Structure 2: List/div-based listing
        if not circulars:
            items = soup.find_all("div", {"class": "circular-item"}) or soup.find_all("li", {"class": "notification"})
            for item in items:
                link = item.find("a")
                if link:
                    title = link.get_text(strip=True)
                    href = link.get("href", "")
                    date_text = ""
                    date_span = item.find("span", {"class": "date"})
                    if date_span:
                        date_text = date_span.get_text(strip=True)

                    circular_id = self._generate_circular_id(title, href, date_text)
                    
                    circulars.append({
                        "circular_id": circular_id,
                        "title": title,
                        "url": href if href.startswith("http") else f"{self.base_url}{href}",
                        "date": self._parse_date(date_text),
                        "date_text": date_text,
                    })

        return circulars

    def _generate_circular_id(self, title: str, url: str, date_text: str) -> str:
        """Generate a unique circular ID from available data."""
        import hashlib
        
        # Try to extract RBI reference number from title
        ref_match = re.search(r'(DPSS\.CO\.[A-Z0-9/.-]+|RBI/\d{4}-\d{2}/\d+)', title, re.IGNORECASE)
        if ref_match:
            return ref_match.group(1).replace("/", "-").replace(".", "-")
        
        # Generate hash-based ID
        combined = f"{title}_{url}_{date_text}"
        hash_id = hashlib.md5(combined.encode()).hexdigest()[:12]
        return f"RBI-PAPG-{hash_id}"

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_text:
            return None

        formats = [
            "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
            "%B %d, %Y", "%b %d, %Y",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_text.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def scrape_all_categories(
        self,
        year: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Scrape all PA/PG related categories.

        Args:
            year: Optional year filter
            progress_callback: Optional async callback for progress updates

        Returns:
            Combined statistics for all categories
        """
        overall_stats = {
            "total": 0, "new": 0, "duplicates": 0, "errors": 0,
            "by_category": {},
        }

        categories_to_scrape = ["master_directions", "circulars", "notifications"]

        for category in categories_to_scrape:
            if progress_callback:
                try:
                    await progress_callback(f"Scraping {PAPG_CATEGORY_LABELS.get(category, category)}...")
                except Exception:
                    pass

            cat_stats = await self.scrape_rbi_circulars(
                category=category,
                year=year,
                progress_callback=progress_callback
            )

            overall_stats["by_category"][category] = cat_stats
            overall_stats["total"] += cat_stats["total"]
            overall_stats["new"] += cat_stats["new"]
            overall_stats["duplicates"] += cat_stats["duplicates"]
            overall_stats["errors"] += cat_stats["errors"]

            await asyncio.sleep(REQUEST_DELAY)

        return overall_stats

    async def list_circulars(
        self,
        category: Optional[str] = None,
        year: Optional[str] = None,
        search: Optional[str] = None,
        processed: Optional[bool] = None,
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        """
        List scraped PA/PG circulars with filters and pagination.

        Args:
            category: Filter by category
            year: Filter by year
            search: Text search in title
            processed: Filter by processed status
            page: Page number (1-indexed)
            size: Items per page

        Returns:
            Dict with items and pagination info
        """
        query = {}

        if category and category != "all":
            query["category"] = category

        if year and year != "all":
            year_int = int(year)
            query["date"] = {
                "$gte": datetime(year_int, 1, 1, tzinfo=timezone.utc),
                "$lt": datetime(year_int + 1, 1, 1, tzinfo=timezone.utc)
            }

        if search:
            query["$text"] = {"$search": search}

        if processed is not None:
            query["processed"] = processed

        skip = (page - 1) * size
        total = await self.collection.count_documents(query)

        cursor = self.collection.find(query).sort("date", -1).skip(skip).limit(size)
        items = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(doc)

        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size,
        }

    async def get_circular(self, circular_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single circular by ID.

        Args:
            circular_id: The circular's unique ID

        Returns:
            Circular document or None
        """
        doc = await self.collection.find_one({"circular_id": circular_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get scraping statistics.

        Returns:
            Dict with stats including counts by category and status
        """
        total = await self.collection.count_documents({})
        processed = await self.collection.count_documents({"processed": True})
        pending = total - processed

        # Get counts by category
        pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_category = []
        async for doc in self.collection.aggregate(pipeline):
            by_category.append({
                "category": doc["_id"],
                "label": PAPG_CATEGORY_LABELS.get(doc["_id"], doc["_id"]),
                "count": doc["count"]
            })

        # Get counts by year
        pipeline_year = [
            {"$project": {"year": {"$year": "$date"}}},
            {"$group": {"_id": "$year", "count": {"$sum": 1}}},
            {"$sort": {"_id": -1}}
        ]
        by_year = []
        async for doc in self.collection.aggregate(pipeline_year):
            if doc["_id"]:
                by_year.append({"year": doc["_id"], "count": doc["count"]})

        return {
            "total": total,
            "processed": processed,
            "pending": pending,
            "by_category": by_category,
            "by_year": by_year,
        }

    async def mark_as_processed(
        self,
        circular_id: str,
        clause_count: int = 0,
        processed_by: str = ""
    ) -> bool:
        """
        Mark a circular as processed.

        Args:
            circular_id: The circular's unique ID
            clause_count: Number of clauses extracted
            processed_by: User/system that processed it

        Returns:
            True if updated, False otherwise
        """
        result = await self.collection.update_one(
            {"circular_id": circular_id},
            {
                "$set": {
                    "processed": True,
                    "processed_at": datetime.now(timezone.utc),
                    "clause_count": clause_count,
                    "processed_by": processed_by,
                }
            }
        )
        return result.modified_count > 0

    async def delete_circular(self, circular_id: str) -> bool:
        """
        Delete a circular.

        Args:
            circular_id: The circular's unique ID

        Returns:
            True if deleted, False otherwise
        """
        result = await self.collection.delete_one({"circular_id": circular_id})
        return result.deleted_count > 0


# Known PA/PG Master Directions and key circulars (for seeding)
KNOWN_PAPG_REGULATIONS = [
    {
        "circular_id": "RBI-MD-PAPG-2025",
        "title": "Master Direction on Regulation of Payment Aggregators (Consolidated) 2025",
        "description": "Consolidated Master Direction issued by RBI on Payment Aggregators covering authorization, capital requirements, merchant onboarding, settlement, escrow accounts, fraud monitoring, and PA-P regulation.",
        "date": datetime(2025, 9, 15, tzinfo=timezone.utc),
        "category": "master_directions",
        "rbi_para": "Full Direction",
        "url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11192",
        "criticality": "high",
        "source": "RBI",
    },
    {
        "circular_id": "RBI-DPSS-CO-PD-2024-25-1",
        "title": "Guidelines on Regulation of Payment Aggregators - Clarifications",
        "description": "Clarifications on various aspects of PA regulations including timeline extensions and compliance requirements.",
        "date": datetime(2025, 2, 28, tzinfo=timezone.utc),
        "category": "circulars",
        "rbi_para": "Circular",
        "source": "RBI",
    },
    {
        "circular_id": "RBI-DPSS-CO-PD-2024-25-2",
        "title": "PA-P (Physical Point of Sale) Regulation Guidelines",
        "description": "Guidelines for Payment Aggregators operating in Physical POS space, including T+0 settlement requirements for physical transactions.",
        "date": datetime(2025, 10, 1, tzinfo=timezone.utc),
        "category": "circulars",
        "rbi_para": "Circular",
        "source": "RBI",
    },
    {
        "circular_id": "RBI-DPSS-CO-PD-2024-25-3",
        "title": "Merchant Due Diligence and KYC Requirements for PAs",
        "description": "Enhanced KYC and due diligence requirements for merchant onboarding by payment aggregators, with deadline of September 15, 2026 for pre-2026 onboardings.",
        "date": datetime(2025, 9, 20, tzinfo=timezone.utc),
        "category": "circulars",
        "rbi_para": "Para 7",
        "source": "RBI",
    },
]


async def seed_known_regulations(db) -> int:
    """
    Seed known PA/PG regulations into the database.

    Args:
        db: MongoDB database instance

    Returns:
        Number of regulations seeded
    """
    collection = db["rbi_papg_circulars"]
    seeded = 0

    for reg in KNOWN_PAPG_REGULATIONS:
        existing = await collection.find_one({"circular_id": reg["circular_id"]})
        if not existing:
            reg["scraped_at"] = datetime.now(timezone.utc)
            reg["processed"] = False
            await collection.insert_one(reg)
            seeded += 1
            logger.info(f"Seeded PA/PG regulation: {reg['title']}")

    return seeded
