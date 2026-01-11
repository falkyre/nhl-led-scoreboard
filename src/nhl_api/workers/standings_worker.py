"""
Standings Worker - Background data fetching and caching for NHL standings.
"""
import logging
from typing import Optional

from nhl_api.data import get_standings_structured
from nhl_api.models import Standings
from utils import sb_cache

debug = logging.getLogger("scoreboard")


class StandingsWorker:
    """Background worker that fetches and caches NHL standings data."""

    JOB_ID = "standingsWorker"
    CACHE_KEY = "nhl_standings"

    def __init__(self, data, scheduler, refresh_minutes: int = 60):
        """
        Initialize the standings worker.

        Args:
            data: Application data object
            scheduler: APScheduler instance
            refresh_minutes: How often to refresh standings (default: 60 minutes)
        """
        self.data = data
        self.refresh_minutes = refresh_minutes

        # Register with scheduler
        scheduler.add_job(
            self.fetch_and_cache,
            'interval',
            minutes=self.refresh_minutes,
            jitter=120,  # Add jitter to avoid hitting API at exact same time
            id=self.JOB_ID
        )

        debug.info(f"StandingsWorker: Scheduled to refresh every {self.refresh_minutes} minutes")

        # Fetch immediately on startup
        self.fetch_and_cache()

    def fetch_and_cache(self):
        """Fetch standings from API and cache the results."""
        try:
            # Fetch standings using the new structured dataclass method
            # This returns a Standings dataclass with by_conference, by_division, and by_wildcard properties
            standings_data = get_standings_structured()

            if standings_data:
                # Cache with TTL slightly longer than refresh interval
                expire_seconds = (self.refresh_minutes * 60) + 300  # +5 minutes buffer
                sb_cache.set(self.CACHE_KEY, standings_data, expire=expire_seconds)
                debug.info("StandingsWorker: Successfully cached standings data")
            else:
                debug.warning("StandingsWorker: No standings data received from API")

        except Exception as e:
            debug.error(f"StandingsWorker: Failed to fetch standings: {e}")

    @staticmethod
    def get_cached_data() -> Optional[Standings]:
        """
        Retrieve cached standings data.

        Returns:
            Standings dataclass object or None if not cached or expired
        """
        return sb_cache.get(StandingsWorker.CACHE_KEY)

    @staticmethod
    def is_cached() -> bool:
        """
        Check if standings data is currently cached.

        Returns:
            True if cached data exists, False otherwise
        """
        return sb_cache.get(StandingsWorker.CACHE_KEY) is not None
