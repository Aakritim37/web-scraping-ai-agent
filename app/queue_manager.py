# app/queue_manager.py
import asyncio
from typing import Dict, Any, Set, List

class ScrapeQueueCoordinator:
    """
    Orchestrates concurrent worker execution thresholds and async task queues.
    Implements a thread-safe singleton state pattern.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ScrapeQueueCoordinator, cls).__new__(cls)
            cls._instance.max_concurrency = 3
            cls._instance.semaphore = asyncio.Semaphore(3)
            cls._instance.active_slots = 0
            cls._instance.processed_count = 0
            cls._instance.queue = asyncio.Queue()
            cls._instance.active_workers = []
        return cls._instance

    def reset(self, concurrency_limit: int = 3):
        """
        Reinitializes the queue and worker semaphore slots.
        """
        self.max_concurrency = concurrency_limit
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.active_slots = 0
        self.processed_count = 0
        self.queue = asyncio.Queue()
        for w in self.active_workers:
            w.cancel()
        self.active_workers = []

    async def add_task(self, url: str, kwargs: dict) -> asyncio.Future:
        """
        Enqueues a target scraping run and returns an awaitable Future for its results.
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put((url, kwargs, future))
        return future

    def start_workers(self, num_workers: int = 3):
        """
        Spawns concurrent background worker tasks to process the queue.
        """
        for _ in range(num_workers):
            w = asyncio.create_task(self._worker_loop())
            self.active_workers.append(w)

    async def _worker_loop(self):
        from app.main import run_prototype
        while True:
            try:
                url, kwargs, future = await self.queue.get()
            except asyncio.CancelledError:
                break
            
            try:
                # Enforce concurrency thresholds via Semaphore
                async with self.semaphore:
                    self.active_slots += 1
                    try:
                        res = await run_prototype(url, **kwargs)
                        if not future.done():
                            future.set_result(res)
                    finally:
                        self.active_slots = max(0, self.active_slots - 1)
                        self.processed_count += 1
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                self.queue.task_done()

    def get_diagnostics(self) -> dict:
        """
        Returns active queue diagnostics.
        """
        # Fetch locks dynamically from global main state if active
        try:
            from app.main import ACTIVE_SCRAPE_URLS
            locks_list = list(ACTIVE_SCRAPE_URLS)
        except ImportError:
            locks_list = []
            
        return {
            "active_concurrency_slots": self.active_slots,
            "task_backlog": self.queue.qsize(),
            "total_processed_tasks": self.processed_count,
            "active_locks": locks_list
        }
