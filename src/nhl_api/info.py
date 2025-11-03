"""
DEPRECATION NOTICE:
    Many classes and functions in this module are candidates for deprecation
    in favor of the new structured dataclasses in src/nhl_api/models.py.

    Still actively used by core application:
    - team_info() - Used to get all team information
    - standings() - Wrapper that returns Standings object
    - playoff_info() - Returns playoff bracket structure

    Deprecation candidates (replace with models.py):
    - Standings class -> Use Standings dataclass from models.py
    - Conference class -> Use Conference dataclass from models.py
    - Division class -> Use Division dataclass from models.py
    - Playoff class -> Consider creating Playoff dataclass in models.py
    - player_info() using MultiLevelObject -> Use Player dataclass from models.py

    See TODO.md for migration strategy.
"""
import json
import logging

import nhl_api.data
from nhl_api.nhl_client import client

debug = logging.getLogger("scoreboard")


def team_info():
    """
        Returns a list of team information dictionaries
    """
    # data = nhl_api.data.get_teams()
    # parsed = data.json()
    # Falling back to this for now until NHL stops screwing up their own API
    f = open('src/data/backup_teams_data.json')
    parsed = json.load(f)
    teams = parsed["data"]
    team_dict = {}
    for team in teams:
        team_dict[team["triCode"]] = team["id"]


    teams_data = {}
    teams_responses = nhl_api.data.get_standings()

    for team in teams_responses["standings"]:
        raw_team_id = team_dict[team["teamAbbrev"]["default"]]
        team_details = TeamDetails(raw_team_id, team["teamName"]["default"], team["teamAbbrev"]["default"])
        team_info = TeamInfo(team, team_details)
        teams_data[raw_team_id] = team_info

    return teams_data

def team_next_game_by_code(team_code):
    # Returns the next game and previous game for a team
    parsed = nhl_api.data.get_team_schedule(team_code)
    pg = None
    ng = None

    for game in parsed["games"]:
        if game["gameState"] == "FUT" or game["gameState"] == "PRE" or game["gameState"] == "LIVE":
            ng = game
            return pg, ng
        else:
            pg = game

    return pg, ng

def team_previous_game(team_code, date, pg = None, ng = None):
    return team_next_game_by_code(team_code)


def player_info(playerId):
    """
    Get player information (legacy wrapper).

    Note: This function is kept for backward compatibility through __init__.py.
    Consider using nhl_api.client.get_player() with Player dataclass instead.
    """
    parsed = nhl_api.data.get_player(playerId)
    # Return raw dict instead of MultiLevelObject since that's deleted
    return parsed


def status():
    """
    Get game status information (legacy wrapper).

    Note: Used by __init__.py wrapper for game_status_info().
    """
    data = nhl_api.data.get_game_status()
    return data


def current_season():
    """
    Get current season information (legacy wrapper).

    Note: Used by Status class through __init__.py wrapper.
    """
    data = nhl_api.data.get_current_season()
    return data


def next_season():
    """
    Get next season schedule information (legacy wrapper).

    Note: Used by Status class through __init__.py wrapper.
    """
    data = nhl_api.data.get_next_season()
    return data


def playoff_info(season):
    try:
        output = {'season': season}
        parsed = client.get_playoff_carousel(season)
        season = parsed["seasonId"]

        playoff_rounds = parsed["rounds"]
        rounds = {}
        for r in range(len(playoff_rounds)):
            rounds[str(playoff_rounds[r]["roundNumber"])] = playoff_rounds[r]

        output['rounds'] = rounds
    except Exception:
        debug.warning("No data for {} Playoff".format(season))
        output['rounds'] = False
        return output

    try:
        currentRound = parsed["currentRound"]
        output['currentRound'] = currentRound
    except KeyError:
        debug.error("No default round for {} Playoff.".format(season))
        output['currentRound'] = currentRound

    return output

def series_record(seriesCode, season):
    data = nhl_api.data.get_series_record(seriesCode, season)
    return data["data"]


def standings():
    """Get current NHL standings as a Standings object."""
    season_standings = nhl_api.data.get_standings()
    return Standings(season_standings, {})



