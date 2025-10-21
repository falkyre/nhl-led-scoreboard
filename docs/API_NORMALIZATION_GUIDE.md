# NHL API Normalization Guide

## Overview

The NHL API has been normalized to provide a consistent, type-safe interface. This document explains the changes and provides migration guidance.

## Architecture

### Two-Layer Design

```
Application Code
      ↓
Data Access Layer (src/nhl_api/data.py)
      ↓
HTTP Client Layer (src/nhl_api/client.py)
      ↓
NHL API
```

### Key Principles

1. **Consistent Naming**: All functions use `get_<resource>` pattern with snake_case parameters
2. **Type Safety**: Structured functions return dataclasses from `models.py`
3. **Backward Compatibility**: Legacy functions still available (return raw dicts)
4. **Clear Distinction**: Structured vs raw data access

---

## API Function Reference

### ✅ Normalized Functions (Use These)

These functions return typed dataclasses for IDE autocomplete and type checking:

```python
from nhl_api.data import (
    get_games,                    # Returns List[Game]
    get_game,                     # Returns Game
    get_player_structured,        # Returns Player
    get_standings_structured      # Returns Standings
)
```

### 📦 Legacy Functions (Backward Compatibility)

These functions return raw dictionaries:

```python
from nhl_api.data import (
    get_score_details,      # Returns Dict (use get_games instead)
    get_game_overview,      # Returns Dict (use get_game instead)
    get_player,             # Returns Dict (use get_player_structured instead)
    get_standings           # Returns Dict (use get_standings_structured instead)
)
```

---

## Migration Examples

### Example 1: Getting Today's Games

**Before (Raw Dicts):**
```python
from nhl_api.data import get_score_details
from datetime import date

data = get_score_details(date.today())
for game in data['games']:
    home_team = game['homeTeam']['abbrev']
    away_team = game['awayTeam']['abbrev']
    home_score = game['homeTeam']['score']
    away_score = game['awayTeam']['score']
    game_state = game['gameState']

    # Manual state checking
    if game_state == 'LIVE' or game_state == 'CRIT':
        print(f"LIVE: {away_team} {away_score} @ {home_team} {home_score}")
```

**After (Structured Objects):**
```python
from nhl_api.data import get_games
from datetime import date

games = get_games(date.today())
for game in games:
    # Clean attribute access with IDE autocomplete
    # Type hints work: game is of type Game

    if game.is_live:  # Built-in property
        print(f"LIVE: {game.away_team.abbrev} {game.score.away} @ "
              f"{game.home_team.abbrev} {game.score.home}")
    elif game.is_final:
        print(f"FINAL: {game}")  # __str__ method formats nicely
```

**Benefits:**
- IDE autocomplete works (`game.` shows all attributes)
- Type checking catches errors before runtime
- Cleaner code with properties (`.is_live`, `.is_final`)
- Less error-prone (no typos in dict keys)

### Example 2: Getting Standings

**Before (Raw Dicts):**
```python
from nhl_api.data import get_standings

standings_data = get_standings()
for team in standings_data['standings']:
    if team['conferenceName'] == 'Eastern':
        abbrev = team['teamAbbrev']['default']
        points = team['points']
        wins = team['wins']
        losses = team['losses']
        ot_losses = team['otLosses']
        print(f"{abbrev}: {wins}-{losses}-{ot_losses} ({points} pts)")
```

**After (Structured Objects):**
```python
from nhl_api.data import get_standings_structured

standings = get_standings_structured()

# Organized by conference
for team in standings.eastern.teams:
    print(f"{team.team.abbrev}: {team.record} ({team.points} pts)")

# Easy lookup
bruins = standings.get_team_by_abbrev('BOS')
if bruins:
    print(f"Bruins: {bruins.record.wins} wins, {bruins.points} points")
```

**Benefits:**
- Conference organization built-in
- Helper methods for lookups
- Record object with calculated properties
- Clean string representations

### Example 3: Getting Player Information

**Before (Raw Dicts):**
```python
from nhl_api.data import get_player

player_data = get_player(8478402)
first_name = player_data['firstName']['default']
last_name = player_data['lastName']['default']
position = player_data['position']

if 'featuredStats' in player_data:
    stats = player_data['featuredStats']['regularSeason']['subSeason']
    goals = stats.get('goals', 0)
    assists = stats.get('assists', 0)
    points = stats.get('points', 0)
    print(f"{first_name} {last_name} ({position}): {points} pts")
```

**After (Structured Objects):**
```python
from nhl_api.data import get_player_structured

player = get_player_structured(8478402)
print(f"{player.name.full} ({player.position.value})")

if player.stats:
    print(f"Stats: {player.stats.goals}G, {player.stats.assists}A, "
          f"{player.stats.points}P")
```

**Benefits:**
- Name handling is automatic (PlayerName with `.full` property)
- Position is an Enum (type-safe)
- Optional stats handled cleanly
- Shorter, more readable code

---

## Data Models Reference

All models are in `src/nhl_api/models.py`

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
    def is_live(self) -> bool: ...

    @property
    def is_final(self) -> bool: ...

    @property
    def is_scheduled(self) -> bool: ...
```

### Player Model

```python
@dataclass
class Player:
    id: int
    name: PlayerName        # .first, .last, .full
    position: PlayerPosition  # Enum: C, L, R, D, G
    sweater_number: int
    team_id: Optional[int]
    team_abbrev: Optional[str]
    headshot: Optional[str]
    stats: Optional[PlayerStats]
