"""
NPCI Circular Scraper Service
Scrapes NPCI circulars via their Strapi REST API (no Selenium/Playwright needed).

NPCI API Details (reverse-engineered from their React SPA):
- Base URL: https://www.npci.org.in
- Circulars endpoint: GET /api/circulars/{product}?pageNum={n}&year={yyyy}&sort=desc&size=10
- Metadata endpoint: GET /api/circulars-and-notifications-page/{product} (returns available years)
- Search endpoint: GET /api/circulars/searchByName/{product}?searchKey={text}&year={yyyy}
- Products: upi, nach, netc, imps, nfs, cts, bhim-aadhaar, aeps, e-rupi, rupay, e-kyc-setu-system, others
"""

import asyncio
import httpx
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# All supported NPCI products
NPCI_PRODUCTS = [
    "upi", "nach", "netc", "imps", "nfs", "cts",
    "bhim-aadhaar", "aeps", "e-rupi", "rupay",
    "e-kyc-setu-system", "others"
]

NPCI_PRODUCT_LABELS = {
    "upi": "UPI",
    "nach": "NACH",
    "netc": "NETC",
    "imps": "IMPS",
    "nfs": "NFS",
    "cts": "CTS",
    "bhim-aadhaar": "BHIM Aadhaar",
    "aeps": "AePS",
    "e-rupi": "e-RUPI",
    "rupay": "RuPay",
    "e-kyc-setu-system": "e-KYC Setu",
    "others": "Others"
}

NPCI_BASE_URL = "https://www.npci.org.in"
REQUEST_DELAY = 0.5  # seconds between requests to be respectful
DEFAULT_PAGE_SIZE = 10
UPLOAD_DIR = "/tmp/uploads/npci"


