"""
NHL API data access functions.

This module provides convenience functions for accessing NHL API data
using the centralized API client.

ARCHITECTURE:
- Legacy functions (get_*): Return raw dictionaries for backward compatibility
- Normalized functions (get_*_structured): Return typed dataclasses from models.py
- All new code should use the structured functions for type safety
"""

import warnings
from datetime import date
from typing import List, Optional

from nhl_api.nhl_client import client
from nhl_api.models import Game, Player, Standings


def get_score_details(date_obj: date):
    """
    Get score details for a specific date.

    NOTE: Returns raw dictionary. Consider using get_games() for structured objects.

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


# ============================================================================
# NORMALIZED API - Structured Dataclass Returns
# ============================================================================
# These functions return typed dataclasses from models.py for type safety
# and better developer experience. All new code should use these functions.
# ============================================================================


def get_games(date_obj: date) -> List[Game]:
    """
    Get all games for a specific date as structured Game objects.

    This is the normalized version that returns type-safe dataclasses.
    For backward compatibility, use get_score_details() for raw dicts.

    Args:
        date_obj: Date to get games for

    Returns:
        List of Game objects with full type hints

    Example:
        >>> from datetime import date
        >>> games = get_games(date.today())
        >>> for game in games:
        ...     print(f"{game.away_team.abbrev} @ {game.home_team.abbrev}")
        ...     if game.is_live:
        ...         print(f"  LIVE: {game.score}")
    """
    raw_data = client.get_score_details(date_obj)
    return [Game.from_dict(game_data) for game_data in raw_data.get('games', [])]


def get_game(game_id: int) -> Game:
    """
    Get detailed game information as a structured Game object.

    This is the normalized version that returns a type-safe dataclass.
    For backward compatibility, use get_game_overview() for raw dict.

    Args:
        game_id: NHL game ID

    Returns:
        Game object with full type hints

    Example:
        >>> game = get_game(2023020001)
        >>> print(f"Score: {game.score.away} - {game.score.home}")
        >>> if game.is_final:
        ...     print("Game over!")
    """
    raw_data = client.get_game_overview(game_id)
    return Game.from_dict(raw_data)


def get_player_structured(player_id: int) -> Player:
    """
    Get player information as a structured Player object.

    This is the normalized version that returns a type-safe dataclass.
    For backward compatibility, use get_player() for raw dict.

    Args:
        player_id: NHL player ID

    Returns:
        Player object with full type hints

    Example:
        >>> player = get_player_structured(8478402)
        >>> print(f"{player.name.full} - {player.position.value}")
        >>> if player.stats:
        ...     print(f"Points: {player.stats.points}")
    """
    raw_data = client.get_player(player_id)
    return Player.from_dict(raw_data)


def get_standings_structured() -> Standings:
    """
    Get current NHL standings as a structured Standings object.

    This is the normalized version that returns a type-safe dataclass.
    For backward compatibility, use get_standings() for raw dict.

    Returns:
        Standings object with conference and division organization

    Example:
        >>> standings = get_standings_structured()
        >>> for team in standings.eastern.teams[:5]:
        ...     print(f"{team.team.abbrev}: {team.points} pts")
        >>> bruins = standings.get_team_by_abbrev('BOS')
        >>> print(f"Bruins: {bruins.record}")
    """
    raw_data = client.get_standings()
    return Standings.from_dict(raw_data)