class Standings:
    """
        Object containing all the standings data per team.

        Contains functions to return a dictionary of the data reorganised to represent
        different type of Standings.

    """
    def __init__(self, records, wildcard):
        self.data = records
        self.data_wildcard = wildcard  # This can probably be removed since we're not using it anymore
        self.get_conference()
        self.get_division()
        self.get_wild_card()

    def get_conference(self):
        eastern, western = self.sort_conference(self.data)
        self.by_conference = nhl_api.info.Conference(eastern, western)

    def get_division(self):
        metropolitan, atlantic, central, pacific = self.sort_division(self.data)
        self.by_division = nhl_api.info.Division(metropolitan, atlantic, central, pacific)

    def get_wild_card(self):
        """
        Creates wildcard standings using conferenceSequence and wildcardSequence.
        Division leaders are teams with divisionSequence 1-3, wildcards are the rest.
        """
        eastern_all = []
        western_all = []

        # First separate into conferences
        for item in self.data["standings"]:
            if item["conferenceName"] == 'Eastern':
                eastern_all.append(item)
            elif item["conferenceName"] == 'Western':
                western_all.append(item)

        # Process each conference
        eastern_wc = self._process_conference_wildcard(eastern_all)
        western_wc = self._process_conference_wildcard(western_all)

        self.by_wildcard = nhl_api.info.Conference(eastern_wc, western_wc)

    def _process_conference_wildcard(self, conference_data):
        # Sort by division sequence to get division leaders
        division_leaders = []
        wild_card_teams = []

        for team in conference_data:
            if team["divisionSequence"] <= 3:
                division_leaders.append(team)
            else:
                wild_card_teams.append(team)

        # Sort division leaders by divisionSequence
        division_leaders.sort(key=lambda x: (x["divisionName"], x["divisionSequence"]))

        # Sort wildcard teams by wildcardSequence
        wild_card_teams.sort(key=lambda x: x["wildcardSequence"])

        # Create division structure
        metropolitan = []
        atlantic = []
        central = []
        pacific = []
        for team in division_leaders:
            if team["divisionName"] == "Metropolitan":
                metropolitan.append(team)
            elif team["divisionName"] == "Atlantic":
                atlantic.append(team)
            elif team["divisionName"] == "Central":
                central.append(team)
            elif team["divisionName"] == "Pacific":
                pacific.append(team)

        division = nhl_api.info.Division(metropolitan, atlantic, central, pacific)
        return nhl_api.info.Wildcard(wild_card_teams, division)

    @staticmethod
    def sort_conference(data):
        eastern = []
        western = []

        for item in data["standings"]:
            if item["conferenceName"] == 'Eastern':
                eastern.append(item)
            elif item["conferenceName"] == 'Western':
                western.append(item)

        # Sort by conferenceSequence instead of points
        eastern.sort(key=lambda x: x["conferenceSequence"])
        western.sort(key=lambda x: x["conferenceSequence"])
        return eastern, western

    @staticmethod
    def sort_division(data):
        metropolitan = []
        atlantic = []
        central = []
        pacific = []

        for item in data["standings"]:
            if item["divisionName"] == 'Metropolitan':
                metropolitan.append(item)
            elif item["divisionName"] == 'Atlantic':
                atlantic.append(item)
            elif item["divisionName"] == 'Central':
                central.append(item)
            elif item["divisionName"] == 'Pacific':
                pacific.append(item)

        # Sort by divisionSequence instead of points
        metropolitan.sort(key=lambda x: x["divisionSequence"])
        atlantic.sort(key=lambda x: x["divisionSequence"])
        central.sort(key=lambda x: x["divisionSequence"])
        pacific.sort(key=lambda x: x["divisionSequence"])

        return metropolitan, atlantic, central, pacific


class Conference:
    def __init__(self, east, west):
        if east:
            self.eastern = east
        if west:
            self.western = west


class Division:
    def __init__(self, met, atl, cen, pac):
        if met:
            self.metropolitan = met
        if atl:
            self.atlantic = atl
        if cen:
            self.central = cen
        if pac:
            self.pacific = pac


class Wildcard:
    def __init__(self, wild, div):
        self.wild_card = wild
        self.division_leaders = div


class Playoff():
    def __init__(self, data):
        self.season = data['season']
        self.default_round = data.get('currentRound', None)
        self.rounds = data['rounds']

    def __str__(self):
        return (f"Season: {self.season}, Current round: {self.default_round}")

    def __repr__(self):
        return self.__str__()

class TeamInfo:
    def __init__(self, standings, team_details):
        self.record = standings
        self.details = team_details

class TeamDetails:
    def __init__(self, id: int, name: str, abbrev: str, previous_game = None, next_game = None):
        self.id = id
        self.name = name
        self.abbrev = abbrev
        self.previous_game = previous_game
        self.next_game = next_game