```

### Standings Model

```python
@dataclass
class Standings:
    eastern: Conference
    western: Conference

    def get_team_by_id(self, team_id: int) -> Optional[TeamStanding]: ...
    def get_team_by_abbrev(self, abbrev: str) -> Optional[TeamStanding]: ...

@dataclass
class TeamStanding:
    team: Team
    record: TeamRecord
    points: int
    games_played: int
    conference_sequence: int
    division_sequence: int
    # ... more fields
```

### Supporting Models

```python
@dataclass
class Team:
    id: int
    abbrev: str
    name: TeamName
    logo: Optional[str]
    # ...

@dataclass
class Score:
    home: int
    away: int

    @property
    def total(self) -> int: ...

@dataclass
class TeamRecord:
    wins: int
    losses: int
    ot_losses: int

    @property
    def points(self) -> int: ...

    def __str__(self) -> str:  # Returns "W-L-OTL"
```

---

## Migration Strategy

### Phase 1: Learn (Current)
- New normalized functions added to `data.py`
- Legacy functions still work
- No breaking changes

### Phase 2: Migrate Gradually
- Update new code to use normalized functions
- Refactor existing code module by module
- Test each module after migration

### Phase 3: Deprecate (Future)
- Add deprecation warnings to legacy functions
- Remove legacy functions after migration complete

---

## Best Practices

### ✅ DO

```python
# Use structured functions for new code
from nhl_api.data import get_games, get_standings_structured

games = get_games(date.today())
standings = get_standings_structured()

# Use built-in properties
if game.is_live:
    print(f"{game.away_team.abbrev} @ {game.home_team.abbrev}")

# Use helper methods
team = standings.get_team_by_abbrev('BOS')
```

### ❌ DON'T

```python
# Don't use raw dict access with structured objects
games = get_games(date.today())
for game in games:
    home = game['homeTeam']  # ❌ Game is not a dict!

# Don't use raw functions for new code
data = get_score_details(date.today())  # ❌ Returns raw dict
games_list = data['games']
```

---

## Type Hints Example

With structured objects, you get full type checking:

```python
from nhl_api.data import get_games, get_standings_structured
from nhl_api.models import Game, Standings
from datetime import date
from typing import List

def analyze_games(game_date: date) -> List[Game]:
    """Get and filter live games."""
    games: List[Game] = get_games(game_date)

    # IDE knows games is List[Game]
    # Type checker validates this code
    live_games = [game for game in games if game.is_live]

    return live_games

def get_division_leaders(standings: Standings) -> None:
    """Print division leaders."""
    # IDE provides autocomplete for standings.eastern
    for team in standings.eastern.teams[:3]:
        # IDE knows team is TeamStanding
        print(f"{team.team.abbrev}: {team.points} pts")
```

---

## Common Patterns

### Pattern: Game State Checking

```python
# Old way (string comparison)
if game_dict['gameState'] == 'LIVE' or game_dict['gameState'] == 'CRIT':
    # ...

# New way (property)
if game.is_live:
    # ...

# Available properties:
# - game.is_live
# - game.is_final
# - game.is_scheduled
```

### Pattern: Team Lookup

```python
# Old way (manual loop)
for team in standings_data['standings']:
    if team['teamAbbrev']['default'] == 'BOS':
        bruins = team
        break

# New way (helper method)
bruins = standings.get_team_by_abbrev('BOS')
```

### Pattern: Score Access

```python
# Old way (nested dict)
home_score = game_dict['homeTeam']['score']
away_score = game_dict['awayTeam']['score']
total = home_score + away_score

# New way (Score object)
total = game.score.total
print(game.score)  # "3-2"
```

---

## Testing Structured Objects

```python
import pytest
from nhl_api.data import get_games
from nhl_api.models import Game, GameState
from datetime import date

def test_get_games_returns_game_objects():
    """Verify get_games returns structured Game objects."""
    games = get_games(date(2024, 1, 15))

    assert isinstance(games, list)
    if games:
        assert isinstance(games[0], Game)
        assert hasattr(games[0], 'home_team')
        assert hasattr(games[0], 'away_team')
        assert isinstance(games[0].state, GameState)

def test_game_properties():
    """Verify Game properties work correctly."""
    games = get_games(date.today())

    for game in games:
        # These should not raise AttributeError
        _ = game.is_live
        _ = game.is_final
        _ = game.is_scheduled

        # State should be valid GameState enum
        assert isinstance(game.state, GameState)
```

---

## Summary

### Benefits of Normalization

1. **Type Safety**: IDE autocomplete and type checking
2. **Cleaner Code**: Properties instead of dict access
3. **Consistency**: All functions follow same pattern
4. **Maintainability**: Easier to understand and refactor
5. **Better DX**: Developer experience improved significantly

### Next Steps

1. Use normalized functions (`get_games`, `get_standings_structured`) for all new code
2. Gradually migrate existing code module by module
3. Refer to this guide and `src/nhl_api/models.py` for available attributes
4. Run type checker (`mypy`) to catch errors early

---

## Questions?

- Check `src/nhl_api/models.py` for complete model definitions
- Check `src/nhl_api/data.py` for all available functions
- Check `docs/NHL_API_MODELS.md` for additional model documentation
