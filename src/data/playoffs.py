import logging
from datetime import datetime, timedelta, timezone

from data.team import SeriesTeam
from nhl_api.data import get_game
from nhl_api.nhl_client import client
from utils import convert_time

debug = logging.getLogger("scoreboard")

def get_team_position(teams_info):
    """
        Lookup for both team's position in the seed data of team's info and return
        their data in respective position (top_team, bottom_team)
    """
    for team in teams_info:
        bottom_team = team
        if bottom_team.seed.isTop:
            top_team = bottom_team

    return top_team, bottom_team

class Playoff:
    def __init__(self, playoff, data):
        pass

class Rounds(Playoff):
    def __init__(self, round, data):
        pass

class Series:
    def __init__(self, series, data):

        """
            Get all games of a series through this.
            https://records.nhl.com/site/api/playoff-series?cayenneExp=playoffSeriesLetter="A" and seasonId=20182019

            This is off from the nhl record api. Not sure if it will update as soon as the day is over.
        """
        try:
            series_info = client.get_series_record(series["seriesLetter"], data.status.season_id)
        except Exception:
            debug.error(f"Failed to get series info for {series['seriesLetter']}")
            return

        top = series_info["topSeedTeam"]
        bottom = series_info["bottomSeedTeam"]
        top_team_abbrev = top["abbrev"]
        bottom_team_abbrev = bottom["abbrev"]
        to_win = series_info["neededToWin"]
        try:
            self.conference = top["conference"]["name"]
        except Exception:
            self.conference = ""
        self.series_letter = series["seriesLetter"]
        self.round_number = series["roundNumber"]
        self.round_name = series["seriesLabel"]
        self.top_team = SeriesTeam(top, top_team_abbrev)
        self.bottom_team = SeriesTeam(bottom, bottom_team_abbrev)
        self.games = series_info["games"]
        self.game_overviews = {}
        self.show = True
        self.data = data
        self.current_game_id = None
        self.live_game_id = None

        if int(top["seriesWins"]) == to_win or int(bottom["seriesWins"]) == to_win:
            self.final=True
            debug.info("Series is Finished")
        else:
            try:
                self.current_game = series_info["games"][int(top["seriesWins"]) + int(bottom["seriesWins"])]
                self.current_game_id = self.current_game["id"]
                start_time_utc = self.current_game["startTimeUTC"]
                self.current_game_date = datetime.strptime(
                    start_time_utc.split("T")[0], "%Y-%m-%d"
                ).strftime("%b %d")
                self.current_game_start_time = convert_time(
                    datetime.strptime(start_time_utc, "%Y-%m-%dT%H:%M:%SZ")
                ).strftime(data.config.time_format)
            except Exception as e:
                debug.info("Unknown error:")
                print(e)



    def get_game_overview(self, gameid):
        overview = ""
        # Check if the game data is already stored in the game overviews from the series
        if gameid in self.game_overviews:
            # Fetch the game overview from the cache
            debug.debug(f"Cache hit for game overview {gameid}")
            overview = self.game_overviews[gameid]

        else:
            # Not cached, request the overview from the NHL API
            try:
                debug.debug(f"Cache miss, requesting overview for game {gameid}")
                overview = client.get_game_overview(gameid)
            except Exception:
                debug.error("failed overview refresh for series game id {}".format(gameid))

            if overview == "":
                debug.error(f"Failed to get overview for game {gameid}")
                return None

            # Get game object for state checking
            game_obj = get_game(gameid)

            # if a game is scheduled, cache it if it is more than 24 hours away
            if game_obj.is_scheduled:
                if game_obj.game_date > datetime.now(timezone.utc) + timedelta(days=1):
                    debug.debug(f"Game {gameid} is scheduled more than 24 hours away, caching")
                    self.game_overviews[gameid] = overview

            # cache completed games
            elif game_obj.is_final:
                debug.debug(f"Caching overview for game {gameid}")
                self.game_overviews[gameid] = overview

                # if the game that was live is now over, lets refresh the playoff data
                if gameid == self.live_game_id:
                    debug.debug(f"Game {gameid} is over, refreshing playoff data")
                    self.data.refresh_playoff() #ideally we'd just refresh the series data but this is easier for now
                    self.live_game_id = None

            # if a game in the series is live, track it.  We will want to refresh the playoff data when it concludes
            if game_obj.is_live:
                debug.debug(f"Game {gameid} is live, tracking")
                self.live_game_id = gameid

        return overview
