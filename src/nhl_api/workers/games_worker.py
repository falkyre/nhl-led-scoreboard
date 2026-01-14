"""
Games Worker - Background data fetching and caching for NHL games.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from nhl_api.data import get_games, get_score_details
from nhl_api.models import Game, GameState
from utils import sb_cache

debug = logging.getLogger("scoreboard")


class GamesWorker:
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

    def __init__(self, data, scheduler, refresh_seconds: int = 60):
        """
        Initialize the games worker with adaptive refresh intervals.

        Args:
            data: Application data object
            scheduler: APScheduler instance
            refresh_seconds: Base refresh interval for ticker display (default: 60 seconds)
        """
        self.data = data
        self.scheduler = scheduler
        self.base_refresh_seconds = refresh_seconds
        self.current_refresh_seconds = refresh_seconds

        # Register with scheduler - will be rescheduled dynamically
        scheduler.add_job(
            self.fetch_and_cache,
            'interval',
            seconds=self.current_refresh_seconds,
            jitter=3,  # Add small jitter to avoid exact timing collisions
            id=self.JOB_ID
        )

        debug.info(f"GamesWorker: Initialized with adaptive refresh (base: {self.base_refresh_seconds}s)")

        # Fetch immediately on startup
        self.fetch_and_cache()

    def fetch_and_cache(self):
        """
        Fetch today's games from API and cache in both raw and structured formats.

        Caches both formats for backward compatibility and future migration:
        - raw: Original dict format for GameSummaryBoard
        - structured: Game dataclass objects for new code

        After caching, adjusts refresh interval based on game states.
        """
        try:
            # Get today's date
            date_obj = date.today()

            # Fetch raw data for backward compatibility with GameSummaryBoard
            raw_data = get_score_details(date_obj)

            # Fetch structured Game objects for new code
            games = get_games(date_obj)

            if raw_data:
                # Cache both formats
                cache_data = {
                    'raw': raw_data.get('games', []),
                    'structured': games,
                    'fetched_at': datetime.now(),
                    'date': date_obj
                }

                # Cache with TTL slightly longer than refresh interval
                expire_seconds = self.current_refresh_seconds + 10
                sb_cache.set(self.CACHE_KEY, cache_data, expire=expire_seconds)

                debug.info(f"GamesWorker: Successfully cached {len(games)} games for {date_obj}")

                # Adjust refresh interval based on game states
                self._adjust_refresh_interval(games)
            else:
                debug.warning("GamesWorker: No games data received from API")
                # No games - use long refresh interval
                self._update_refresh_interval(1800)  # 30 minutes

        except Exception as e:
            debug.error(f"GamesWorker: Failed to fetch games: {e}")

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
            # Game times are timezone-aware, use UTC for comparison
            from datetime import timezone
            now = datetime.now(timezone.utc)
            debug.debug(f"GamesWorker: Using UTC time. Now: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}, First game: {games[0].game_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            # Game times are naive, use local time
            now = datetime.now()
            debug.debug(f"GamesWorker: Using local time. Now: {now.strftime('%Y-%m-%d %H:%M:%S')}, First game: {games[0].game_date.strftime('%Y-%m-%d %H:%M:%S')}")

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

    def _update_refresh_interval(self, new_interval: int):
        """
        Update the refresh interval if it has changed.

        Args:
            new_interval: New interval in seconds
        """
        if new_interval != self.current_refresh_seconds:
            self.current_refresh_seconds = new_interval

            try:
                # Reschedule the job with new interval
                self.scheduler.reschedule_job(
                    self.JOB_ID,
                    trigger='interval',
                    seconds=new_interval,
                    jitter=3
                )
                debug.info(f"GamesWorker: Adjusted refresh interval to {new_interval}s")
            except Exception as e:
                debug.error(f"GamesWorker: Failed to reschedule job: {e}")

    @staticmethod
    def get_cached_data() -> Optional[Dict]:
        """
        Retrieve cached games data.

        Returns:
            Dict containing raw and structured game data, or None if not cached
        """
        return sb_cache.get(GamesWorker.CACHE_KEY)

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
        return data['raw'] if data else []

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
        return data['structured'] if data else []

    @staticmethod
    def is_cached() -> bool:
        """
        Check if games data is currently cached.

        Returns:
            True if cached data exists, False otherwise
        """
        return GamesWorker.get_cached_data() is not None
