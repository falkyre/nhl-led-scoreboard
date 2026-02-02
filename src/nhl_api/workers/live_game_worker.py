"""
Live Game Worker - Background data fetching for the currently displayed live game.
"""

import logging
from typing import Any, Dict, Optional

from nhl_api.data import get_game_overview
from nhl_api.workers.base_worker import LifecycleWorker

debug = logging.getLogger("scoreboard")


class LiveGameWorker(LifecycleWorker[Dict]):
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
    DEFAULT_TTL_BUFFER = 5

    def fetch_data(self, game_id: int) -> Optional[Dict]:
        """
        Fetch game overview from NHL API.

        Args:
            game_id: NHL game ID to fetch

        Returns:
            Game overview dict, or None if fetch failed
        """
        return get_game_overview(game_id)

    def _on_fetch_success(self, overview: Dict):
        """Adjust refresh based on game state."""
        self._adjust_refresh_interval(overview)

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
                debug.info(f"LiveGameWorker: Game {self.current_resource_id} is {game_state}, stopping")
                self.stop_monitoring()
                return
            elif is_intermission:
                # Intermission - slower refresh
                new_interval = 30
                debug.debug("LiveGameWorker: Intermission detected, using 30-second refresh")
            elif game_state in ['LIVE', 'CRIT']:
                # Active play - fast refresh (CRIT = critical period, close game near end)
                new_interval = 5
                debug.debug(f"LiveGameWorker: Live play detected ({game_state}), using 5-second refresh")
            elif game_state in ['PRE', 'FUT']:
                # Pre-game - moderate refresh
                new_interval = 30
                debug.debug(f"LiveGameWorker: Pre-game state ({game_state}), using 30-second refresh")
            else:
                # Unknown state - use default
                new_interval = 10
                debug.debug(f"LiveGameWorker: Unknown state ({game_state}), using 10-second refresh")

            # Update interval if changed
            if new_interval != self.current_refresh_seconds:
                self._update_refresh_interval(new_interval)
                # Show intermission status in log for clarity
                state_display = f"{game_state} (Intermission)" if is_intermission else game_state
                debug.info(f"LiveGameWorker: Adjusted refresh to {new_interval}s (state: {state_display})")

        except Exception as e:
            debug.error(f"LiveGameWorker: Error adjusting interval: {e}")

    # Convenience method for backward compatibility

    @classmethod
    def get_cached_overview(cls, game_id: int) -> Optional[Dict]:
        """
        Retrieve cached game overview for a specific game.

        This is an alias for get_cached_data for backward compatibility.

        Args:
            game_id: NHL game ID

        Returns:
            Game overview dict, or None if not cached
        """
        return cls.get_cached_data(game_id)
