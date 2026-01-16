"""
Team Schedule Worker - Background data fetching and caching for team schedule data.

Fetches and caches previous game and next game for preferred teams.
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

from nhl_api import info as nhl_info
from utils import sb_cache

debug = logging.getLogger("scoreboard")


@dataclass
class TeamScheduleData:
    """Cached schedule data for a single team."""
    team_id: int
    team_abbrev: str
    team_name: str
    previous_game: Optional[dict]
    next_game: Optional[dict]


class TeamScheduleWorker:
    """Background worker that fetches and caches team schedule data (previous/next games)."""

    JOB_ID = "teamScheduleWorker"
    CACHE_KEY = "team_schedule_data"

    def __init__(self, data, scheduler, refresh_minutes: int = 30):
        """
        Initialize the team schedule worker.

        Args:
            data: Application data object (contains pref_teams)
            scheduler: APScheduler instance
            refresh_minutes: How often to refresh data (default: 30 minutes)
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

        debug.info(f"TeamScheduleWorker: Scheduled to refresh every {self.refresh_minutes} minutes")

        # Fetch immediately on startup
        self.fetch_and_cache()

    def fetch_and_cache(self):
        """Fetch schedule data for all preferred teams and cache the results."""
        try:
            pref_teams = getattr(self.data, 'pref_teams', [])

            if not pref_teams:
                debug.warning("TeamScheduleWorker: No preferred teams configured")
                return

            schedules: Dict[int, TeamScheduleData] = {}
            today = str(date.today())

            for team_id in pref_teams:
                try:
                    # Get team info from data.teams_info for abbrev lookup
                    teams_info = getattr(self.data, 'teams_info', {})
                    team_info = teams_info.get(team_id)
                    if not team_info:
                        debug.warning(f"TeamScheduleWorker: Team {team_id} not found in teams_info")
                        continue

                    team_abbrev = team_info.details.abbrev
                    team_name = team_info.details.name

                    # Fetch previous and next game
                    pg, ng = nhl_info.team_previous_game(team_abbrev, today)

                    schedules[team_id] = TeamScheduleData(
                        team_id=team_id,
                        team_abbrev=team_abbrev,
                        team_name=team_name,
                        previous_game=pg,
                        next_game=ng
                    )

                    debug.debug(f"TeamScheduleWorker: Fetched schedule for {team_abbrev}")

                except Exception as e:
                    debug.error(f"TeamScheduleWorker: Failed to fetch schedule for team {team_id}: {e}")

            if schedules:
                # Cache with TTL slightly longer than refresh interval
                expire_seconds = (self.refresh_minutes * 60) + 300  # +5 minutes buffer
                sb_cache.set(self.CACHE_KEY, schedules, expire=expire_seconds)
                debug.info(f"TeamScheduleWorker: Successfully cached schedule data for {len(schedules)} teams")
            else:
                debug.warning("TeamScheduleWorker: No schedule data received")

        except Exception as e:
            debug.error(f"TeamScheduleWorker: Failed to fetch schedules: {e}")

    @staticmethod
    def get_cached_data() -> Optional[Dict[int, TeamScheduleData]]:
        """
        Retrieve all cached team schedule data.

        Returns:
            Dict mapping team_id to TeamScheduleData, or None if not cached
        """
        return sb_cache.get(TeamScheduleWorker.CACHE_KEY)

    @staticmethod
    def get_team_schedule(team_id: int) -> Optional[TeamScheduleData]:
        """
        Retrieve cached schedule data for a specific team.

        Args:
            team_id: The team ID to look up

        Returns:
            TeamScheduleData for the team, or None if not found
        """
        data = sb_cache.get(TeamScheduleWorker.CACHE_KEY)
        if data:
            return data.get(team_id)
        return None

    @staticmethod
    def is_cached() -> bool:
        """
        Check if team schedule data is currently cached.

        Returns:
            True if cached data exists, False otherwise
        """
        return sb_cache.get(TeamScheduleWorker.CACHE_KEY) is not None
