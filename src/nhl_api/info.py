import nhl_api.data
from nhl_api.object import Object, MultiLevelObject
from nameparser import HumanName
import debug
import datetime
import json

from nhlpy import NHLClient


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


    client = NHLClient(verbose=False)
    teams_data = {}
    teams_response = {}
    #with client as client:
    #teams_responses = client.standings.get_standings(str(datetime.date.today()))
    teams_responses = client.standings.get_standings()

    for team in teams_responses["standings"]:
        raw_team_id = team_dict[team["teamAbbrev"]["default"]]
        team_details = TeamDetails(raw_team_id, team["teamName"]["default"], team["teamAbbrev"]["default"])
        team_info = TeamInfo(team, team_details)
        teams_data[raw_team_id] = team_info
    if "59" in teams_data:
        return teams_data
    else:
        team_details=TeamDetails("59", "Utah Hockey Club", "UTA")
        team_info = TeamInfo(team, team_details)
        teams_data[59] = team_info
        return teams_data

    # TODO: I think most of this is now held in the TeamStandings object, but leaving here for reference
    # for team in teams_data:
    #     try:
    #         team_id = team['id']
    #         name = team['fullName']
    #         # abbreviation = team['abbreviation']
    #         # team_name = team['teamName']
    #         # location_name = team['locationName']
    #         short_name = team['triCode']
    #         # division_id = team['division']['id']
    #         # division_name = team['division']['name']
    #         # division_abbrev = team['division']['abbreviation']
    #         # conference_id = team['conference']['id']
    #         # conference_name = team['conference']['name']
    #         # official_site_url = team['officialSiteUrl']
    #         # franchise_id = team['franchiseId']
            
    #         pg, ng = team_previous_game(short_name, 20232024)
    #         # print(pg, ng)
    #         try:
    #             previous_game = pg
    #         except:
    #             debug.log("No next game detected for {}".format(name))
    #             previous_game = False

    #         try:
    #             next_game = ng
    #         except:
    #             debug.log("No next game detected for {}".format(team_name))
    #             next_game = False

    #         # try:
    #         #     stats = team['teamStats'][0]['splits'][0]['stat']
    #         # except:
    #         #     debug.log("No Stats detected for {}".format(team_name))
    #         #     stats = False

    #         # roster = {}
    #         # for p in team['roster']['roster']:
    #         #     person = p['person']
    #         #     person_id = person['id']
    #         #     name = HumanName(person['fullName'])
    #         #     first_name = name.first
    #         #     last_name = name.last

    #         #     position_name = p['position']['name']
    #         #     position_type = p['position']['abbreviation']
    #         #     position_abbrev = p['position']['abbreviation']

    #         #     try:
    #         #         jerseyNumber = p['jerseyNumber']
    #         #     except KeyError:
    #         #         jerseyNumber = ""
                
    #         #     roster[person_id]= {
    #         #         'firstName': first_name,
    #         #         'lastName': last_name,
    #         #         'jerseyNumber': jerseyNumber,
    #         #         'positionName': position_name,
    #         #         'positionType': position_type,
    #         #         'positionAbbrev': position_abbrev
    #         #         }
                
            
    #         output = {
    #             'team_id': team_id,
    #             'name': name,
    #             # 'abbreviation': abbreviation,
    #             'team_name': name,
    #             # 'location_name': location_name,
    #             'short_name': short_name,
    #             # 'division_id': division_id,
    #             # 'division_name': division_name,
    #             # 'division_abbrev': division_abbrev,
    #             # 'conference_id': conference_id,
    #             # 'conference_name': conference_name,
    #             # 'official_site_url': official_site_url,
    #             # 'franchise_id': franchise_id,
    #             # 'roster': roster,
    #             'previous_game': previous_game,
    #             'next_game': next_game,
    #             # 'stats': stats
    #         }

    #         # put this dictionary into the larger dictionary
    #         teams.append(output)
    #     except:
    #         print(team)
    #         debug.error("Missing data in current team info")


# This one is a little funky for the time. I'll loop through the what and why
def team_previous_game(team_code, date, pg = None, ng = None):
    # This response returns the next three games, starting from the date given
    client = NHLClient(verbose=False)
    teams_response = {}
    #with client as client:
    teams_response = client.schedule.get_schedule_by_team_by_week(team_code, date)
    
    if teams_response:
        pg = teams_response[0]
    else:
        if ng is None or pg is None:
            pg, ng = team_previous_game(team_code, teams_response[0]["gametDate"], None, None) 
    # If the first game in the list is a future game, the that's the next game. I think this will always be the case...
    # TODO: Get a better situation for a LIVE game when showing a team summary during intermission

    if pg["gameState"] == "FUT" or pg["gameState"] == "PRE" or pg["gameState"] == "LIVE":
        ng = pg
        # Then we take the previous_start_date given from the response and run through it again
        previousStartDate = datetime.date.today() - datetime.timedelta(days=7)
        pg, ng = team_previous_game(team_code, previousStartDate, None, ng)
    else:
        # I _think_ that realistically the previous_game will always be the last game in this list, but
        # I'm going to simply loop through for now.
        for game in teams_response[1:]:
            if (game["gameState"] == "FINAL" or game["gameState"] == "OFF") and game["gameDate"] > pg["gameDate"]:
                pg = game
            else:
                if ng is None or ng["gameDate"] < game["gameDate"]:
                    ng = game

    # Then return. I'd like to say we could be smart and take a few days off from the initial request,
    # but I'm already questioning how that'd act with the likes of the all-star break.
    # I think two requests is fine for now
    return pg, ng

def player_info(playerId):
    data = nhl_api.data.get_player(playerId)
    parsed = data.json()
    player = parsed["people"][0]

    return MultiLevelObject(player)

def status():
    data = nhl_api.data.get_game_status().json()
    return data


def current_season():
    data = nhl_api.data.get_current_season().json()
    return data

def next_season():
    data = nhl_api.data.get_next_season()
    return data


def playoff_info(season):
    data = nhl_api.data.get_playoff_data(season)
    parsed = data.json()
    season = parsed["season"]
    output = {'season': season}
    try:
        playoff_rounds = parsed["rounds"]
        rounds = {}
        for r in range(len(playoff_rounds)):
            rounds[str(playoff_rounds[r]["number"])] = MultiLevelObject(playoff_rounds[r])
        
        output['rounds'] = rounds
    except KeyError:
        debug.error("No data for {} Playoff".format(season))
        output['rounds'] = False

    try:
        default_round = parsed["defaultRound"]
        output['default_round'] = default_round
    except KeyError:
        debug.error("No default round for {} Playoff.".format(season))
        default_round = 1
        output['default_round'] = default_round

    return output

def series_record(seriesCode, season):
    data = data = nhl_api.data.get_series_record(seriesCode, season)
    parsed = data.json()
    return parsed["data"]



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
        self.default_round = data['default_round']
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

class Info(nhl_api.object.Object):
    pass