class NPCIScraper:
    """
    Scraper for NPCI circulars using their public Strapi REST API.
    Stores scraped circulars in MongoDB 'npci_circulars' collection.
    """

    def __init__(self, db):
        """
        Initialize the NPCI scraper service.

        Args:
            db: MongoDB database instance (Motor async driver)
        """
        self.db = db
        self.collection = db["npci_circulars"]
        self.base_url = NPCI_BASE_URL
        self.headers = {
            "User-Agent": "CompliAI/1.0 (Compliance Monitoring System)",
            "Accept": "application/json",
            "Referer": "https://www.npci.org.in/",
        }
        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make an HTTP GET request with error handling and rate limiting.

        Args:
            url: Full URL to fetch
            params: Optional query parameters

        Returns:
            JSON response dict or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
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

    async def get_available_years(self, product: str) -> List[Dict[str, Any]]:
        """
        Get available years for a specific NPCI product.
        Calls /api/circulars-and-notifications-page/{product}

        Args:
            product: NPCI product slug (e.g., 'upi', 'nach')

        Returns:
            List of year info dicts with 'year' and 'label' keys
        """
        url = f"{self.base_url}/api/circulars-and-notifications-page/{product}"
        data = await self._make_request(url)

        if not data:
            # Return default years if API call fails
            logger.warning(f"Failed to get years for {product}, using defaults")
            return [
                {"year": str(y), "label": f"FY {y}-{str(y+1)[2:]}"}
                for y in range(2025, 2015, -1)
            ]

        # Extract year information from response
        years = []
        try:
            # The API typically returns year data in the response
            if isinstance(data, dict):
                # Try different response structures
                year_data = data.get("data", {})
                if isinstance(year_data, dict):
                    year_list = year_data.get("years", [])
                    if year_list:
                        for y in year_list:
                            if isinstance(y, dict):
                                years.append({
                                    "year": str(y.get("year", y.get("value", ""))),
                                    "label": y.get("label", y.get("name", str(y.get("year", ""))))
                                })
                            elif isinstance(y, (int, str)):
                                years.append({"year": str(y), "label": str(y)})
        except Exception as e:
            logger.warning(f"Error parsing years for {product}: {e}")

        # Fallback to default years if none parsed
        if not years:
            years = [
                {"year": str(y), "label": f"FY {y}-{str(y+1)[2:]}"}
                for y in range(2025, 2015, -1)
            ]

        return years

    async def scrape_circulars(
        self,
        product: str,
        year: str,
        page: int = 1,
        size: int = DEFAULT_PAGE_SIZE
    ) -> Dict[str, Any]:
        """
        Scrape circulars for a specific product, year, and page.
        Calls /api/circulars/{product}?pageNum={n}&year={yyyy}&sort=desc&size={size}

        Args:
            product: NPCI product slug
            year: Year string (e.g., '2025')
            page: Page number (1-indexed)
            size: Number of results per page

        Returns:
            Dict with 'files', 'totalCount', 'pageNum', 'size' keys
        """
        url = f"{self.base_url}/api/circulars/{product}"
        params = {
            "pageNum": page,
            "year": year,
            "sort": "desc",
            "size": size,
        }

        data = await self._make_request(url, params=params)

        if not data:
            return {"files": [], "totalCount": 0, "pageNum": page, "size": size}

        try:
            result_data = data.get("data", {})
            files = result_data.get("files", [])
            total_count = result_data.get("totalCount", 0)

            return {
                "files": files,
                "totalCount": total_count,
                "pageNum": result_data.get("pageNum", page),
                "size": result_data.get("size", size),
            }
        except Exception as e:
            logger.error(f"Error parsing circulars response for {product}/{year}: {e}")
            return {"files": [], "totalCount": 0, "pageNum": page, "size": size}

    async def search_circulars(
        self,
        product: str,
        search_key: str,
        year: str
    ) -> List[Dict[str, Any]]:
        """
        Search circulars by name for a product and year.
        Calls /api/circulars/searchByName/{product}?searchKey={text}&year={yyyy}

        Args:
            product: NPCI product slug
            search_key: Search text
            year: Year string

        Returns:
            List of matching circular dicts
        """
        url = f"{self.base_url}/api/circulars/searchByName/{product}"
        params = {
            "searchKey": search_key,
            "year": year,
        }

        data = await self._make_request(url, params=params)

        if not data:
            return []

        try:
            result_data = data.get("data", {})
            return result_data.get("files", [])
        except Exception as e:
            logger.error(f"Error parsing search results for {product}: {e}")
            return []

    def _parse_circular(self, raw: Dict, product: str, year: str) -> Dict[str, Any]:
        """
        Parse a raw circular API response into our MongoDB document format.

        Args:
            raw: Raw circular dict from NPCI API
            product: NPCI product slug
            year: Year string

        Returns:
            Formatted circular document for MongoDB
        """
        npci_id = raw.get("id")
        file_name = raw.get("fileName", "")
        media = raw.get("media", {})
        media_url = media.get("url", "") if isinstance(media, dict) else ""
        pdf_url = f"{self.base_url}{media_url}" if media_url else ""
        media_type = raw.get("mediaType", "pdf")
        is_downloadable = raw.get("isDownloadable", True)

        return {
            "npci_id": npci_id,
            "title": file_name,
            "product": product,
            "product_label": NPCI_PRODUCT_LABELS.get(product, product),
            "year": year,
            "year_label": f"FY {year}",
            "pdf_url": pdf_url,
            "media_type": media_type,
            "is_downloadable": is_downloadable,
            "pdf_downloaded": False,
            "local_pdf_path": None,
            "raw_text": None,
            "clauses": [],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "processed_at": None,
            "raw_response": raw,
        }

    async def _store_circular(self, circular: Dict[str, Any]) -> bool:
        """
        Store a circular in MongoDB with dedup by npci_id.

        Args:
            circular: Circular document to store

        Returns:
            True if new circular stored, False if duplicate
        """
        try:
            # Dedup by npci_id
            existing = await self.collection.find_one({"npci_id": circular["npci_id"]})
            if existing:
                # Update scraped_at timestamp
                await self.collection.update_one(
                    {"npci_id": circular["npci_id"]},
                    {"$set": {"scraped_at": circular["scraped_at"]}}
                )
                return False

            await self.collection.insert_one(circular)
            return True
        except Exception as e:
            logger.error(f"Error storing circular {circular.get('npci_id')}: {e}")
            return False

    async def scrape_product_year(
        self,
        product: str,
        year: str,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Scrape all circulars for a specific product and year, paginating through all pages.

        Args:
            product: NPCI product slug
            year: Year string
            progress_callback: Optional async callback(message: str) for progress updates

        Returns:
            Dict with scraping results: total, new, duplicates, errors
        """
        stats = {"total": 0, "new": 0, "duplicates": 0, "errors": 0}
        page = 1

        while True:
            if progress_callback:
                await progress_callback(f"Scraping {NPCI_PRODUCT_LABELS.get(product, product)} {year} - page {page}...")

            result = await self.scrape_circulars(product, year, page=page)
            files = result.get("files", [])
            total_count = result.get("totalCount", 0)

            if not files:
                break

            for raw_file in files:
                stats["total"] += 1
                circular = self._parse_circular(raw_file, product, year)

                if circular["npci_id"] is None:
                    stats["errors"] += 1
                    continue

                is_new = await self._store_circular(circular)
                if is_new:
                    stats["new"] += 1
                else:
                    stats["duplicates"] += 1

            # Check if we've fetched all pages
            fetched_so_far = page * result.get("size", DEFAULT_PAGE_SIZE)
            if fetched_so_far >= total_count or len(files) < result.get("size", DEFAULT_PAGE_SIZE):
                break

            page += 1
            # Rate limiting
            await asyncio.sleep(REQUEST_DELAY)

        return stats

    async def scrape_all_circulars(
        self,
        product: str,
        years: Optional[List[str]] = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Scrape all circulars for a product across all available years.

        Args:
            product: NPCI product slug
            years: Optional list of years to scrape. If None, gets all available years.
            progress_callback: Optional async callback(message: str) for progress updates

        Returns:
            Dict with overall scraping results
        """
        if product not in NPCI_PRODUCTS:
            raise ValueError(f"Unknown product: {product}. Must be one of: {NPCI_PRODUCTS}")

        overall_stats = {"total": 0, "new": 0, "duplicates": 0, "errors": 0, "years_scraped": 0}

        if years is None:
            if progress_callback:
                await progress_callback(f"Fetching available years for {NPCI_PRODUCT_LABELS.get(product, product)}...")
            year_list = await self.get_available_years(product)
            years = [y["year"] for y in year_list]

        for year in years:
            if progress_callback:
                await progress_callback(f"Scraping {NPCI_PRODUCT_LABELS.get(product, product)} - Year {year}...")

            year_stats = await self.scrape_product_year(product, year, progress_callback)

            overall_stats["total"] += year_stats["total"]
            overall_stats["new"] += year_stats["new"]
            overall_stats["duplicates"] += year_stats["duplicates"]
            overall_stats["errors"] += year_stats["errors"]
            overall_stats["years_scraped"] += 1

            # Rate limiting between years
            await asyncio.sleep(REQUEST_DELAY)

        if progress_callback:
            await progress_callback(
                f"Completed scraping {NPCI_PRODUCT_LABELS.get(product, product)}: "
                f"{overall_stats['new']} new, {overall_stats['duplicates']} duplicates, "
                f"{overall_stats['errors']} errors out of {overall_stats['total']} total"
            )

        return overall_stats

    async def scrape_all_products(self, progress_callback=None) -> Dict[str, Any]:
        """
        Scrape circulars for all NPCI products across all years.

        Args:
            progress_callback: Optional async callback(message: str) for progress updates

        Returns:
            Dict with scraping results per product and overall totals
        """
        results = {
            "products": {},
            "total": 0,
            "new": 0,
            "duplicates": 0,
            "errors": 0,
        }

        for product in NPCI_PRODUCTS:
            if progress_callback:
                await progress_callback(f"Starting scrape for {NPCI_PRODUCT_LABELS.get(product, product)}...")

            try:
                product_stats = await self.scrape_all_circulars(product, progress_callback=progress_callback)
                results["products"][product] = product_stats
                results["total"] += product_stats["total"]
                results["new"] += product_stats["new"]
                results["duplicates"] += product_stats["duplicates"]
                results["errors"] += product_stats["errors"]
            except Exception as e:
                logger.error(f"Error scraping product {product}: {e}")
                results["products"][product] = {"error": str(e)}

        if progress_callback:
            await progress_callback(
                f"Completed scraping all products: "
                f"{results['new']} new, {results['duplicates']} duplicates, "
                f"{results['errors']} errors out of {results['total']} total"
            )

        return results

    async def download_pdf(self, pdf_url: str, npci_id: int = None) -> Optional[str]:
        """
        Download a PDF from NPCI and save to local storage.

        Args:
            pdf_url: Full URL of the PDF to download
            npci_id: Optional NPCI circular ID for naming

        Returns:
            Local file path or None on error
        """
        if not pdf_url:
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(pdf_url, headers=self.headers)
                response.raise_for_status()

                # Generate filename
                if npci_id:
                    filename = f"npci_circular_{npci_id}.pdf"
                else:
                    # Extract from URL
                    url_path = pdf_url.split("/")[-1]
                    filename = url_path if url_path.endswith(".pdf") else f"npci_{hash(pdf_url)}.pdf"

                filepath = os.path.join(UPLOAD_DIR, filename)

                with open(filepath, "wb") as f:
                    f.write(response.content)

                # Update MongoDB record
                if npci_id:
                    await self.collection.update_one(
                        {"npci_id": npci_id},
                        {"$set": {
                            "pdf_downloaded": True,
                            "local_pdf_path": filepath,
                        }}
                    )

                logger.info(f"Downloaded PDF: {filepath}")
                return filepath

        except Exception as e:
            logger.error(f"Error downloading PDF from {pdf_url}: {e}")
            return None

    async def get_circular_by_id(self, circular_id: str) -> Optional[Dict]:
        """Get a single circular from MongoDB by its _id."""
        from bson import ObjectId
        try:
            doc = await self.collection.find_one({"_id": ObjectId(circular_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Error getting circular {circular_id}: {e}")
            return None

    async def get_circular_by_npci_id(self, npci_id: int) -> Optional[Dict]:
        """Get a single circular from MongoDB by its NPCI ID."""
        try:
            doc = await self.collection.find_one({"npci_id": npci_id})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Error getting circular by npci_id {npci_id}: {e}")
            return None

    async def list_circulars(
        self,
        product: Optional[str] = None,
        year: Optional[str] = None,
        search: Optional[str] = None,
        processed_only: bool = False,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """
        List circulars from MongoDB with filtering and pagination.

        Args:
            product: Filter by product slug
            year: Filter by year
            search: Search text in title
            processed_only: Legacy boolean — equivalent to ``status="completed"``.
            status: Richer status filter. One of:
                "completed" - LLM extraction succeeded
                "pending"   - never processed (or processed_status missing)
                "failed"    - LLM extraction was attempted and failed
                "processing"- currently in-flight
                ``None``    - no status filter
                If both ``processed_only`` and ``status`` are passed, ``status`` wins.
            page: Page number (1-indexed)
            size: Results per page

        Returns:
            Dict with 'items', 'total', 'page', 'size', 'pages'
        """
        query = {}

        if product:
            query["product"] = product
        if year:
            query["year"] = year
        if search:
            query["title"] = {"$regex": search, "$options": "i"}

        if status:
            status_norm = status.strip().lower()
            if status_norm == "pending":
                # Anything that hasn't successfully completed and isn't actively
                # in-flight or marked failed is "pending" from the user's POV.
                query["$or"] = [
                    {"processing_status": {"$exists": False}},
                    {"processing_status": {"$nin": ["completed", "failed", "processing"]}},
                ]
            elif status_norm in ("completed", "failed", "processing"):
                query["processing_status"] = status_norm
            # any other value: treat as "no filter" silently
        elif processed_only:
            # Real LLM extraction succeeded — not just any processed_at marker
            query["processing_status"] = "completed"

        try:
            total = await self.collection.count_documents(query)
            skip = (page - 1) * size

            cursor = self.collection.find(query).sort("scraped_at", -1).skip(skip).limit(size)
            items = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                items.append(doc)

            pages = (total + size - 1) // size if size > 0 else 0

            return {
                "items": items,
                "total": total,
                "page": page,
                "size": size,
                "pages": pages,
            }
        except Exception as e:
            logger.error(f"Error listing circulars: {e}")
            return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}

    async def get_product_stats(self) -> List[Dict[str, Any]]:
        """
        Get circular counts per product.

        A circular is counted as "processed" only when its processing_status is
        "completed" (i.e. real LLM clause extraction succeeded). Circulars with
        a `processed_at` timestamp but no `processing_status == "completed"`
        (legacy placeholder runs) are NOT counted as processed; they appear in
        `pending`.

        Returns:
            List of dicts with 'product', 'label', 'total', 'processed',
            'pending', 'failed', 'in_progress'.
        """
        stats = []

        try:
            pipeline = [
                {"$group": {
                    "_id": "$product",
                    "total": {"$sum": 1},
                    "processed": {
                        "$sum": {"$cond": [
                            {"$eq": ["$processing_status", "completed"]}, 1, 0
                        ]}
                    },
                    "failed": {
                        "$sum": {"$cond": [
                            {"$eq": ["$processing_status", "failed"]}, 1, 0
                        ]}
                    },
                    "in_progress": {
                        "$sum": {"$cond": [
                            {"$eq": ["$processing_status", "processing"]}, 1, 0
                        ]}
                    },
                }},
                {"$sort": {"total": -1}},
            ]

            async for doc in self.collection.aggregate(pipeline):
                product = doc["_id"]
                processed = doc["processed"]
                failed = doc["failed"]
                in_progress = doc["in_progress"]
                pending = doc["total"] - processed - failed - in_progress
                stats.append({
                    "product": product,
                    "label": NPCI_PRODUCT_LABELS.get(product, product),
                    "total": doc["total"],
                    "processed": processed,
                    "failed": failed,
                    "in_progress": in_progress,
                    "pending": pending,
                })
        except Exception as e:
            logger.error(f"Error getting product stats: {e}")

        # Include products with zero circulars
        existing_products = {s["product"] for s in stats}
        for product in NPCI_PRODUCTS:
            if product not in existing_products:
                stats.append({
                    "product": product,
                    "label": NPCI_PRODUCT_LABELS.get(product, product),
                    "total": 0,
                    "processed": 0,
                    "failed": 0,
                    "in_progress": 0,
                    "pending": 0,
                })

        return stats

    async def get_overall_stats(self) -> Dict[str, Any]:
        """
        Get overall scraping statistics.

        "processed" means real LLM extraction succeeded
        (processing_status == "completed"). A non-null `processed_at` alone is
        NOT enough — legacy placeholder runs left rows in that state without
        any real clause extraction.

        Returns:
            Dict with total, processed, pending, failed, in_progress,
            by_product, last_scraped.
        """
        try:
            total = await self.collection.count_documents({})
            processed = await self.collection.count_documents(
                {"processing_status": "completed"}
            )
            failed = await self.collection.count_documents(
                {"processing_status": "failed"}
            )
            in_progress = await self.collection.count_documents(
                {"processing_status": "processing"}
            )
            pending = total - processed - failed - in_progress

            # Get last scraped time
            last_doc = await self.collection.find_one(
                {},
                sort=[("scraped_at", -1)]
            )
            last_scraped = last_doc.get("scraped_at") if last_doc else None

            product_stats = await self.get_product_stats()

            return {
                "total": total,
                "processed": processed,
                "pending": pending,
                "failed": failed,
                "in_progress": in_progress,
                "last_scraped": last_scraped,
                "by_product": product_stats,
            }
        except Exception as e:
            logger.error(f"Error getting overall stats: {e}")
            return {
                "total": 0,
                "processed": 0,
                "pending": 0,
                "failed": 0,
                "in_progress": 0,
                "last_scraped": None,
                "by_product": [],
            }

    async def ensure_indexes(self):
        """Create MongoDB indexes for efficient querying."""
        try:
            await self.collection.create_index("npci_id", unique=True, sparse=True)
            await self.collection.create_index("product")
            await self.collection.create_index("year")
            await self.collection.create_index([("product", 1), ("year", 1)])
            await self.collection.create_index("scraped_at")
            await self.collection.create_index("processed_at")
            await self.collection.create_index([("title", "text")])
            logger.info("NPCI circulars indexes created")
        except Exception as e:
            logger.warning(f"Error creating NPCI indexes: {e}")
