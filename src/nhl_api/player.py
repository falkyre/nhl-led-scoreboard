"""
DEPRECATION NOTICE:
    This PlayerStats class is a candidate for deprecation in favor of the new
    Player and PlayerStats dataclasses in src/nhl_api/models.py.

    Current usage:
    - boards/ovi_tracker.py
    - boards/player_stats.py
    - nhl_api/data.py (get_player_stats function)

    Migration path:
    - Use Player dataclass from models.py instead
    - client.get_player_structured(player_id) returns structured Player object
    - See TODO.md for migration strategy
"""

class PlayerStats:
    """Class to handle NHL API player statistics"""

    def __init__(self, player_data):
        """Initialize player stats from API response data"""
        self.player_id = player_data.get('playerId')
        first_name = player_data.get('firstName', {}).get('default', '')
        last_name = player_data.get('lastName', {}).get('default', '')
        self.name = f"{first_name} {last_name}"
        self.position = player_data.get('position', '')
        self.team = player_data.get('currentTeamAbbrev', '')
        self.team_id = player_data.get('currentTeamId', 0)
        self.sweater_number = player_data.get('sweaterNumber', 0)

        # Get current season stats
        current_stats = player_data.get('featuredStats', {}).get('regularSeason', {}).get('subSeason', {})
        self.games_played = current_stats.get('gamesPlayed', 0)

        # Get career stats
        career_stats = player_data.get('careerTotals', {}).get('regularSeason', {})


        # Handle different stats for goalies vs skaters
        if self.position == 'G':
            self.goals_against_avg = current_stats.get('goalsAgainstAvg', 0.0)
            self.save_percentage = current_stats.get('savePctg', 0.0)
            self.shutouts = current_stats.get('shutouts', 0)
            self.wins = current_stats.get('wins', 0)
            self.losses = current_stats.get('losses', 0)
        else:
            self.goals = current_stats.get('goals', 0)
            self.assists = current_stats.get('assists', 0)
            self.points = current_stats.get('points', 0)
            self.plus_minus = current_stats.get('plusMinus', 0)
            self.penalty_minutes = current_stats.get('pim', 0)
            self.power_play_goals = current_stats.get('powerPlayGoals', 0)
            self.game_winning_goals = current_stats.get('gameWinningGoals', 0)
            self.shots = current_stats.get('shots', 0)
            self.shooting_percentage = current_stats.get('shootingPctg', 0.0)
            self.career_goals = career_stats.get('goals', 0)

    @classmethod
    def from_api(cls, player_id):
        """Create PlayerStats instance from API call"""
        from nhl_api.data import fetch_player_data  # Import here to avoid circular imports
        data = fetch_player_data(player_id)
        return cls(data)

    def __str__(self):
        """String representation of player stats"""
        output = [
            f"\nPlayer: {self.name}",
            f"Team: {self.team}",
            f"Position: {self.position}",
            f"Games Played: {self.games_played}"
        ]

        if self.position == 'G':
            output.extend([
                f"GAA: {self.goals_against_avg:.2f}",
                f"Save %: {self.save_percentage:.3f}",
                f"Shutouts: {self.shutouts}"
            ])
        else:
            output.extend([
                f"Goals: {self.goals}",
                f"Assists: {self.assists}",
                f"Points: {self.points}",
                f"Plus/Minus: {self.plus_minus}",
                f"PIM: {self.penalty_minutes}",
                f"PPG: {self.power_play_goals}",
                f"GWG: {self.game_winning_goals}",
                f"Shots: {self.shots}",
                f"Shooting %: {self.shooting_percentage:.1f}"
            ])

        return "\n".join(output)
