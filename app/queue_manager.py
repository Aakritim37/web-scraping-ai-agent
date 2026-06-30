# app/queue_manager.py
import os
import hashlib
import asyncio
from typing import Dict, Any, List, Optional
from celery import Celery
import redis

# Redis Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Celery Application setup
celery_app = Celery("universal_scraper", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Redis client configuration
# We use a mock Redis client fallback if the connection fails during tests
try:
    redis_client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1)
    redis_client.ping()
except Exception:
    celery_app.conf.task_always_eager = True
    class InMemoryMockRedis:
        def __init__(self):
            self.storage = {}
        def ping(self):
            return True
        def get(self, key):
            k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            return self.storage.get(k)
        def set(self, key, value, nx=False, ex=None):
            k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            v = value.decode("utf-8") if isinstance(value, bytes) else str(value)
            if nx and k in self.storage:
                return False
            self.storage[k] = v
            return True
        def delete(self, key):
            k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            if k in self.storage:
                del self.storage[k]
                return 1
            return 0
        def incr(self, key):
            k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            val = int(self.storage.get(k, 0)) + 1
            self.storage[k] = str(val)
            return val
        def decr(self, key):
            k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            val = int(self.storage.get(k, 0)) - 1
            self.storage[k] = str(max(0, val))
            return val
        def keys(self, pattern="*"):
            return [k.encode("utf-8") for k in self.storage.keys()]
        def llen(self, key):
            return 0
            
    redis_client = InMemoryMockRedis()

@celery_app.task(bind=True, max_retries=3)
def task_scrape_url(self, url: str, **kwargs):
    """
    Distributed scraping task with locking, exception backoff, and Celery retries.
    """
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    
    # 1. Ensure task idempotency via distributed lock
    acquired = redis_client.set(url_hash, "locked", nx=True, ex=300)
    if not acquired:
        print(f"[*] Task for {url} is already processing in cluster. Skipping duplicate job.")
        return {"status": "skipped", "reason": "duplicate concurrent job"}
        
    try:
        # Increment active concurrency slots counter
        redis_client.incr("celery_active_slots")
        
        # Run the async orchestrator loop inside synchronous Celery worker
        from app.main import run_prototype
        
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
            
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = executor.submit(lambda: asyncio.run(run_prototype(url, **kwargs))).result()
        else:
            result = asyncio.run(run_prototype(url, **kwargs))
        
        # 2. Check result for transient failure categories to apply backoff retry
        status_val = result.status if hasattr(result, "status") else result.get("status")
        if status_val == "failed":
            category = result.failure_category if hasattr(result, "failure_category") else result.get("failure_category")
            if category in ("NETWORK", "HTTP_STATUS", "CONTENT"):
                countdown = 2 ** self.request.retries
                raise self.retry(countdown=countdown)
                
        # Increment processed tasks counter on success
        redis_client.incr("celery_processed_count")
        return result.model_dump() if hasattr(result, "model_dump") else result
    except Exception as exc:
        if "celery" in str(type(exc)).lower():
            raise exc
        countdown = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        # Decrement active concurrency slots counter
        redis_client.decr("celery_active_slots")
        # Release the lock
        redis_client.delete(url_hash)

class ScrapeQueueCoordinator:
    """
    Distributed task coordinator mapping enqueue requests to Celery and Redis.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ScrapeQueueCoordinator, cls).__new__(cls)
            cls._instance.max_concurrency = 3
        return cls._instance

    def reset(self, concurrency_limit: int = 3):
        """
        Resets stats counters stored in Redis.
        """
        self.max_concurrency = concurrency_limit
        redis_client.set("celery_active_slots", "0")
        redis_client.set("celery_processed_count", "0")

    def start_workers(self, num_workers: int = 3):
        """
        No-op in Celery mode since workers are managed externally.
        """
        pass

    @property
    def active_slots(self) -> int:
        try:
            return int(redis_client.get("celery_active_slots") or 0)
        except Exception:
            return 0

    @property
    def processed_count(self) -> int:
        try:
            return int(redis_client.get("celery_processed_count") or 0)
        except Exception:
            return 0

    @property
    def queue(self):
        class MockQueueSize:
            def qsize(self):
                try:
                    return redis_client.llen("celery")
                except Exception:
                    return 0
        return MockQueueSize()

    async def add_task(self, url: str, kwargs: dict) -> Any:
        """
        Enqueues scraping task to Celery distributed queue and returns an awaitable Future.
        """
        result = task_scrape_url.delay(url, **kwargs)
        
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        if hasattr(result, "get"):
            try:
                val = result.get(timeout=5)
                future.set_result(val)
            except Exception as e:
                future.set_exception(e)
        else:
            future.set_result(result)
        return future

    def get_diagnostics(self) -> dict:
        """
        Reads queue telemetry diagnostics from Redis.
        """
        try:
            active_slots = int(redis_client.get("celery_active_slots") or 0)
        except Exception:
            active_slots = 0
            
        try:
            processed_count = int(redis_client.get("celery_processed_count") or 0)
        except Exception:
            processed_count = 0
            
        active_locks = []
        try:
            all_keys = redis_client.keys("*")
            for k in all_keys:
                k_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                try:
                    val = redis_client.get(k_str)
                    val_str = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    if val_str == "locked":
                        active_locks.append(k_str)
                except Exception:
                    pass
        except Exception:
            pass
            
        try:
            task_backlog = redis_client.llen("celery")
        except Exception:
            task_backlog = 0
            
        return {
            "active_concurrency_slots": active_slots,
            "task_backlog": task_backlog,
            "total_processed_tasks": processed_count,
            "active_locks": active_locks
        }
