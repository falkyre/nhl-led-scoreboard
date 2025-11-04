# NHL API Reference

Complete reference for the NHL LED Scoreboard API client, models, and functions.

## Quick Start

```python
from nhl_api.nhl_client import client
from datetime import date

# Get today's games
games = client.get_games_structured(date.today())
for game in games:
    if game.is_live:
        print(f"{game.away_team.abbrev} @ {game.home_team.abbrev}: {game.score}")

# Get standings
standings = client.get_standings_structured()
bruins = standings.get_team_by_abbrev('BOS')
print(f"{bruins.team.name.default}: {bruins.record} ({bruins.points} pts)")

# Get player info
player = client.get_player_structured(8478402)  # Connor McDavid
print(f"{player.name.full}: {player.stats.points} pts")
```

## API Client

### NHLAPIClient

Located in `src/nhl_api/nhl_client.py`. Singleton instance available as `client`.

**Features:**
- Automatic retry with exponential backoff
- Timeout handling (default 10s)
- Request logging
- Error wrapping with `NHLAPIError`

**Key Methods:**

```python
# Games
client.get_score_details(date_obj) -> Dict
client.get_games_structured(date_obj) -> List[Game]
client.get_game_overview(game_id) -> Dict
client.get_game_structured(game_id) -> Game

# Standings
client.get_standings() -> Dict
client.get_standings_structured() -> Standings

# Players
client.get_player(player_id) -> Dict
client.get_player_structured(player_id) -> Player

# Teams
client.get_team_schedule(team_code, season=None) -> Dict

# Playoffs
client.get_playoff_carousel(season) -> Dict
client.get_series_record(series_code, season) -> Dict

# Misc
client.get_game_status() -> Dict
client.get_current_season() -> Dict
```

## Models

All models are in `src/nhl_api/models.py` and created via `Model.from_dict(api_response)`.

### Game

Full game information with state checking properties.

```python
@dataclass
class Game:
    id: int
    season: int
    game_type: int
    game_date: datetime              # Timezone-aware UTC datetime
    venue: str
    home_team: Team
    away_team: Team
    score: Score
    state: GameState                 # Enum
    period: Optional[GamePeriod]
    time_remaining: Optional[str]

    # Properties
    @property
    def is_live(self) -> bool:
        """True if game is LIVE or CRIT"""

    @property
    def is_final(self) -> bool:
        """True if game is FINAL or OFF"""

    @property
    def is_scheduled(self) -> bool:
        """True if game is FUT or PRE"""

    @property
    def is_irregular(self) -> bool:
        """True if game is POSTPONED, CANCELLED, SUSPENDED, or TIME_TBD"""
```

**Usage:**
```python
game = client.get_game_structured(game_id)
if game.is_live:
    print(f"Period {game.period.number}: {game.time_remaining}")
print(f"{game.away_team.abbrev} {game.score.away} @ {game.home_team.abbrev} {game.score.home}")
```

### Team

Team identification and metadata.

```python
@dataclass
class Team:
    id: int
    abbrev: str                      # 3-letter code (e.g., "BOS")
    name: TeamName
    logo: Optional[str]
    dark_logo: Optional[str]
    conference_name: Optional[str]
    division_name: Optional[str]

@dataclass
class TeamName:
    default: str                     # e.g., "Boston Bruins"
    french: Optional[str]
```

**Usage:**
```python
team = game.home_team
print(f"{team.name.default} ({team.abbrev})")
print(f"Division: {team.division_name}")
```

### Player

Player information and statistics.

```python
@dataclass
class Player:
    id: int
    name: PlayerName
    position: PlayerPosition         # Enum: C, L, R, D, G
    sweater_number: int
    team_id: Optional[int]
    team_abbrev: Optional[str]
    headshot: Optional[str]
    stats: Optional[PlayerStats]

@dataclass
class PlayerName:
    first: str
    last: str

    @property
    def full(self) -> str:           # "First Last"

@dataclass
class PlayerStats:
    games_played: int
    goals: int
    assists: int
    points: int
    plus_minus: int
    penalty_minutes: int
    power_play_goals: int
    game_winning_goals: int
    shots: int
    shooting_percentage: float
    # Goalie-specific fields (all Optional):
    goals_against_avg: Optional[float]
    save_percentage: Optional[float]
    shutouts: Optional[int]
    wins: Optional[int]
    losses: Optional[int]
    ot_losses: Optional[int]
```

**Usage:**
```python
player = client.get_player_structured(8478402)
print(f"#{player.sweater_number} {player.name.full} ({player.position.value})")

if player.position == PlayerPosition.GOALIE:
    print(f"GAA: {player.stats.goals_against_avg}")
else:
    print(f"Points: {player.stats.points} ({player.stats.goals}G, {player.stats.assists}A)")
```

### Standings

League-wide standings with conference/division organization.

```python
@dataclass
class Standings:
    eastern: Conference
    western: Conference

    def get_team_by_id(self, team_id: int) -> Optional[TeamStanding]
    def get_team_by_abbrev(self, abbrev: str) -> Optional[TeamStanding]

@dataclass
class Conference:
    teams: List[TeamStanding]        # Sorted by conference_sequence

@dataclass
class TeamStanding:
    team: Team
    record: TeamRecord
    points: int
    games_played: int
    conference_sequence: int         # Position in conference (1-16)
    division_sequence: int           # Position in division (1-8)
    league_sequence: int            # Overall position (1-32)
    wildcard_sequence: int
    streak_code: Optional[str]       # "W" or "L" or "OT"
    streak_count: int
    goal_differential: int
    goals_for: int
    goals_against: int
```

