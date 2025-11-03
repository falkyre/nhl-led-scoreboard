"""
NHL API Data Models

Modern dataclasses for structured NHL API data with type hints and helper methods.
These classes provide a clean, typed interface to NHL API responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ============================================================================
# Enums
# ============================================================================

class GameState(Enum):
    """Possible game states"""
    FUTURE = "FUT"
    PREVIEW = "PRE"
    LIVE = "LIVE"
    CRITICAL = "CRIT"
    FINAL = "FINAL"
    OFFICIAL_FINAL = "OFF"
    # Irregular game states (codes 8 and 9 in old NHL API)
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"
    TIME_TBD = "TBD"


class PlayerPosition(Enum):
    """Player positions"""
    CENTER = "C"
    LEFT_WING = "L"
    RIGHT_WING = "R"
    DEFENSE = "D"
    GOALIE = "G"


# ============================================================================
# Team Models
# ============================================================================

@dataclass
class TeamName:
    """Team name in multiple languages"""
    default: str
    fr: Optional[str] = None


@dataclass
class Team:
    """NHL Team information"""
    id: int
    abbrev: str
    name: TeamName
    logo: Optional[str] = None
    dark_logo: Optional[str] = None

    # Conference and division
    conference_name: Optional[str] = None
    division_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Team':
        """Create Team from API response dictionary"""
        name_data = data.get('teamName', {})
        if isinstance(name_data, dict):
            name = TeamName(
                default=name_data.get('default', ''),
                fr=name_data.get('fr')
            )
        else:
            name = TeamName(default=str(name_data))

        return cls(
            id=data.get('id', 0),
            abbrev=data.get('abbrev', data.get('teamAbbrev', {}).get('default', '')),
            name=name,
            logo=data.get('logo'),
            dark_logo=data.get('darkLogo'),
            conference_name=data.get('conferenceName'),
            division_name=data.get('divisionName')
        )

    def __str__(self) -> str:
        return f"{self.name.default} ({self.abbrev})"


@dataclass
class TeamRecord:
    """Team win-loss record"""
    wins: int = 0
    losses: int = 0
    ot_losses: int = 0

    @property
    def total_games(self) -> int:
        """Total games played"""
        return self.wins + self.losses + self.ot_losses

    @property
    def points(self) -> int:
        """Calculate points (2 for win, 1 for OT loss)"""
        return (self.wins * 2) + self.ot_losses

    def __str__(self) -> str:
        return f"{self.wins}-{self.losses}-{self.ot_losses}"


@dataclass
class TeamStanding:
    """Team standings information"""
    team: Team
    record: TeamRecord
    points: int
    games_played: int

    # Sequences (positions)
    conference_sequence: int
    division_sequence: int
    league_sequence: int
    wildcard_sequence: int = 0

    # Streaks
    streak_code: Optional[str] = None
    streak_count: int = 0

    # Additional stats
    goal_differential: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TeamStanding':
        """Create TeamStanding from API response"""
        team = Team.from_dict(data)

        wins = data.get('wins', 0)
        losses = data.get('losses', 0)
        ot_losses = data.get('otLosses', 0)
        record = TeamRecord(wins=wins, losses=losses, ot_losses=ot_losses)

        return cls(
            team=team,
            record=record,
            points=data.get('points', 0),
            games_played=data.get('gamesPlayed', 0),
            conference_sequence=data.get('conferenceSequence', 0),
            division_sequence=data.get('divisionSequence', 0),
            league_sequence=data.get('leagueSequence', 0),
            wildcard_sequence=data.get('wildcardSequence', 0),
            streak_code=data.get('streakCode'),
            streak_count=data.get('streakCount', 0),
            goal_differential=data.get('goalDifferential', 0),
            goals_for=data.get('goalsFor', 0),
            goals_against=data.get('goalsAgainst', 0)
        )


# ============================================================================
# Player Models
# ============================================================================

@dataclass
class PlayerName:
    """Player name information"""
    first: str
    last: str

    @property
    def full(self) -> str:
        """Full name"""
        return f"{self.first} {self.last}"

    def __str__(self) -> str:
        return self.full


@dataclass
class PlayerStats:
    """Player statistics"""
    games_played: int = 0

    # Skater stats
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    penalty_minutes: int = 0
    power_play_goals: int = 0
    shorthanded_goals: int = 0
    game_winning_goals: int = 0
    shots: int = 0
    shooting_percentage: float = 0.0

    # Goalie stats
    wins: int = 0
    losses: int = 0
    goals_against_avg: float = 0.0
    save_percentage: float = 0.0
    shutouts: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any], position: str) -> 'PlayerStats':
        """Create PlayerStats from API response"""
        stats = cls(games_played=data.get('gamesPlayed', 0))

        if position == 'G':
            # Goalie stats
            stats.wins = data.get('wins', 0)
            stats.losses = data.get('losses', 0)
            stats.goals_against_avg = data.get('goalsAgainstAvg', 0.0)
            stats.save_percentage = data.get('savePctg', 0.0)
            stats.shutouts = data.get('shutouts', 0)
        else:
            # Skater stats
            stats.goals = data.get('goals', 0)
            stats.assists = data.get('assists', 0)
            stats.points = data.get('points', 0)
            stats.plus_minus = data.get('plusMinus', 0)
            stats.penalty_minutes = data.get('pim', 0)
            stats.power_play_goals = data.get('powerPlayGoals', 0)
            stats.shorthanded_goals = data.get('shortHandedGoals', 0)
            stats.game_winning_goals = data.get('gameWinningGoals', 0)
            stats.shots = data.get('shots', 0)
            stats.shooting_percentage = data.get('shootingPctg', 0.0)

        return stats


@dataclass
class Player:
    """NHL Player information"""
    id: int
    name: PlayerName
    position: PlayerPosition
    sweater_number: int
    team_id: Optional[int] = None
    team_abbrev: Optional[str] = None
    headshot: Optional[str] = None

    # Current season stats
    stats: Optional[PlayerStats] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Player':
        """Create Player from API response"""
        first_name = data.get('firstName', {})
        last_name = data.get('lastName', {})

        if isinstance(first_name, dict):
            first_name = first_name.get('default', '')
        if isinstance(last_name, dict):
            last_name = last_name.get('default', '')

        name = PlayerName(first=str(first_name), last=str(last_name))

        position_code = data.get('position', data.get('positionCode', 'C'))
        try:
            position = PlayerPosition(position_code)
        except ValueError:
            position = PlayerPosition.CENTER

        # Get stats if available
        stats = None
        if 'featuredStats' in data:
            featured = data['featuredStats'].get('regularSeason', {}).get('subSeason', {})
            stats = PlayerStats.from_dict(featured, position.value)

        return cls(
            id=data.get('playerId', data.get('id', 0)),
            name=name,
            position=position,
            sweater_number=data.get('sweaterNumber', 0),
            team_id=data.get('currentTeamId'),
            team_abbrev=data.get('currentTeamAbbrev'),
            headshot=data.get('headshot'),
            stats=stats
        )

    def __str__(self) -> str:
        return f"#{self.sweater_number} {self.name} ({self.position.value})"


# ============================================================================
# Game Models
# ============================================================================

@dataclass
class Score:
    """Game score"""
    home: int = 0
    away: int = 0

    @property
    def total(self) -> int:
        """Total goals in game"""
        return self.home + self.away

    def __str__(self) -> str:
        return f"{self.away}-{self.home}"


@dataclass
class GamePeriod:
    """Period information"""
    number: int
    type: str  # "REG", "OT", "SO"

    @property
    def is_overtime(self) -> bool:
        return self.type == "OT"

    @property
    def is_shootout(self) -> bool:
        return self.type == "SO"


@dataclass
class Game:
    """NHL Game information"""
    id: int
    season: int
    game_type: int
    game_date: datetime
    venue: str

    # Teams
    home_team: Team
    away_team: Team

    # Score
    score: Score

    # Game state
    state: GameState
    period: Optional[GamePeriod] = None

    # Clock
    time_remaining: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Game':
        """Create Game from API response"""
        home_team = Team.from_dict(data.get('homeTeam', {}))
        away_team = Team.from_dict(data.get('awayTeam', {}))

        score = Score(
            home=data.get('homeTeam', {}).get('score', 0),
            away=data.get('awayTeam', {}).get('score', 0)
        )

        try:
            state = GameState(data.get('gameState', 'FUT'))
        except ValueError:
            state = GameState.FUTURE

        # Parse game date
        game_date_str = data.get('gameDate', data.get('startTimeUTC', ''))
        try:
            game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            game_date = datetime.now()

        # Parse period if in progress
        period = None
        if 'period' in data and 'periodDescriptor' in data:
            period = GamePeriod(
                number=data['period'],
                type=data['periodDescriptor'].get('periodType', 'REG')
            )

        return cls(
            id=data.get('id', 0),
            season=data.get('season', 0),
            game_type=data.get('gameType', 2),
            game_date=game_date,
            venue=data.get('venue', {}).get('default', 'Unknown'),
            home_team=home_team,
            away_team=away_team,
            score=score,
            state=state,
            period=period,
            time_remaining=data.get('clock', {}).get('timeRemaining')
        )

    @property
    def is_live(self) -> bool:
        """Check if game is currently live"""
        return self.state in (GameState.LIVE, GameState.CRITICAL)

    @property
    def is_final(self) -> bool:
        """Check if game is final"""
        return self.state in (GameState.FINAL, GameState.OFFICIAL_FINAL)

    @property
    def is_scheduled(self) -> bool:
        """Check if game is scheduled (not started)"""
        return self.state in (GameState.FUTURE, GameState.PREVIEW)

    @property
    def is_irregular(self) -> bool:
        """Check if game has irregular status (postponed, cancelled, suspended, TBD)"""
        return self.state in (GameState.POSTPONED, GameState.CANCELLED, GameState.SUSPENDED, GameState.TIME_TBD)

    def __str__(self) -> str:
        return f"{self.away_team.abbrev} @ {self.home_team.abbrev} - {self.score}"


# ============================================================================
# Standings Models
# ============================================================================

@dataclass
class Division:
    """Division standings"""
    name: str
    teams: List[TeamStanding] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name} Division ({len(self.teams)} teams)"


@dataclass
class Conference:
    """Conference standings"""
    name: str
    teams: List[TeamStanding] = field(default_factory=list)
    divisions: List[Division] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name} Conference ({len(self.teams)} teams)"


@dataclass
class Standings:
    """Complete NHL standings"""
    eastern: Conference
    western: Conference

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Standings':
        """Create Standings from API response"""
        eastern_teams = []
        western_teams = []

        for team_data in data.get('standings', []):
            standing = TeamStanding.from_dict(team_data)

            if standing.team.conference_name == 'Eastern':
                eastern_teams.append(standing)
            elif standing.team.conference_name == 'Western':
                western_teams.append(standing)

        # Sort by conference sequence
        eastern_teams.sort(key=lambda x: x.conference_sequence)
        western_teams.sort(key=lambda x: x.conference_sequence)

        eastern = Conference(name='Eastern', teams=eastern_teams)
        western = Conference(name='Western', teams=western_teams)

        return cls(eastern=eastern, western=western)

    def get_team_by_id(self, team_id: int) -> Optional[TeamStanding]:
        """Find a team by ID"""
        for standing in self.eastern.teams + self.western.teams:
            if standing.team.id == team_id:
                return standing
        return None

    def get_team_by_abbrev(self, abbrev: str) -> Optional[TeamStanding]:
        """Find a team by abbreviation"""
        for standing in self.eastern.teams + self.western.teams:
            if standing.team.abbrev == abbrev:
                return standing
        return None
