"""
NHL API data access functions.

This module provides convenience functions for accessing NHL API data
using the centralized API client.
"""

from datetime import date

from nhl_api.nhl_client import client


def get_score_details(date_obj: date):
    """
    Get score details for a specific date.

    Args:
        date_obj: Date to get scores for

    Returns:
        Score details including all games for the date
    """
    return client.get_score_details(date_obj)


def get_game_overview(game_id: int):
    """
    Get detailed game overview including play-by-play.

    Args:
        game_id: NHL game ID

    Returns:
        Complete game details
    """
    return client.get_game_overview(game_id)


def get_overview(game_id: int):
    """
    Alias for get_game_overview for backward compatibility.

    Args:
        game_id: NHL game ID

    Returns:
        Complete game details
    """
    return client.get_game_overview(game_id)


def get_game_status():
    """
    Get current game status information.

    Returns:
        Game status data
    """
    return client.get_game_status()


def get_teams():
    """
    Get all NHL teams information.

    Returns:
        Dictionary of team data
    """
    return client.get_teams()


def get_team_schedule(team_code: str, season_code: str = None):
    """
    Get schedule for a specific team.

    Args:
        team_code: Three-letter team code (e.g., 'TOR', 'MTL')
        season_code: Optional season code (e.g., '20232024')

    Returns:
        Team schedule data
    """
    return client.get_team_schedule(team_code, season_code)


def get_player(player_id: int):
    """
    Get player information and statistics.

    Args:
        player_id: NHL player ID

    Returns:
        Player data including stats and biographical info
    """
    return client.get_player(player_id)


def fetch_player_data(player_id: int):
    """
    Alias for get_player for backward compatibility.

    Args:
        player_id: NHL player ID

    Returns:
        Player data
    """
    return client.get_player(player_id)


def get_player_stats(player_id: int):
    """
    Get player stats from the NHL API.

    Args:
        player_id: NHL player ID

    Returns:
        Dictionary containing player stats
    """
    from nhl_api.player import PlayerStats  # Import here to avoid circular imports
    player_stats = PlayerStats.from_api(player_id)

    # Convert relevant attributes to dictionary
    return {
        attr: getattr(player_stats, attr)
        for attr in player_stats.__dict__
        if not attr.startswith('_') and attr != 'player_data'
    }


def get_skater_stats_leaders(category: str = None, limit: int = None):
    """
    Get current NHL skater statistics leaders.

    Args:
        category: Specific stat category (goals, points, assists, etc.)
        limit: Number of results to return

    Returns:
        Leader statistics data
    """
    return client.get_skater_stats_leaders(category, limit)


def get_current_season():
    """
    Get current season information.

    Returns:
        Current season data
    """
    return client.get_current_season()


def get_next_season():
    """
    Get next season schedule information.

    Returns:
        Next season data
    """
    return client.get_next_season()


def get_standings():
    """
    Get current NHL standings.

    Returns:
        Standings data
    """
    return client.get_standings()


def get_standings_wildcard():
    """
    Get standings with wildcard leaders.

    Returns:
        Standings with wildcard information
    """
    return client.get_standings_wildcard()


def get_playoff_data(season: str):
    """
    Get playoff tournament data for a season.

    Args:
        season: Season code (e.g., '20232024')

    Returns:
        Playoff bracket and series data
    """
    return client.get_playoff_data(season)


def get_series_record(series_code: str, season: str):
    """
    Get playoff series record.

    Args:
        series_code: Series letter code (e.g., 'A', 'B', 'C')
        season: Season ID (e.g., '20232024')

    Returns:
        Series record data
    """
    return client.get_series_record(series_code, season)
