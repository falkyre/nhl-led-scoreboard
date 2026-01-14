"""
Live Game Worker - Background data fetching for the currently displayed live game.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from nhl_api.data import get_game_overview
from utils import sb_cache

debug = logging.getLogger("scoreboard")


class LiveGameWorker:
    """
    Background worker that fetches detailed game overview data for the live game
    currently being displayed on the main screen.

    This worker is dynamically started/stopped based on game state and only fetches
    data for one game at a time - the game being actively displayed.

    Refresh intervals based on game state:
    - Live play: 5 seconds (real-time updates for score/clock/penalties)
    - Intermission: 30 seconds (slower updates between periods)
    - Pre-game (<15min): 30 seconds (waiting for game to start)
    - Game over: Stops monitoring

    Usage:
        worker = LiveGameWorker(data, scheduler)
        worker.start_monitoring(game_id)  # When game goes live
        worker.stop_monitoring()           # When game ends or switching games
    """

    JOB_ID = "liveGameWorker"
    CACHE_KEY_PREFIX = "live_game_overview"

    def __init__(self, data, scheduler):
        """
        Initialize the live game worker (does not start fetching).

        Args:
            data: Application data object
            scheduler: APScheduler instance
        """
        self.data = data
        self.scheduler = scheduler
        self.current_game_id = None
        self.is_monitoring = False
        self.current_refresh_seconds = 5

        debug.info("LiveGameWorker: Initialized (not monitoring)")

    def start_monitoring(self, game_id: int, refresh_seconds: int = 5):
        """
        Start monitoring a specific game with real-time updates.

        If already monitoring a different game, stops that and starts the new one.

        Args:
            game_id: NHL game ID to monitor
            refresh_seconds: Base refresh interval (default: 5 seconds for live play)
        """
        # If already monitoring this game, don't restart
        if self.is_monitoring and self.current_game_id == game_id:
            debug.debug(f"LiveGameWorker: Already monitoring game {game_id}")
            return

        # If monitoring a different game, stop first
        if self.is_monitoring:
            debug.info(f"LiveGameWorker: Switching from game {self.current_game_id} to {game_id}")
            self.stop_monitoring()

        self.current_game_id = game_id
        self.current_refresh_seconds = refresh_seconds
        self.is_monitoring = True

        # Add job to scheduler
        try:
            self.scheduler.add_job(
                self.fetch_and_cache,
                'interval',
                seconds=self.current_refresh_seconds,
                jitter=1,  # Small jitter for live updates
                id=self.JOB_ID
            )
            debug.info(f"LiveGameWorker: Started monitoring game {game_id} ({refresh_seconds}s refresh)")

            # Fetch immediately
            self.fetch_and_cache()
        except Exception as e:
            debug.error(f"LiveGameWorker: Failed to start monitoring: {e}")
            self.is_monitoring = False

    def stop_monitoring(self):
        """
        Stop monitoring the current game and remove from scheduler.
        """
        if not self.is_monitoring:
            debug.debug("LiveGameWorker: Not monitoring, nothing to stop")
            return

        try:
            self.scheduler.remove_job(self.JOB_ID)
            debug.info(f"LiveGameWorker: Stopped monitoring game {self.current_game_id}")
        except Exception as e:
            debug.warning(f"LiveGameWorker: Error removing job (may not exist): {e}")

        self.is_monitoring = False
        self.current_game_id = None

    def fetch_and_cache(self):
        """
        Fetch game overview from API and cache it.

        Caches the overview data for the renderer to consume with a short TTL
        since we're fetching frequently.
        """
        if not self.is_monitoring or not self.current_game_id:
            debug.warning("LiveGameWorker: fetch_and_cache called but not monitoring")
            return

        try:
            # Fetch detailed game overview
            overview = get_game_overview(self.current_game_id)

            if overview:
                # Cache with short TTL (slightly longer than refresh interval)
                cache_data = {
                    'overview': overview,
                    'game_id': self.current_game_id,
                    'fetched_at': datetime.now()
                }

                cache_key = f"{self.CACHE_KEY_PREFIX}_{self.current_game_id}"
                expire_seconds = self.current_refresh_seconds + 5
                sb_cache.set(cache_key, cache_data, expire=expire_seconds)

                debug.debug(f"LiveGameWorker: Cached overview for game {self.current_game_id}")

                # Check if we should adjust refresh rate based on game state
                self._adjust_refresh_interval(overview)
            else:
                debug.warning(f"LiveGameWorker: No overview data for game {self.current_game_id}")

        except Exception as e:
            debug.error(f"LiveGameWorker: Failed to fetch game {self.current_game_id}: {e}")

    def _adjust_refresh_interval(self, overview: Dict):
        """
        Adjust refresh interval based on game state.

        Args:
            overview: Game overview data from API
        """
        try:
            game_state = overview.get('gameState', 'LIVE')
            clock_info = overview.get('clock', {})
            is_intermission = clock_info.get('inIntermission', False)

            # Determine appropriate refresh interval
            if game_state in ['FINAL', 'OFF']:
                # Game is over - stop monitoring
                debug.info(f"LiveGameWorker: Game {self.current_game_id} is {game_state}, stopping")
                self.stop_monitoring()
                return
            elif is_intermission:
                # Intermission - slower refresh
                new_interval = 30
            elif game_state == 'LIVE':
                # Active play - fast refresh
                new_interval = 5
            elif game_state in ['PRE', 'FUT']:
                # Pre-game - moderate refresh
                new_interval = 30
            else:
                # Unknown state - use default
                new_interval = 10

            # Update interval if changed
            if new_interval != self.current_refresh_seconds:
                self.current_refresh_seconds = new_interval

                try:
                    self.scheduler.reschedule_job(
                        self.JOB_ID,
                        trigger='interval',
                        seconds=new_interval,
                        jitter=1
                    )
                    debug.info(f"LiveGameWorker: Adjusted refresh to {new_interval}s (state: {game_state})")
                except Exception as e:
                    debug.error(f"LiveGameWorker: Failed to reschedule: {e}")

        except Exception as e:
            debug.error(f"LiveGameWorker: Error adjusting interval: {e}")

    @staticmethod
    def get_cached_overview(game_id: int) -> Optional[Dict]:
        """
        Retrieve cached game overview for a specific game.

        Args:
            game_id: NHL game ID

        Returns:
            Game overview dict, or None if not cached
        """
        cache_key = f"{LiveGameWorker.CACHE_KEY_PREFIX}_{game_id}"
        cached = sb_cache.get(cache_key)

        if cached:
            return cached.get('overview')
        return None

    @staticmethod
    def is_cached(game_id: int) -> bool:
        """
        Check if game overview is currently cached.

        Args:
            game_id: NHL game ID

        Returns:
            True if cached, False otherwise
        """
        return LiveGameWorker.get_cached_overview(game_id) is not None
