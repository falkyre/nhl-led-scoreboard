"""
Standings Worker - Background data fetching and caching for NHL standings.
"""

from typing import Optional

from nhl_api.data import get_standings_structured
from nhl_api.models import Standings
from nhl_api.workers.base_worker import BaseWorker


class StandingsWorker(BaseWorker[Standings]):
    """Background worker that fetches and caches NHL standings data."""

    JOB_ID = "standingsWorker"
    CACHE_KEY = "nhl_standings"
    DEFAULT_TTL_BUFFER = 300  # 5 minutes

    def __init__(self, data, scheduler, refresh_minutes: int = 60):
        """
        Initialize the standings worker.

        Args:
            data: Application data object
            scheduler: APScheduler instance
            refresh_minutes: How often to refresh standings (default: 60 minutes)
        """
        super().__init__(
            data=data,
            scheduler=scheduler,
            refresh_minutes=refresh_minutes,
            jitter=120,
            ttl_buffer=300
        )

    def fetch_data(self) -> Optional[Standings]:
        """Fetch standings from NHL API."""
        return get_standings_structured()
