from datetime import datetime, date
from nhl_api import current_season_info, next_season_info
import logging

debug = logging.getLogger("scoreboard")


class Status:
    """
    Season information manager for NHL seasons.

    Manages season metadata including start/end dates, season IDs,
    and provides season-related utility methods.

    Note: Game state checking methods have been migrated to the Game model.
    See nhl_api.models.Game for is_live, is_final, is_scheduled, is_irregular properties.
    """

    def __init__(self):
        self.season_id = 20252026
        self.refresh_next_season()

    def is_offseason(self, date):
        """Check if a given date is in the offseason"""
        try:
            regular_season_startdate = datetime.strptime(
                self.season_info['regularSeasonStartDate'], "%Y-%m-%d"
            ).date()
            end_of_season = datetime.strptime(
                self.season_info['seasonEndDate'], "%Y-%m-%d"
            ).date()
            return date < regular_season_startdate or date > end_of_season
        except Exception:
            debug.error('The argument provided for status.is_offseason is missing or not right.')
            return False

    def is_playoff(self, date, playoff_obj):
        """Check if a given date is in the playoff period"""
        try:
            # Get dates of the planned end of regular season and end of season
            regular_season_enddate = datetime.strptime(
                self.season_info['regularSeasonEndDate'], "%Y-%m-%d"
            ).date()
            end_of_season = datetime.strptime(
                self.season_info['seasonEndDate'], "%Y-%m-%d"
            ).date()

            return regular_season_enddate < date <= end_of_season and playoff_obj.rounds
        except TypeError:
            debug.error('The argument provided for status.is_playoff is missing or not right.')
            return False

    def refresh_next_season(self):
        """Fetch and update season information from NHL API"""
        debug.info("Updating next season info")
        self.season_info = current_season_info()[-1]
        self.next_season_info = next_season_info()

        # Make sure that the next_season_info is not an empty list
        # If it is, make next_season equal to current season
        if not self.next_season_info:
            debug.info("Next season info unavailable, defaulting to Oct 1 of current year as start of new season")
            self.next_season_info = self.season_info
            # Arbitrarily set the regularSeasonStartDate to Oct 1 of current year
            self.next_season_info['regularSeasonStartDate'] = f"{date.today().year}-10-01"

    def next_season_start(self):
        """Get the start date of the next season"""
        return self.next_season_info['regularSeasonStartDate']
