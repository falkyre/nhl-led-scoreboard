"""
Games Worker - Background data fetching and caching for NHL games.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from nhl_api.data import get_games, get_score_details
from nhl_api.models import Game
from nhl_api.workers.base_worker import BaseWorker

debug = logging.getLogger("scoreboard")


@dataclass
class GamesData:
    """Wrapper for games data supporting both raw and structured formats."""
    raw: List[Dict]
    structured: List[Game]
    date: date


class GamesWorker(BaseWorker[GamesData]):
    """
    Background worker that fetches and caches daily NHL games data.

    This worker provides game summary data for the scoreticker board and other
    non-live displays. For live game details, use LiveGameWorker instead.

    Refresh intervals optimized for ticker display (not real-time):
    - Any live games: 1 minute (ticker doesn't need real-time)
    - Scheduled <1hr: 5 minutes
    - Scheduled >1hr: 15 minutes
    - All games final: 5 minutes
    - No games: 30 minutes
    """

    JOB_ID = "gamesWorker"
    CACHE_KEY = "nhl_games_today"
    DEFAULT_TTL_BUFFER = 10

    def __init__(self, data, scheduler, refresh_seconds: int = 60):
        """
        Initialize the games worker with adaptive refresh intervals.

        Args:
            data: Application data object
            scheduler: APScheduler instance
            refresh_seconds: Base refresh interval for ticker display (default: 60 seconds)
        """
        self.base_refresh_seconds = refresh_seconds
        super().__init__(
            data=data,
            scheduler=scheduler,
            refresh_seconds=refresh_seconds,
            jitter=3,
            ttl_buffer=10
        )

    def fetch_data(self) -> Optional[GamesData]:
        """Fetch today's games in both raw and structured formats."""
        date_obj = self.data.date()

        # Fetch raw data for backward compatibility with GameSummaryBoard
        raw_data = get_score_details(date_obj)

        # Fetch structured Game objects for new code
        games = get_games(date_obj)

        if raw_data:
            return GamesData(
                raw=raw_data.get('games', []),
                structured=games,
                date=date_obj
            )
        return None

    def _on_fetch_success(self, data: GamesData):
        """Adjust refresh interval based on game states."""
        self._adjust_refresh_interval(data.structured)

    def _on_fetch_empty(self):
        """No games - use long refresh."""
        self._update_refresh_interval(1800)  # 30 minutes

    def _adjust_refresh_interval(self, games: List[Game]):
        """
        Dynamically adjust refresh interval based on game states and timing.

        Optimized for ticker display - slower intervals since real-time updates
        are handled by LiveGameWorker for the main display.

        Args:
            games: List of Game objects to analyze
        """
        if not games:
            # No games scheduled - check infrequently
            new_interval = 1800  # 30 minutes
            debug.debug("GamesWorker: No games today, using 30-minute refresh")
            self._update_refresh_interval(new_interval)
            return

        # Get current time - use UTC if game times are timezone-aware, otherwise local time
        first_game_tz = games[0].game_date.tzinfo
        if first_game_tz is not None:
            now = datetime.now(timezone.utc)
            debug.debug(f"GamesWorker: Using UTC time. Now: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            now = datetime.now()
            debug.debug(f"GamesWorker: Using local time. Now: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # Check if any games are live or final
        has_live = any(g.is_live for g in games)
        has_scheduled = any(g.is_scheduled for g in games)
        all_games_final = all(g.is_final for g in games)

        # Priority 1: Any live games - moderate refresh for ticker
        if has_live:
            new_interval = 60  # 1 minute (sufficient for ticker)
            debug.debug("GamesWorker: Live games detected, using 1-minute refresh")
            self._update_refresh_interval(new_interval)
            return

        # Priority 2: All games finished - slow refresh for final stats
        if all_games_final:
            new_interval = 300  # 5 minutes
            debug.debug("GamesWorker: All games final, using 5-minute refresh")
            self._update_refresh_interval(new_interval)
            return

        # Priority 3: Check scheduled games timing
        if has_scheduled:
            scheduled_games = [g for g in games if g.is_scheduled]
            if scheduled_games:
                earliest_game = min(scheduled_games, key=lambda g: g.game_date)
                time_until_game = (earliest_game.game_date - now).total_seconds()

                if time_until_game < 3600:  # Less than 1 hour
                    # Game starting soon - moderate refresh
                    new_interval = 300  # 5 minutes
                    debug.debug(f"GamesWorker: Game in {int(time_until_game/60)}min, using 5-minute refresh")
                else:
                    # Game more than 1 hour away - slow refresh
                    new_interval = 900  # 15 minutes
                    debug.debug(f"GamesWorker: Game in {int(time_until_game/60)}min, using 15-minute refresh")

                self._update_refresh_interval(new_interval)
                return

        # Default fallback - slow refresh
        new_interval = 900  # 15 minutes
        debug.debug("GamesWorker: Using default 15-minute refresh")
        self._update_refresh_interval(new_interval)

    # Backward-compatible static methods

    @staticmethod
    def get_games_raw() -> List[Dict]:
        """
        Get games in raw dictionary format for backward compatibility.

        This format is compatible with GameSummaryBoard and existing code
        that expects the old API response format.

        Returns:
            List of game dictionaries, or empty list if not cached
        """
        data = GamesWorker.get_cached_data()
        return data.raw if data else []

    @staticmethod
    def get_games_structured() -> List[Game]:
        """
        Get games as structured Game dataclass objects.

        This is the preferred method for new code as it provides type safety
        and better IDE support.

        Returns:
            List of Game objects, or empty list if not cached
        """
        data = GamesWorker.get_cached_data()
        return data.structured if data else []
