"""
Stats Leaders Worker - Background data fetching and caching for stats leaders.
"""

import logging
from typing import Dict, List, Optional

from nhl_api.data import get_skater_stats_leaders
from nhl_api.models import StatsLeadersData
from nhl_api.workers.base_worker import BaseWorker

debug = logging.getLogger("scoreboard")


class StatsLeadersWorker(BaseWorker[Dict[str, StatsLeadersData]]):
    """Background worker that fetches and caches stats leaders data."""

    JOB_ID = "statsLeadersWorker"
    CACHE_KEY = "nhl_stats_leaders"
    DEFAULT_TTL_BUFFER = 120  # 2 minutes

    # Valid categories supported by the NHL API
    VALID_CATEGORIES = {
        'goals', 'points', 'assists', 'toi', 'plusMinus',
        'penaltyMins', 'faceoffLeaders', 'goalsPp', 'goalsSh'
    }

    def __init__(
        self,
        data,
        scheduler,
        categories: List[str] = None,
        limit: int = 15,
        refresh_minutes: int = 30
    ):
        """
        Initialize the stats leaders worker.

        Args:
            data: Application data object
            scheduler: APScheduler instance
            categories: List of stat categories to fetch (default: goals, assists, points)
            limit: Number of leaders to fetch per category (default: 15)
            refresh_minutes: How often to refresh data (default: 30 minutes)
        """
        # Validate categories before calling super().__init__
        requested = categories or ['goals', 'assists', 'points']
        valid = [c for c in requested if c in self.VALID_CATEGORIES]
        invalid = [c for c in requested if c not in self.VALID_CATEGORIES]

        if invalid:
            debug.warning(
                f"StatsLeadersWorker: Ignoring invalid categories: {invalid}. "
                f"Valid options: {sorted(self.VALID_CATEGORIES)}"
            )

        self.categories = valid if valid else ['goals', 'assists', 'points']
        self.limit = limit

        super().__init__(
            data=data,
            scheduler=scheduler,
            refresh_minutes=refresh_minutes,
            jitter=60,
            ttl_buffer=120
        )

    def fetch_data(self) -> Optional[Dict[str, StatsLeadersData]]:
        """Fetch stats leaders for configured categories."""
        all_leaders: Dict[str, StatsLeadersData] = {}

        for category in self.categories:
            raw_data = get_skater_stats_leaders(category=category, limit=self.limit)

            if raw_data and category in raw_data:
                # Convert to structured data
                leaders_data = StatsLeadersData.from_api_response(
                    category,
                    raw_data[category]
                )
                all_leaders[category] = leaders_data
                debug.debug(f"StatsLeadersWorker: Fetched {len(leaders_data.leaders)} {category} leaders")

        return all_leaders if all_leaders else None

    @staticmethod
    def get_category(category: str) -> Optional[StatsLeadersData]:
        """Get a specific category from cache."""
        data = StatsLeadersWorker.get_cached_data()
        if data:
            return data.get(category)
        return None
