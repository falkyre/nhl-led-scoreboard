"""
Team Summary Worker - Background data fetching and caching for team summary data.

Fetches and caches team record, previous game, and next game for preferred teams.
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

from nhl_api import data as nhl_data
from nhl_api import info as nhl_info
from utils import sb_cache

debug = logging.getLogger("scoreboard")


@dataclass
class TeamSummaryData:
    """Cached summary data for a single team."""
    team_id: int
    team_abbrev: str
    team_name: str
    record: Optional[dict]  # Contains gamesPlayed, points, wins, losses, otLosses
    previous_game: Optional[dict]
    next_game: Optional[dict]


class TeamSummaryWorker:
    """Background worker that fetches and caches team summary data (record, previous/next games)."""

    JOB_ID = "teamSummaryWorker"
    CACHE_KEY = "team_summary_data"

    def __init__(self, data, scheduler, refresh_minutes: int = 30):
        """
        Initialize the team summary worker.

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

        debug.info(f"TeamSummaryWorker: Scheduled to refresh every {self.refresh_minutes} minutes")

        # Fetch immediately on startup
        self.fetch_and_cache()

    def fetch_and_cache(self):
        """Fetch summary data for all preferred teams and cache the results."""
        try:
            pref_teams = getattr(self.data, 'pref_teams', [])

            if not pref_teams:
                debug.warning("TeamSummaryWorker: No preferred teams configured")
                return

            # Fetch standings to get team records
            standings_response = nhl_data.get_standings()
            standings_by_abbrev = {}
            if standings_response and "standings" in standings_response:
                for team_standing in standings_response["standings"]:
                    abbrev = team_standing["teamAbbrev"]["default"]
                    standings_by_abbrev[abbrev] = team_standing

            summaries: Dict[int, TeamSummaryData] = {}
            today = str(date.today())

            for team_id in pref_teams:
                try:
                    # Get team info from data.teams_info for abbrev lookup
                    teams_info = getattr(self.data, 'teams_info', {})
                    team_info = teams_info.get(team_id)
                    if not team_info:
                        debug.warning(f"TeamSummaryWorker: Team {team_id} not found in teams_info")
                        continue

                    team_abbrev = team_info.details.abbrev
                    team_name = team_info.details.name

                    # Get record from standings
                    record = standings_by_abbrev.get(team_abbrev)

                    # Fetch previous and next game
                    pg, ng = nhl_info.team_previous_game(team_abbrev, today)

                    summaries[team_id] = TeamSummaryData(
                        team_id=team_id,
                        team_abbrev=team_abbrev,
                        team_name=team_name,
                        record=record,
                        previous_game=pg,
                        next_game=ng
                    )

                    debug.debug(f"TeamSummaryWorker: Fetched summary for {team_abbrev}")

                except Exception as e:
                    debug.error(f"TeamSummaryWorker: Failed to fetch summary for team {team_id}: {e}")

            if summaries:
                # Cache with TTL slightly longer than refresh interval
                expire_seconds = (self.refresh_minutes * 60) + 300  # +5 minutes buffer
                sb_cache.set(self.CACHE_KEY, summaries, expire=expire_seconds)
                debug.info(f"TeamSummaryWorker: Successfully cached summary data for {len(summaries)} teams")
            else:
                debug.warning("TeamSummaryWorker: No summary data received")

        except Exception as e:
            debug.error(f"TeamSummaryWorker: Failed to fetch summaries: {e}")

    @staticmethod
    def get_cached_data() -> Optional[Dict[int, TeamSummaryData]]:
        """
        Retrieve all cached team summary data.

        Returns:
            Dict mapping team_id to TeamSummaryData, or None if not cached
        """
        return sb_cache.get(TeamSummaryWorker.CACHE_KEY)

    @staticmethod
    def get_team_summary(team_id: int) -> Optional[TeamSummaryData]:
        """
        Retrieve cached summary data for a specific team.

        Args:
            team_id: The team ID to look up

        Returns:
            TeamSummaryData for the team, or None if not found
        """
        data = sb_cache.get(TeamSummaryWorker.CACHE_KEY)
        if data:
            return data.get(team_id)
        return None

    @staticmethod
    def is_cached() -> bool:
        """
        Check if team summary data is currently cached.

        Returns:
            True if cached data exists, False otherwise
        """
        return sb_cache.get(TeamSummaryWorker.CACHE_KEY) is not None