**Usage:**
```python
standings = client.get_standings_structured()

# Get specific team
bruins = standings.get_team_by_abbrev('BOS')
print(f"{bruins.team.name.default}")
print(f"Record: {bruins.record}")
print(f"Points: {bruins.points}")
print(f"Position: #{bruins.division_sequence} in division")

# Division leaders
for team in standings.eastern.teams:
    if team.division_sequence == 1:
        print(f"{team.team.division_name} leader: {team.team.name.default}")
```

### Supporting Models

#### Score

```python
@dataclass
class Score:
    home: int
    away: int

    @property
    def total(self) -> int:
        """Total goals scored"""

    def __str__(self) -> str:
        return f"{self.away}-{self.home}"
```

#### TeamRecord

```python
@dataclass
class TeamRecord:
    wins: int
    losses: int
    ot_losses: int

    @property
    def total_games(self) -> int:
        """Total games played"""

    @property
    def points(self) -> int:
        """Total points (wins*2 + ot_losses*1)"""

    def __str__(self) -> str:
        return f"{self.wins}-{self.losses}-{self.ot_losses}"
```

#### GamePeriod

```python
@dataclass
class GamePeriod:
    number: int                      # 1, 2, 3, or 4+ for OT
    type: str                        # "REG" or "OT" or "SO"
```

## Enums

### GameState

```python
class GameState(Enum):
    FUTURE = "FUT"                   # Not yet started
    PREVIEW = "PRE"                  # Pregame
    LIVE = "LIVE"                    # In progress
    CRITICAL = "CRIT"                # Final minutes/OT
    FINAL = "FINAL"                  # Complete
    OFFICIAL_FINAL = "OFF"           # Official final
    # Irregular states
    POSTPONED = "PPD"
    CANCELLED = "CANC"
    SUSPENDED = "SUSP"
    TIME_TBD = "TBD"
```

### PlayerPosition

```python
class PlayerPosition(Enum):
    CENTER = "C"
    LEFT_WING = "L"
    RIGHT_WING = "R"
    DEFENSE = "D"
    GOALIE = "G"
```

## Legacy Functions

These functions in `src/nhl_api/data.py` return raw dictionaries for backward compatibility:

```python
from nhl_api.data import (
    get_score_details,       # Use client.get_games_structured() instead
    get_game_overview,       # Use client.get_game_structured() instead
    get_player,              # Use client.get_player_structured() instead
    get_standings,           # Use client.get_standings_structured() instead
)
```

**Note:** New code should use the structured functions that return typed models.

## Common Patterns

### Check Game State

```python
game = client.get_game_structured(game_id)

if game.is_live:
    print(f"LIVE - Period {game.period.number}")
elif game.is_final:
    print("FINAL")
elif game.is_scheduled:
    print(f"Starts {game.game_date}")
elif game.is_irregular:
    print(f"Game status: {game.state.value}")
```

### Filter Games

```python
games = client.get_games_structured(date.today())

live_games = [g for g in games if g.is_live]
completed_games = [g for g in games if g.is_final]
```

### Display Score

```python
game = client.get_game_structured(game_id)
print(f"{game.away_team.abbrev} {game.score.away} @ {game.home_team.abbrev} {game.score.home}")

# Or use Score's __str__:
print(f"Final score: {game.score}")  # "3-2"
```

### Look Up Team in Standings

```python
standings = client.get_standings_structured()

# By abbreviation
bruins = standings.get_team_by_abbrev('BOS')

# By ID
bruins = standings.get_team_by_id(6)

if bruins:
    print(f"{bruins.team.name.default}: {bruins.record} ({bruins.points} pts)")
    print(f"Streak: {bruins.streak_code}{bruins.streak_count}")
```

### Calculate Win Percentage

```python
team_standing = standings.get_team_by_abbrev('TOR')
record = team_standing.record
win_pct = record.wins / record.total_games
print(f"Win%: {win_pct:.3f}")
```

## Error Handling

All API calls can raise `NHLAPIError`:

```python
from nhl_api.nhl_client import NHLAPIError

try:
    games = client.get_games_structured(date.today())
except NHLAPIError as e:
    logger.error(f"Failed to fetch games: {e}")
    # Fall back or retry
```

The client automatically retries failed requests with exponential backoff, so `NHLAPIError` only raises after all retries are exhausted.

## Type Hints

All models and functions have full type hints:

```python
from nhl_api.nhl_client import client
from nhl_api.models import Game, Standings, Player
from datetime import date
from typing import List, Optional

def get_live_games(game_date: date) -> List[Game]:
    """Get all live games for a date."""
    games: List[Game] = client.get_games_structured(game_date)
    return [game for game in games if game.is_live]

def find_team(standings: Standings, abbrev: str) -> Optional[TeamStanding]:
    """Find team in standings by abbreviation."""
    return standings.get_team_by_abbrev(abbrev)
```

Use with `mypy` or your IDE's type checker for compile-time error detection.

## See Also

- [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) - How to migrate from legacy dict-based API
- [../TODO.md](../TODO.md) - Current development status and roadmap
- `src/nhl_api/models.py` - Complete model definitions with all fields
- `src/nhl_api/nhl_client.py` - API client implementation
