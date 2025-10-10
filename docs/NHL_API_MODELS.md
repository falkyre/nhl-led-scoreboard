# NHL API Structured Data Models

This guide covers the modern dataclass-based models available for working with NHL API data in a type-safe, structured way.

## Overview

The NHL API client now supports two ways to access data:

1. **Raw dictionaries** (default) - Direct JSON responses from the API
2. **Structured dataclasses** (optional) - Typed Python objects with helper methods

## Why Use Structured Models?

✅ **Type Safety** - IDE autocomplete and type checking
✅ **Validation** - Data is validated when parsed
✅ **Helper Methods** - Convenient properties and methods
✅ **Documentation** - Self-documenting code
✅ **Consistency** - Standardized interface across the codebase

## Available Models

All models are defined in `src/nhl_api/models.py`:

- **Team** - Team information
- **Player** - Player information and stats
- **Game** - Game details, score, and state
- **Standings** - League standings with conferences/divisions
- **TeamStanding** - Individual team standings
- **TeamRecord** - Win-loss-OT record

## Usage Examples

### Getting Games (Structured)

```python
from nhl_api.nhl_client import client
from datetime import date

# Get structured Game objects
games = client.get_games_structured(date.today())

for game in games:
    print(f"{game.away_team} @ {game.home_team}")
    print(f"Score: {game.score}")
    print(f"State: {game.state.value}")

    # Use helper properties
    if game.is_live:
        print(f"LIVE - Period {game.period.number}")
    elif game.is_final:
        print("FINAL")
    elif game.is_scheduled:
        print(f"Starts at {game.game_date}")
```

### Getting Standings (Structured)

```python
from nhl_api.nhl_client import client

# Get structured Standings object
standings = client.get_standings_structured()

# Access by conference
print("Eastern Conference:")
for team_standing in standings.eastern.teams[:5]:  # Top 5
    team = team_standing.team
    record = team_standing.record
    print(f"{team.name.default}: {record} ({team_standing.points} pts)")

# Find specific team
bruins = standings.get_team_by_abbrev('BOS')
if bruins:
    print(f"\n{bruins.team.name.default}")
    print(f"Record: {bruins.record}")
    print(f"Position: #{bruins.division_sequence} in division")
    print(f"Goal Differential: {bruins.goal_differential:+d}")
```

### Getting Player Info (Structured)

```python
from nhl_api.nhl_client import client

# Connor McDavid
player = client.get_player_structured(8478402)

print(f"{player.name.full}")
print(f"Team: {player.team_abbrev}")
print(f"Position: {player.position.value}")
print(f"Number: #{player.sweater_number}")

if player.stats:
    stats = player.stats
    print(f"\nStats:")
    print(f"  GP: {stats.games_played}")
    print(f"  G: {stats.goals}")
    print(f"  A: {stats.assists}")
    print(f"  PTS: {stats.points}")
```

## Working with Raw Dictionaries (Default)

If you prefer raw dictionaries (for flexibility), use the standard methods:

```python
from nhl_api.data import get_score_details, get_standings, get_player
from datetime import date

# Returns dict
games_dict = get_score_details(date.today())

# Access dict keys
for game in games_dict['games']:
    home = game['homeTeam']['abbrev']
    away = game['awayTeam']['abbrev']
    print(f"{away} @ {home}")
```

## Model Reference

### Game Model

```python
@dataclass
class Game:
    id: int
    season: int
    game_type: int
    game_date: datetime
    venue: str
    home_team: Team
    away_team: Team
    score: Score
    state: GameState
    period: Optional[GamePeriod]
    time_remaining: Optional[str]

    # Properties
    @property
    def is_live(self) -> bool

    @property
    def is_final(self) -> bool

    @property
    def is_scheduled(self) -> bool
```

**Usage:**
```python
game = Game.from_dict(api_response)
if game.is_live and game.period:
    print(f"Period {game.period.number}: {game.time_remaining}")
```

