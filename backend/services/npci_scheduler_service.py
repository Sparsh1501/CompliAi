"""
NPCI Circular Scheduler Service
Feature #220: Scheduled NPCI circular scraping with new circular detection.

Provides automated periodic scraping that:
1. Checks for new NPCI circulars on a configurable interval (default daily)
2. Tracks last_scraped_at per product to only fetch new circulars
3. Auto-triggers LLM clause extraction on newly scraped circulars
4. Creates notifications when new circulars are detected
5. Optionally auto-generates review tasks for new circulars
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Default schedule interval in hours
DEFAULT_INTERVAL_HOURS = 24
MIN_INTERVAL_HOURS = 1
MAX_INTERVAL_HOURS = 168  # 1 week


class NPCISchedulerService:
    """
    Manages scheduled NPCI circular scraping with new circular detection.
    Uses asyncio background tasks for scheduling (no external dependencies).
    Persists schedule config and per-product tracking in MongoDB app_settings.
    """

    def __init__(self, db, npci_scraper):
        """
        Initialize the scheduler service.

        Args:
            db: MongoDB database instance (Motor async driver)
            npci_scraper: NPCIScraper service instance
        """
        self.db = db
        self.npci_scraper = npci_scraper
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_run_result: Optional[Dict] = None
        self._next_run_at: Optional[str] = None

    async def get_schedule_config(self) -> Dict[str, Any]:
        """
        Get the current schedule configuration from MongoDB.

        Returns:
            Schedule config dict with enabled, interval_hours, auto_process,
            auto_create_tasks, products settings.
        """
        config = await self.db.app_settings.find_one({"key": "npci_schedule_config"})
        if config and config.get("value"):
            return config["value"]

        # Return defaults
        return {
            "enabled": False,
            "interval_hours": DEFAULT_INTERVAL_HOURS,
            "auto_process": True,
            "auto_create_tasks": False,
            "products": [],  # Empty = all products
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def save_schedule_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save schedule configuration to MongoDB.

        Args:
            config: Updated config dict

        Returns:
            Saved config
        """
        config["updated_at"] = datetime.now(timezone.utc).isoformat()

        await self.db.app_settings.update_one(
            {"key": "npci_schedule_config"},
            {"$set": {"key": "npci_schedule_config", "value": config}},
            upsert=True,
        )
        return config

    async def get_product_tracking(self) -> Dict[str, Any]:
        """
        Get per-product last_scraped_at tracking data.

        Returns:
            Dict mapping product slug to last_scraped_at timestamp
        """
        doc = await self.db.app_settings.find_one({"key": "npci_product_tracking"})
        if doc and doc.get("value"):
            return doc["value"]
        return {}

    async def update_product_tracking(self, product: str, scraped_at: str, new_count: int = 0):
        """
        Update last_scraped_at for a specific product.

        Args:
            product: NPCI product slug
            scraped_at: ISO timestamp of scrape
            new_count: Number of new circulars found
        """
        tracking = await self.get_product_tracking()
        tracking[product] = {
            "last_scraped_at": scraped_at,
            "new_count": new_count,
            "total_scrapes": tracking.get(product, {}).get("total_scrapes", 0) + 1,
        }

        await self.db.app_settings.update_one(
            {"key": "npci_product_tracking"},
            {"$set": {"key": "npci_product_tracking", "value": tracking}},
            upsert=True,
        )

    async def get_schedule_status(self) -> Dict[str, Any]:
        """
        Get the current scheduler status including last run and next run.

        Returns:
            Status dict with running, enabled, last_run, next_run, etc.
        """
        config = await self.get_schedule_config()
        tracking = await self.get_product_tracking()

        # Get last run result from history
        last_run = await self.db.app_settings.find_one({"key": "npci_last_scheduled_run"})
        last_run_data = last_run.get("value") if last_run else None

        return {
            "scheduler_active": self._running,
            "enabled": config.get("enabled", False),
            "interval_hours": config.get("interval_hours", DEFAULT_INTERVAL_HOURS),
            "auto_process": config.get("auto_process", True),
            "auto_create_tasks": config.get("auto_create_tasks", False),
            "next_run_at": self._next_run_at,
            "last_run": last_run_data,
            "product_tracking": tracking,
        }

    async def _create_notification(self, title: str, message: str, link: str = "/npci-circulars"):
        """
        Create a notification for all admin users about new NPCI circulars.

        Args:
            title: Notification title
            message: Notification body
            link: Link to navigate to
        """
        try:
            # Find all admin users to notify
            admin_users = await self.db.users.find(
                {"role": {"$in": ["admin", "compliance_officer"]}},
                {"id": 1, "_id": 0}
            ).to_list(100)

            if not admin_users:
                # Fallback: notify all users
                admin_users = await self.db.users.find(
                    {},
                    {"id": 1, "_id": 0}
                ).to_list(50)

            for user in admin_users:
                user_id = user.get("id")
                if not user_id:
                    continue

                notification = {
                    "id": f"npci_notify_{uuid.uuid4().hex[:12]}",
                    "user_id": user_id,
                    "type": "npci_new_circulars",
                    "title": title,
                    "message": message,
                    "link": link,
                    "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await self.db.notifications.insert_one(notification)

            logger.info(f"Created NPCI notification for {len(admin_users)} users: {title}")
        except Exception as e:
            logger.error(f"Failed to create NPCI notification: {e}")

    async def _auto_process_circulars(self, circular_ids: List[str]) -> Dict[str, int]:
        """
        Auto-trigger real LLM clause extraction on newly scraped circulars.

        Uses the full NPCIProcessingService.process_circular() pipeline so that
        a circular is only marked as processed (processing_status="completed",
        processed_at=now) when actual LLM extraction succeeds. If the LLM is
        unavailable (no API credits, Ollama not running, etc.) the circular is
        marked processing_status="failed" instead of being silently flipped to
        "processed" with placeholder data.

        Args:
            circular_ids: List of MongoDB _id strings for new circulars

        Returns:
            Dict with counts: {"succeeded": int, "failed": int}
        """
        result = {"succeeded": 0, "failed": 0}
        if not circular_ids:
            return result

        # Get the real processing service from server module (lazy import to
        # avoid circulars; the scheduler is constructed before server module
        # initializes the service).
        try:
            import sys
            srv = sys.modules.get('__main__') or sys.modules.get('server')
            processing_service = getattr(srv, 'npci_processing_service', None) if srv else None
        except Exception:
            processing_service = None

        if processing_service is None:
            logger.error(
                "Auto-process skipped: NPCIProcessingService is not available on the server module. "
                "New circulars will remain in 'pending' status."
            )
            result["failed"] = len(circular_ids)
            return result

        for cid in circular_ids:
            try:
                circular = await self.npci_scraper.get_circular_by_id(cid)
                if not circular:
                    continue
                if circular.get("processing_status") == "completed":
                    continue

                proc_result = await processing_service.process_circular(cid)
                if proc_result.get("success"):
                    result["succeeded"] += 1
                else:
                    result["failed"] += 1
                    logger.warning(
                        f"Auto-process failed for circular {cid}: "
                        f"{proc_result.get('error', 'Unknown error')}"
                    )

                # Be nice to the LLM provider
                await asyncio.sleep(0.5)

            except Exception as e:
                result["failed"] += 1
                logger.error(f"Auto-process exception for circular {cid}: {e}", exc_info=True)

        logger.info(
            f"Auto-processed new circulars: {result['succeeded']} succeeded, "
            f"{result['failed']} failed (out of {len(circular_ids)} new)"
        )
        return result

    async def _auto_create_tasks(self, new_circulars: List[Dict]):
        """
        Auto-generate review tasks for newly scraped circulars.

        Args:
            new_circulars: List of new circular documents
        """
        if not new_circulars:
            return

        tasks_created = 0
        for circular in new_circulars:
            try:
                task_id = f"npci_review_{uuid.uuid4().hex[:12]}"
                task = {
                    "id": task_id,
                    "title": f"Review NPCI Circular: {circular.get('title', 'Unknown')[:100]}",
                    "description": (
                        f"A new NPCI circular has been detected for {circular.get('product_label', circular.get('product', 'Unknown'))}.\n\n"
                        f"Circular: {circular.get('title', 'Unknown')}\n"
                        f"Product: {circular.get('product_label', '')}\n"
                        f"Year: {circular.get('year', '')}\n\n"
                        f"Please review this circular for compliance impact and update policies if needed."
                    ),
                    "status": "todo",
                    "priority": "high",
                    "category": "regulatory_review",
                    "source": "npci_auto_scrape",
                    "source_id": circular.get("_id"),
                    "npci_circular_id": circular.get("npci_id"),
                    "assigned_to": None,
                    "due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                await self.db.tasks.insert_one(task)
                tasks_created += 1
            except Exception as e:
                logger.error(f"Failed to create review task for circular: {e}")

        logger.info(f"Auto-created {tasks_created} review tasks for new circulars")

    async def run_scheduled_scrape(self) -> Dict[str, Any]:
        """
        Execute a single scheduled scrape run.
        Scrapes configured products, detects new circulars,
        and triggers follow-up actions.

        Returns:
            Result dict with stats, new circulars, etc.
        """
        config = await self.get_schedule_config()
        from services.npci_scraper_service import NPCI_PRODUCTS

        products = config.get("products", [])
        if not products:
            products = NPCI_PRODUCTS

        # Get current year for scraping
        current_year = str(datetime.now(timezone.utc).year)

        result = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "products_scraped": 0,
            "total_found": 0,
            "new_circulars": 0,
            "duplicates": 0,
            "errors": 0,
            "auto_processed": 0,
            "tasks_created": 0,
            "product_results": {},
        }

        all_new_circular_ids = []
        all_new_circulars = []

        for product in products:
            try:
                # Scrape current year for the product
                stats = await self.npci_scraper.scrape_product_year(product, current_year)

                result["products_scraped"] += 1
                result["total_found"] += stats.get("total", 0)
                result["new_circulars"] += stats.get("new", 0)
                result["duplicates"] += stats.get("duplicates", 0)
                result["errors"] += stats.get("errors", 0)
                result["product_results"][product] = stats

                # Update per-product tracking
                await self.update_product_tracking(
                    product,
                    datetime.now(timezone.utc).isoformat(),
                    stats.get("new", 0),
                )

                # If new circulars found, collect their IDs
                if stats.get("new", 0) > 0:
                    # Get recently scraped circulars for this product
                    recent = await self.npci_scraper.list_circulars(
                        product=product,
                        year=current_year,
                        page=1,
                        size=stats["new"],
                    )
                    for item in recent.get("items", []):
                        # Schedule for auto-processing if it hasn't been
                        # successfully processed yet (pending or previously failed)
                        if item.get("_id") and item.get("processing_status") != "completed":
                            all_new_circular_ids.append(item["_id"])
                            all_new_circulars.append(item)

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Scheduled scrape failed for {product}: {e}")
                result["errors"] += 1
                result["product_results"][product] = {"error": str(e)}

        result["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Create notification if new circulars found
        if result["new_circulars"] > 0:
            await self._create_notification(
                title=f"{result['new_circulars']} New NPCI Circular(s) Detected",
                message=(
                    f"Scheduled scrape found {result['new_circulars']} new circular(s) "
                    f"across {result['products_scraped']} products. "
                    f"Review them in the NPCI Circulars page."
                ),
            )

        # Auto-process if enabled
        if config.get("auto_process", True) and all_new_circular_ids:
            ap_result = await self._auto_process_circulars(all_new_circular_ids)
            result["auto_processed"] = ap_result.get("succeeded", 0)
            result["auto_process_failed"] = ap_result.get("failed", 0)

        # Auto-create tasks if enabled
        if config.get("auto_create_tasks", False) and all_new_circulars:
            await self._auto_create_tasks(all_new_circulars)
            result["tasks_created"] = len(all_new_circulars)

        # Save last run result
        await self.db.app_settings.update_one(
            {"key": "npci_last_scheduled_run"},
            {"$set": {"key": "npci_last_scheduled_run", "value": result}},
            upsert=True,
        )

        self._last_run_result = result
        logger.info(
            f"Scheduled NPCI scrape completed: {result['new_circulars']} new, "
            f"{result['duplicates']} duplicates, {result['errors']} errors"
        )

        return result

    async def _scheduler_loop(self):
        """
        Main scheduler loop. Runs the scrape at configured intervals.
        """
        logger.info("NPCI scheduler loop started")
        self._running = True

        try:
            while self._running:
                config = await self.get_schedule_config()

                if not config.get("enabled", False):
                    logger.info("NPCI scheduler is disabled, stopping loop")
                    break

                interval_hours = max(
                    MIN_INTERVAL_HOURS,
                    min(config.get("interval_hours", DEFAULT_INTERVAL_HOURS), MAX_INTERVAL_HOURS)
                )

                # Calculate next run time
                next_run = datetime.now(timezone.utc) + timedelta(hours=interval_hours)
                self._next_run_at = next_run.isoformat()
                logger.info(f"NPCI scheduler: next run at {self._next_run_at}")

                # Wait for the interval
                try:
                    await asyncio.sleep(interval_hours * 3600)
                except asyncio.CancelledError:
                    logger.info("NPCI scheduler sleep cancelled")
                    break

                # Re-check if still enabled after sleeping
                config = await self.get_schedule_config()
                if not config.get("enabled", False):
                    logger.info("NPCI scheduler disabled during wait, stopping")
                    break

                # Run the scrape
                try:
                    logger.info("NPCI scheduler: starting scheduled scrape...")
                    await self.run_scheduled_scrape()
                except Exception as e:
                    logger.error(f"NPCI scheduled scrape failed: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("NPCI scheduler loop cancelled")
        except Exception as e:
            logger.error(f"NPCI scheduler loop error: {e}", exc_info=True)
        finally:
            self._running = False
            self._next_run_at = None
            logger.info("NPCI scheduler loop stopped")

    async def start(self):
        """
        Start the scheduler if enabled in config.
        Called during application startup.
        """
        config = await self.get_schedule_config()

        if config.get("enabled", False):
            if self._task and not self._task.done():
                logger.info("NPCI scheduler already running")
                return

            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info("NPCI scheduler started (background task)")
        else:
            logger.info("NPCI scheduler not enabled, skipping start")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._next_run_at = None
        logger.info("NPCI scheduler stopped")

    async def restart(self):
        """Restart the scheduler (stop then start)."""
        await self.stop()
        await self.start()

    async def toggle(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable the scheduler.

        Args:
            enabled: Whether to enable or disable

        Returns:
            Updated schedule config
        """
        config = await self.get_schedule_config()
        config["enabled"] = enabled
        config = await self.save_schedule_config(config)

        if enabled:
            await self.start()
        else:
            await self.stop()

        return config

    async def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update schedule configuration and restart if needed.

        Args:
            updates: Dict with fields to update (interval_hours, auto_process, etc.)

        Returns:
            Updated config
        """
        config = await self.get_schedule_config()

        # Apply updates
        if "interval_hours" in updates:
            config["interval_hours"] = max(
                MIN_INTERVAL_HOURS,
                min(int(updates["interval_hours"]), MAX_INTERVAL_HOURS)
            )
        if "auto_process" in updates:
            config["auto_process"] = bool(updates["auto_process"])
        if "auto_create_tasks" in updates:
            config["auto_create_tasks"] = bool(updates["auto_create_tasks"])
        if "products" in updates:
            config["products"] = updates["products"] if isinstance(updates["products"], list) else []
        if "enabled" in updates:
            config["enabled"] = bool(updates["enabled"])

        config = await self.save_schedule_config(config)

        # Restart scheduler if running to pick up new interval
        if config.get("enabled", False):
            await self.restart()
        elif not config.get("enabled", False) and self._running:
            await self.stop()

        return config

    async def trigger_now(self) -> Dict[str, Any]:
        """
        Manually trigger an immediate scheduled scrape run.

        Returns:
            Scrape result dict
        """
        logger.info("NPCI scheduler: manual trigger requested")
        result = await self.run_scheduled_scrape()
        return result
