import httpx
from unittest.mock import patch

def test_player_api(player_id):
    """Test direct API calls for player info and stats"""
    base_url = "https://api-web.nhle.com/v1/"
    
    # Get player info and stats from landing endpoint
    info_url = f"{base_url}player/{player_id}/landing"
    info_response = httpx.get(info_url)
    print(f"\nResponse Status: {info_response.status_code}")
    print(f"Response Text: {info_response.text[:200]}...")  # Print first 200 chars

    try:
        player_data = info_response.json()

        # Print results
        print("\nPlayer Info:")
        print(f"Name: {player_data.get('firstName', {}).get('default', '')} {player_data.get('lastName', {}).get('default', '')}")
        print(f"Position: {player_data.get('position', '')}")
        print(f"Team: {player_data.get('currentTeamAbbrev', '')}")

        print("\nCurrent Season Stats:")
        current_stats = player_data.get('featuredStats', {}).get('regularSeason', {}).get('subSeason', {})
        if player_data.get('position') == 'G':
            print(f"Games Played: {current_stats.get('gamesPlayed', 0)}")
            print(f"GAA: {current_stats.get('goalsAgainstAverage', 0.0)}")
            print(f"Save %: {current_stats.get('savePercentage', 0.0)}")
            print(f"Shutouts: {current_stats.get('shutouts', 0)}")
        else:
            print(f"Games Played: {current_stats.get('gamesPlayed', 0)}")
            print(f"Goals: {current_stats.get('goals', 0)}")
            print(f"Assists: {current_stats.get('assists', 0)}")
            print(f"Points: {current_stats.get('points', 0)}")
            print(f"Plus/Minus: {current_stats.get('plusMinus', 0)}")

    except Exception as e:
        print(f"\nError: {e}")


def get_player_stats(player_id):
    """Get player stats from the NHL API"""
    url = f'https://api-web.nhle.com/v1/player/{player_id}/landing'

    response = httpx.get(url)
    if response.status_code != 200:
        raise Exception('API request failed')

    data = response.json()
    current_stats = data['featuredStats']['regularSeason']['subSeason']

    return {
        'assists': current_stats['assists'],
        'goals': current_stats['goals'],
        'games_played': current_stats['gamesPlayed'],
        'plus_minus': current_stats['plusMinus'],
        'points': current_stats['points'],
        'penalty_minutes': current_stats['pim'],
        'power_play_goals': current_stats['powerPlayGoals'],
        'game_winning_goals': current_stats['gameWinningGoals'],
        'shots': current_stats['shots'],
        'shooting_percentage': current_stats['shootingPctg']
    }

if __name__ == "__main__":
    # Test with McDavid's ID
    test_player_api('8471214') 