### Team Model

```python
@dataclass
class Team:
    id: int
    abbrev: str
    name: TeamName
    logo: Optional[str]
    dark_logo: Optional[str]
    conference_name: Optional[str]
    division_name: Optional[str]
```

**Usage:**
```python
team = Team.from_dict(api_response)
print(f"{team.name.default} ({team.abbrev})")
print(f"Division: {team.division_name}")
```

### Player Model

```python
@dataclass
class Player:
    id: int
    name: PlayerName
    position: PlayerPosition
    sweater_number: int
    team_id: Optional[int]
    team_abbrev: Optional[str]
    headshot: Optional[str]
    stats: Optional[PlayerStats]
```

**Usage:**
```python
player = Player.from_dict(api_response)
print(f"#{player.sweater_number} {player.name.full}")

if player.position == PlayerPosition.GOALIE:
    print(f"GAA: {player.stats.goals_against_avg}")
else:
    print(f"Points: {player.stats.points}")
```

### TeamStanding Model

```python
@dataclass
class TeamStanding:
    team: Team
    record: TeamRecord
    points: int
    games_played: int
    conference_sequence: int
    division_sequence: int
    league_sequence: int
    wildcard_sequence: int
    streak_code: Optional[str]
    streak_count: int
    goal_differential: int
    goals_for: int
    goals_against: int
```

**Usage:**
```python
standing = TeamStanding.from_dict(api_response)
print(f"{standing.team.abbrev}: {standing.record}")
print(f"Points: {standing.points}")
print(f"Streak: {standing.streak_code}{standing.streak_count}")
```

### Standings Model

```python
@dataclass
class Standings:
    eastern: Conference
    western: Conference

    def get_team_by_id(self, team_id: int) -> Optional[TeamStanding]
    def get_team_by_abbrev(self, abbrev: str) -> Optional[TeamStanding]
```

**Usage:**
```python
standings = Standings.from_dict(api_response)

# Get division leaders
for team in standings.eastern.teams:
    if team.division_sequence == 1:
        print(f"{team.team.division_name}: {team.team.name.default}")

# Find specific team
leafs = standings.get_team_by_abbrev('TOR')
```

## Enums

### GameState

```python
class GameState(Enum):
    FUTURE = "FUT"
    PREVIEW = "PRE"
    LIVE = "LIVE"
    CRITICAL = "CRIT"
    FINAL = "FINAL"
    OFFICIAL_FINAL = "OFF"
```

**Usage:**
```python
if game.state == GameState.LIVE:
    print("Game is in progress!")
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

**Usage:**
```python
if player.position == PlayerPosition.GOALIE:
    print(f"Goalie: {player.name.full}")
```

## Helper Properties

### Score

```python
@dataclass
class Score:
    home: int
    away: int

    @property
    def total(self) -> int:
        """Total goals in game"""
        return self.home + self.away
```

**Usage:**
```python
if game.score.total > 8:
    print("High scoring game!")
```

### TeamRecord

```python
@dataclass
class TeamRecord:
    wins: int
    losses: int
    ot_losses: int

    @property
    def total_games(self) -> int

    @property
    def points(self) -> int
```

**Usage:**
```python
record = team_standing.record
win_pct = record.wins / record.total_games
print(f"Win%: {win_pct:.3f}")
```

## Converting Existing Code

### Before (Raw Dicts)

```python
from nhl_api.data import get_score_details
from datetime import date

data = get_score_details(date.today())
for game in data['games']:
    if game['gameState'] == 'LIVE':
        home_score = game['homeTeam']['score']
        away_score = game['awayTeam']['score']
        home_abbrev = game['homeTeam']['abbrev']
        away_abbrev = game['awayTeam']['abbrev']
        print(f"{away_abbrev} {away_score} @ {home_abbrev} {home_score}")
```

### After (Structured Models)

```python
from nhl_api.nhl_client import client
from datetime import date

