import nhl_api.game
import nhl_api.info
from nhl_api.nhl_client import client


def player(playerId):
    """Return an Info object of a player information"""
    return nhl_api.info.player_info(playerId)


def overview(game_id):
    """Return Overview object that contains game information."""
    return nhl_api.game.overview(game_id)


def play_by_play(game_id):
    """Get play-by-play data for a game."""
    return client.get_game_overview(game_id)


def game_status_info():
    return nhl_api.info.status()


def current_season_info():
    return nhl_api.info.current_season()


def next_season_info():
    return nhl_api.info.next_season()


def standings():
    """Get current NHL standings."""
    return nhl_api.info.standings()


def playoff(season=""):
    return nhl_api.info.Playoff(nhl_api.info.playoff_info(season))


def series_game_record(seriesCode, season):
    return nhl_api.info.series_record(seriesCode, season)
