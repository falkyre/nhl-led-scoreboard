"""
Team Schedule Worker - Background data fetching and caching for team schedule data.

Fetches and caches previous game and next game for preferred teams.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

from nhl_api import info as nhl_info
from nhl_api.workers.base_worker import BaseWorker

debug = logging.getLogger("scoreboard")


@dataclass
class TeamScheduleData:
    """Cached schedule data for a single team."""
    team_id: int
    team_abbrev: str
    team_name: str
    previous_game: Optional[dict]
    next_game: Optional[dict]


class TeamScheduleWorker(BaseWorker[Dict[int, TeamScheduleData]]):
    """Background worker that fetches and caches team schedule data (previous/next games)."""

    JOB_ID = "teamScheduleWorker"
    CACHE_KEY = "team_schedule_data"
    DEFAULT_TTL_BUFFER = 300  # 5 minutes

    def __init__(self, data, scheduler, refresh_minutes: int = 30):
        """
        Initialize the team schedule worker.

        Args:
            data: Application data object (contains pref_teams)
            scheduler: APScheduler instance
            refresh_minutes: How often to refresh data (default: 30 minutes)
        """
        super().__init__(
            data=data,
            scheduler=scheduler,
            refresh_minutes=refresh_minutes,
            jitter=120,
            ttl_buffer=300
        )

    def fetch_data(self) -> Optional[Dict[int, TeamScheduleData]]:
        """Fetch schedule data for all preferred teams."""
        pref_teams = getattr(self.data, 'pref_teams', [])

        if not pref_teams:
            debug.warning("TeamScheduleWorker: No preferred teams configured")
            return None

        schedules: Dict[int, TeamScheduleData] = {}
        today = str(self.data.date())

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

        return schedules if schedules else None

    @staticmethod
    def get_team_schedule(team_id: int) -> Optional[TeamScheduleData]:
        """
        Retrieve cached schedule data for a specific team.

        Args:
            team_id: The team ID to look up

        Returns:
            TeamScheduleData for the team, or None if not found
        """
        data = TeamScheduleWorker.get_cached_data()
        if data:
            return data.get(team_id)
        return None
