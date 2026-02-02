"""
Base Worker Classes - Common infrastructure for background data workers.

Provides standardized:
- Job registration with APScheduler
- Cache management with TTL and metadata
- Error handling
- Static retrieval methods
- Optional adaptive refresh support
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Generic, Optional, TypeVar

from utils import sb_cache

debug = logging.getLogger("scoreboard")

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """
    Standardized cache wrapper with metadata.

    All workers wrap their cached data in this structure
    to provide consistent access to fetch timestamps and metadata.
    """
    data: T
    fetched_at: datetime
    cache_key: str
    ttl_seconds: int

    @property
    def age_seconds(self) -> float:
        """Return seconds since data was fetched."""
        return (datetime.now() - self.fetched_at).total_seconds()

    @property
    def is_stale(self) -> bool:
        """Return True if data has exceeded its TTL."""
        return self.age_seconds > self.ttl_seconds


class BaseWorker(ABC, Generic[T]):
    """
    Abstract base class for background data workers.

    Provides standardized:
    - Job registration with APScheduler
    - Cache management with TTL
    - Error handling
    - Static retrieval methods
    - Optional adaptive refresh support

    Subclasses must implement:
    - fetch_data(): Fetch and return data from source
    - JOB_ID: Class variable for scheduler job identification
    - CACHE_KEY: Class variable for cache key
    """

    JOB_ID: ClassVar[str] = ""
    CACHE_KEY: ClassVar[str] = ""
    DEFAULT_TTL_BUFFER: ClassVar[int] = 10

    def __init__(
        self,
        data,
        scheduler,
        refresh_seconds: Optional[int] = None,
        refresh_minutes: Optional[int] = None,
        jitter: int = 60,
        ttl_buffer: Optional[int] = None,
        fetch_on_init: bool = True
    ):
        """
        Initialize the worker and register with scheduler.

        Args:
            data: Application data object
            scheduler: APScheduler instance
            refresh_seconds: Refresh interval in seconds (mutually exclusive with refresh_minutes)
            refresh_minutes: Refresh interval in minutes (mutually exclusive with refresh_seconds)
            jitter: Jitter in seconds for scheduler (default: 60)
            ttl_buffer: Extra seconds to add to refresh interval for cache TTL
            fetch_on_init: Whether to fetch data immediately on initialization
        """
        if not self.JOB_ID:
            raise ValueError(f"{self.__class__.__name__} must define JOB_ID")

        self.data = data
        self.scheduler = scheduler
        self.jitter = jitter
        self.ttl_buffer = ttl_buffer if ttl_buffer is not None else self.DEFAULT_TTL_BUFFER

        # Normalize refresh interval to seconds
        if refresh_seconds is not None:
            self.refresh_seconds = refresh_seconds
        elif refresh_minutes is not None:
            self.refresh_seconds = refresh_minutes * 60
        else:
            self.refresh_seconds = 60  # Default: 1 minute

        self.current_refresh_seconds = self.refresh_seconds

        # Register with scheduler
        self._register_job()

        debug.info(f"{self.__class__.__name__}: Initialized with {self.refresh_seconds}s refresh")

        # Fetch immediately on startup (if enabled)
        if fetch_on_init:
            self.fetch_and_cache()

    def _register_job(self):
        """Register the worker job with the scheduler."""
        self.scheduler.add_job(
            self.fetch_and_cache,
            'interval',
            seconds=self.current_refresh_seconds,
            jitter=self.jitter,
            id=self.JOB_ID
        )

    @abstractmethod
    def fetch_data(self) -> Optional[T]:
        """
        Fetch data from the source (API, etc).

        Returns:
            The fetched data, or None if fetch failed

        Raises:
            Exception: If fetch fails (will be caught by fetch_and_cache)
        """
        pass

    def fetch_and_cache(self):
        """
        Fetch data and store in cache with metadata.

        This method handles error catching and cache management.
        Subclasses should override fetch_data() instead.
        """
        try:
            data = self.fetch_data()

            if data is not None:
                self._store_in_cache(data)
                debug.info(f"{self.__class__.__name__}: Successfully cached data")

                # Allow subclasses to adjust refresh interval based on data
                self._on_fetch_success(data)
            else:
                debug.warning(f"{self.__class__.__name__}: No data received")
                self._on_fetch_empty()

        except Exception as e:
            debug.error(f"{self.__class__.__name__}: Failed to fetch: {e}")
            self._on_fetch_error(e)

    def _store_in_cache(self, data: T, cache_key: Optional[str] = None):
        """
        Store data in cache with standardized wrapper.

        Args:
            data: The data to cache
            cache_key: Optional override for cache key (default: self.get_cache_key())
        """
        key = cache_key or self.get_cache_key()
        ttl = self.current_refresh_seconds + self.ttl_buffer

        cache_entry = CacheEntry(
            data=data,
            fetched_at=datetime.now(),
            cache_key=key,
            ttl_seconds=ttl
        )

        sb_cache.set(key, cache_entry, expire=ttl)

    def get_cache_key(self) -> str:
        """
        Get the cache key for this worker.

        Override this method for workers with dynamic cache keys.

        Returns:
            Cache key string
        """
        if not self.CACHE_KEY:
            raise ValueError(f"{self.__class__.__name__} must define CACHE_KEY or override get_cache_key()")
        return self.CACHE_KEY

    # Hooks for subclass customization

    def _on_fetch_success(self, data: T):
        """
        Called after successful fetch and cache.

        Override to implement adaptive refresh or other post-fetch logic.
        """
        pass

    def _on_fetch_empty(self):
        """Called when fetch returns None/empty."""
        pass

    def _on_fetch_error(self, error: Exception):
        """Called when fetch raises an exception."""
        pass

    # Adaptive refresh support

    def _update_refresh_interval(self, new_interval: int):
        """
        Update the refresh interval dynamically.

        Args:
            new_interval: New interval in seconds
        """
        if new_interval != self.current_refresh_seconds:
            self.current_refresh_seconds = new_interval

            try:
                self.scheduler.reschedule_job(
                    self.JOB_ID,
                    trigger='interval',
                    seconds=new_interval,
                    jitter=self.jitter
                )
                debug.info(f"{self.__class__.__name__}: Adjusted refresh to {new_interval}s")
            except Exception as e:
                debug.error(f"{self.__class__.__name__}: Failed to reschedule: {e}")

    # Static retrieval methods

    @classmethod
    def get_cached_entry(cls) -> Optional[CacheEntry[T]]:
        """
        Retrieve the full cache entry including metadata.

        Returns:
            CacheEntry object or None if not cached
        """
        return sb_cache.get(cls.CACHE_KEY)

    @classmethod
    def get_cached_data(cls) -> Optional[T]:
        """
        Retrieve just the cached data (unwrapped from CacheEntry).

        Returns:
            Cached data or None if not cached
        """
        entry = cls.get_cached_entry()
        if entry is None:
            return None
        if isinstance(entry, CacheEntry):
            return entry.data
        # Backward compatibility: if old format, return as-is
        return entry

    @classmethod
    def is_cached(cls) -> bool:
        """
        Check if data is currently cached.

        Returns:
            True if cached data exists
        """
        return cls.get_cached_entry() is not None

    @classmethod
    def get_fetched_at(cls) -> Optional[datetime]:
        """
        Get the timestamp when data was last fetched.

        Returns:
            datetime or None if not cached
        """
        entry = cls.get_cached_entry()
        if entry and isinstance(entry, CacheEntry):
            return entry.fetched_at
        return None


class LifecycleWorker(ABC, Generic[T]):
    """
    Abstract base class for workers with explicit start/stop lifecycle.

    Unlike BaseWorker which starts fetching on init, LifecycleWorker
    requires explicit start_monitoring()/stop_monitoring() calls.

    Use this for workers that:
    - Monitor specific resources (game IDs, etc.)
    - Need dynamic cache keys
    - Should only run during specific conditions
    """

    JOB_ID: ClassVar[str] = ""
    CACHE_KEY_PREFIX: ClassVar[str] = ""
    DEFAULT_TTL_BUFFER: ClassVar[int] = 5

    def __init__(self, data, scheduler):
        """
        Initialize the lifecycle worker (does not start monitoring).

        Args:
            data: Application data object
            scheduler: APScheduler instance
        """
        if not self.JOB_ID:
            raise ValueError(f"{self.__class__.__name__} must define JOB_ID")

        self.data = data
        self.scheduler = scheduler
        self.is_monitoring = False
        self.current_resource_id = None
        self.current_refresh_seconds = 5
        self.jitter = 1
        self.ttl_buffer = self.DEFAULT_TTL_BUFFER

        debug.info(f"{self.__class__.__name__}: Initialized (not monitoring)")

    @abstractmethod
    def fetch_data(self, resource_id: Any) -> Optional[T]:
        """
        Fetch data for the specified resource.

        Args:
            resource_id: Identifier for the resource to fetch

        Returns:
            Fetched data or None
        """
        pass

    def start_monitoring(self, resource_id: Any, refresh_seconds: int = 5):
        """
        Start monitoring a specific resource.

        Args:
            resource_id: Identifier for the resource to monitor
            refresh_seconds: Refresh interval in seconds
        """
        if self.is_monitoring and self.current_resource_id == resource_id:
            debug.debug(f"{self.__class__.__name__}: Already monitoring {resource_id}")
            return

        if self.is_monitoring:
            debug.info(f"{self.__class__.__name__}: Switching from {self.current_resource_id} to {resource_id}")
            self.stop_monitoring()

        self.current_resource_id = resource_id
        self.current_refresh_seconds = refresh_seconds
        self.is_monitoring = True

        try:
            self.scheduler.add_job(
                self.fetch_and_cache,
                'interval',
                seconds=self.current_refresh_seconds,
                jitter=self.jitter,
                id=self.JOB_ID
            )
            debug.info(f"{self.__class__.__name__}: Started monitoring {resource_id} ({refresh_seconds}s)")

            # Fetch immediately
            self.fetch_and_cache()
        except Exception as e:
            debug.error(f"{self.__class__.__name__}: Failed to start: {e}")
            self.is_monitoring = False

    def stop_monitoring(self):
        """Stop monitoring and remove from scheduler."""
        if not self.is_monitoring:
            debug.debug(f"{self.__class__.__name__}: Not monitoring, nothing to stop")
            return

        try:
            self.scheduler.remove_job(self.JOB_ID)
            debug.info(f"{self.__class__.__name__}: Stopped monitoring {self.current_resource_id}")
        except Exception as e:
            debug.warning(f"{self.__class__.__name__}: Error removing job: {e}")

        self.is_monitoring = False
        self.current_resource_id = None

    def fetch_and_cache(self):
        """Fetch data for current resource and cache it."""
        if not self.is_monitoring or self.current_resource_id is None:
            debug.warning(f"{self.__class__.__name__}: fetch_and_cache called but not monitoring")
            return

        try:
            data = self.fetch_data(self.current_resource_id)

            if data is not None:
                self._store_in_cache(data)
                debug.debug(f"{self.__class__.__name__}: Cached data for {self.current_resource_id}")
                self._on_fetch_success(data)
            else:
                debug.warning(f"{self.__class__.__name__}: No data for {self.current_resource_id}")

        except Exception as e:
            debug.error(f"{self.__class__.__name__}: Failed to fetch {self.current_resource_id}: {e}")

    def _store_in_cache(self, data: T):
        """Store data in cache with dynamic key."""
        cache_key = self.get_cache_key(self.current_resource_id)
        ttl = self.current_refresh_seconds + self.ttl_buffer

        cache_entry = CacheEntry(
            data=data,
            fetched_at=datetime.now(),
            cache_key=cache_key,
            ttl_seconds=ttl
        )

        sb_cache.set(cache_key, cache_entry, expire=ttl)

    def get_cache_key(self, resource_id: Any) -> str:
        """Get cache key for a resource."""
        if not self.CACHE_KEY_PREFIX:
            raise ValueError(f"{self.__class__.__name__} must define CACHE_KEY_PREFIX")
        return f"{self.CACHE_KEY_PREFIX}_{resource_id}"

    def _on_fetch_success(self, data: T):
        """Hook for post-fetch processing (e.g., adaptive refresh)."""
        pass

    def _update_refresh_interval(self, new_interval: int):
        """Update refresh interval dynamically."""
        if new_interval != self.current_refresh_seconds:
            self.current_refresh_seconds = new_interval
            try:
                self.scheduler.reschedule_job(
                    self.JOB_ID,
                    trigger='interval',
                    seconds=new_interval,
                    jitter=self.jitter
                )
                debug.info(f"{self.__class__.__name__}: Adjusted refresh to {new_interval}s")
            except Exception as e:
                debug.error(f"{self.__class__.__name__}: Failed to reschedule: {e}")

    # Static retrieval with resource_id

    @classmethod
    def get_cached_entry(cls, resource_id: Any) -> Optional[CacheEntry[T]]:
        """Get cache entry for a specific resource."""
        cache_key = f"{cls.CACHE_KEY_PREFIX}_{resource_id}"
        return sb_cache.get(cache_key)

    @classmethod
    def get_cached_data(cls, resource_id: Any) -> Optional[T]:
        """Get cached data for a specific resource."""
        entry = cls.get_cached_entry(resource_id)
        if entry is None:
            return None
        if isinstance(entry, CacheEntry):
            return entry.data
        # Backward compatibility
        return entry

    @classmethod
    def is_cached(cls, resource_id: Any) -> bool:
        """Check if data is cached for a resource."""
        return cls.get_cached_entry(resource_id) is not None

    @classmethod
    def get_fetched_at(cls, resource_id: Any) -> Optional[datetime]:
        """Get the timestamp when data was last fetched for a resource."""
        entry = cls.get_cached_entry(resource_id)
        if entry and isinstance(entry, CacheEntry):
            return entry.fetched_at
        return None
