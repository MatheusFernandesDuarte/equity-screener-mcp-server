"""ScrapeManager — background task queue for region scraping.

Rules enforced here:
- submit() is the only public method and ALWAYS returns immediately.
- A region is marked in_progress before it enters the queue (prevents
  duplicates even if the worker has not started yet).
- Only one thread holds _write_lock when writing to DuckDB.
- The browser driver is always closed after each scrape, even on failure.
- The region is removed from in_progress only after the write completes
  (or after failure cleanup), so re-submission cannot race.
"""

import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from src.scraper.engine import ScraperEngine
from src.storage.repository import StockRepository

logger = logging.getLogger(__name__)


class ScrapeManager:
    """Manages a background thread pool that scrapes regions on demand."""

    def __init__(
        self,
        engine_factory: Callable[[], ScraperEngine],
        repository: StockRepository,
        max_workers: int = 2,
    ) -> None:
        self._engine_factory = engine_factory
        self._repository = repository

        self._in_progress: set[str] = set()
        self._lock = threading.Lock()  # guards _in_progress mutations
        self._write_lock = threading.Lock()  # one DuckDB writer at a time

        self._queue: queue.Queue[str] = queue.Queue()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = threading.Event()

        for _ in range(max_workers):
            self._executor.submit(self._worker_loop)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, region: str) -> bool:
        """Queue a scrape for region. Returns False if already queued/running."""
        with self._lock:
            if region in self._in_progress:
                return False
            self._in_progress.add(region)  # mark BEFORE enqueue
            self._queue.put(region)
        logger.debug("Queued scrape for region: %s", region)
        return True

    def shutdown(self, wait: bool = True) -> None:
        """Signal workers to stop and optionally wait for them to finish."""
        self._shutdown.set()
        # Unblock each worker thread that is waiting on queue.get()
        for _ in range(self._executor._max_workers):
            self._queue.put(_SENTINEL)
        self._executor.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Consume regions from the queue until shutdown is signalled."""
        while True:
            region = self._queue.get()
            if region is _SENTINEL:
                break
            self._process(region)

    def _process(self, region: str) -> None:
        """Scrape one region and persist the result. Always cleans up."""
        engine: ScraperEngine | None = None
        try:
            engine = self._engine_factory()
            batch_ts = datetime.now(tz=timezone.utc)
            rows = engine.scrape(region)

            with self._write_lock:
                self._repository.insert_batch(region, rows, batch_ts)
                self._repository.upsert_region_metadata(region, batch_ts)

            logger.info("Scraped %d rows for region '%s'", len(rows), region)

        except Exception:
            logger.exception("Scrape failed for region '%s'", region)

        finally:
            if engine is not None:
                try:
                    engine.driver.quit()
                except Exception:
                    pass
            with self._lock:
                self._in_progress.discard(region)


# Sentinel value used to unblock worker threads during shutdown
_SENTINEL = object()