games = client.get_games_structured(date.today())
for game in games:
    if game.is_live:
        print(f"{game.away_team.abbrev} {game.score.away} @ "
              f"{game.home_team.abbrev} {game.score.home}")
```

## Best Practices

1. **Use structured models for new code** - Easier to maintain and understand
2. **Keep raw dicts for flexibility** - When you need access to all API fields
3. **Type hints** - Use proper type hints with the models
4. **Error handling** - Models validate on creation, wrap in try/except if needed
5. **Documentation** - Models are self-documenting, use docstrings for clarity

## Creating Custom Models

You can extend existing models or create new ones:

```python
from dataclasses import dataclass
from nhl_api.models import Game

@dataclass
class GameWithPrediction(Game):
    """Game with win probability prediction"""
    home_win_probability: float = 0.5

    @property
    def predicted_winner(self) -> str:
        if self.home_win_probability > 0.5:
            return self.home_team.abbrev
        else:
            return self.away_team.abbrev
```

## Performance Considerations

- **Parsing overhead**: Structured models have minimal parsing overhead
- **Memory**: Models use slightly more memory than dicts (negligible)
- **Caching**: Models are stateless and can be cached
- **Lazy loading**: Import models only when needed (already done)

## Migration Path

For existing code, you don't need to change anything immediately:

1. ✅ **Old code works** - All existing dict-based code continues to work
2. ✅ **Gradual migration** - Convert to structured models as you refactor
3. ✅ **Mixed usage** - Use both approaches in the same codebase
4. ✅ **No breaking changes** - Structured models are additive, not replacing

## Examples: Common Tasks

### Display Today's Games

```python
from nhl_api.nhl_client import client
from datetime import date

games = client.get_games_structured(date.today())

print(f"Games for {date.today()}")
print("=" * 50)

for game in games:
    status = "🔴 LIVE" if game.is_live else ("✅ FINAL" if game.is_final else "🕐 UPCOMING")
    print(f"{status} {game.away_team.abbrev} @ {game.home_team.abbrev}")

    if not game.is_scheduled:
        print(f"   Score: {game.score}")
```

### Track Team Throughout Season

```python
from nhl_api.nhl_client import client

standings = client.get_standings_structured()
team = standings.get_team_by_abbrev('TOR')

if team:
    print(f"{team.team.name.default}")
    print(f"Record: {team.record} ({team.points} pts)")
    print(f"Division: #{team.division_sequence}")
    print(f"Conference: #{team.conference_sequence}")
    print(f"League: #{team.league_sequence}")
    print(f"Goals: {team.goals_for} for, {team.goals_against} against")
    print(f"Differential: {team.goal_differential:+d}")
```

### Compare Players

```python
from nhl_api.nhl_client import client

# McDavid vs Matthews
mcdavid = client.get_player_structured(8478402)
matthews = client.get_player_structured(8479318)

print(f"{mcdavid.name.full}: {mcdavid.stats.points} pts")
print(f"{matthews.name.full}: {matthews.stats.points} pts")

if mcdavid.stats.points > matthews.stats.points:
    print(f"{mcdavid.name.last} leads by {mcdavid.stats.points - matthews.stats.points}")
```

## Troubleshooting

### Model Parse Errors

If a model fails to parse API data:

```python
from nhl_api.models import Game

try:
    game = Game.from_dict(api_response)
except Exception as e:
    logger.error(f"Failed to parse game: {e}")
    # Fall back to raw dict
    game_dict = api_response
```

### Missing Fields

Models use `Optional` types and defaults for fields that might be missing:

```python
if game.period is not None:
    print(f"Period: {game.period.number}")
else:
    print("Game not started")
```

### Type Checking

Enable type checking in your IDE or use mypy:

```bash
mypy src/your_module.py
```

## Additional Resources

- See `src/nhl_api/models.py` for complete model definitions
- See `docs/NHL_API_USAGE.md` for general API usage
- See `src/nhl_api/client.py` for all available methods
