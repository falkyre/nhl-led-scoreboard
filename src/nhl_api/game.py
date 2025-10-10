"""
Module that is used for getting basic information about a game
such as the scoreboard and the box score.
"""

from nhl_api.nhl_client import client


def overview(game_id):
    """
    Get game overview including play-by-play data.

    Args:
        game_id: NHL game ID

    Returns:
        Game details dictionary
    """
    return client.get_game_overview(game_id)
