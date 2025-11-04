# NHL API Migration Guide

Guide for migrating from legacy dict-based API to structured models.

## Why Migrate?

**Benefits of structured models:**

- ✅ **Type safety** - Catch errors at development time, not runtime
- ✅ **IDE autocomplete** - See all available fields while typing
- ✅ **Cleaner code** - `game.score.home` instead of `game['homeTeam']['score']`
- ✅ **Self-documenting** - Type hints show what data is available
- ✅ **Helper properties** - Built-in methods like `is_live`, `is_final`
- ✅ **Single source of truth** - API changes handled in one place

## Migration Strategy

**Approach:** Gradual, module-by-module migration. No need to change everything at once.

1. Pick one module/file to migrate
2. Update imports to use structured functions
3. Replace dict access with object properties
4. Test thoroughly
5. Commit
6. Repeat with next module

Both old and new APIs work simultaneously - no breaking changes.

## Quick Reference

### Function Names

| Old (returns Dict) | New (returns Model) | Model Type |
|--------------------|---------------------|------------|
| `get_score_details(date)` | `client.get_games_structured(date)` | `List[Game]` |
| `get_game_overview(id)` | `client.get_game_structured(id)` | `Game` |
| `get_player(id)` | `client.get_player_structured(id)` | `Player` |
| `get_standings()` | `client.get_standings_structured()` | `Standings` |

### Data Access Changes

| Old (Dict) | New (Object) |
|------------|--------------|
| `game['homeTeam']['abbrev']` | `game.home_team.abbrev` |
| `game['awayTeam']['score']` | `game.score.away` |
| `game['gameState'] == 'LIVE'` | `game.is_live` |
| `game['gameState'] in ['FINAL', 'OFF']` | `game.is_final` |
| `player['firstName']['default']` | `player.name.first` |
| `player['position']` | `player.position.value` |
| `team['teamAbbrev']['default']` | `team.abbrev` |

## Migration Examples

### Example 1: Game State Checking

**Before (dict-based):**
```python
from nhl_api.data import get_game_overview

overview = get_game_overview(game_id)

if overview["gameState"] == "LIVE" or overview["gameState"] == "CRIT":
    print("Game is live!")
elif overview["gameState"] == "FINAL" or overview["gameState"] == "OFF":
    print("Game is over")
elif overview["gameState"] == "FUT" or overview["gameState"] == "PRE":
    print("Game hasn't started")
```

**After (structured):**
```python
from nhl_api.nhl_client import client

game = client.get_game_structured(game_id)

if game.is_live:
    print("Game is live!")
elif game.is_final:
    print("Game is over")
elif game.is_scheduled:
    print("Game hasn't started")
```

**Benefits:**
- No manual string comparison
- Typo-proof (IDE catches errors)
- Handles all state variations automatically
- Cleaner, more readable

### Example 2: Displaying Games

**Before (dict-based):**
```python
from nhl_api.data import get_score_details
from datetime import date

data = get_score_details(date.today())
if not data:
    return

for game in data['games']:
    home_team = game['homeTeam']['abbrev']
    away_team = game['awayTeam']['abbrev']
    home_score = game['homeTeam']['score']
    away_score = game['awayTeam']['score']
    game_state = game['gameState']

    if game_state == 'LIVE' or game_state == 'CRIT':
        print(f"LIVE: {away_team} {away_score} @ {home_team} {home_score}")
    elif game_state == 'FINAL' or game_state == 'OFF':
        print(f"FINAL: {away_team} {away_score} @ {home_team} {home_score}")
```

**After (structured):**
```python
from nhl_api.nhl_client import client
from datetime import date

games = client.get_games_structured(date.today())
if not games:
    return

for game in games:
    if game.is_live:
        print(f"LIVE: {game.away_team.abbrev} {game.score.away} @ "
              f"{game.home_team.abbrev} {game.score.home}")
    elif game.is_final:
        print(f"FINAL: {game.away_team.abbrev} {game.score.away} @ "
              f"{game.home_team.abbrev} {game.score.home}")
```

**Benefits:**
- Shorter, cleaner code
- Type hints work (`game` is type `Game`)
- Properties handle complex logic internally
- No nested dict access

### Example 3: Working with Standings

**Before (dict-based):**
```python
from nhl_api.data import get_standings

standings_data = get_standings()

# Find a specific team
bruins = None
for team in standings_data['standings']:
    if team['teamAbbrev']['default'] == 'BOS':
        bruins = team
        break

if bruins:
    name = bruins['teamName']['default']
    wins = bruins['wins']
    losses = bruins['losses']
    ot = bruins['otLosses']
    points = bruins['points']
    print(f"{name}: {wins}-{losses}-{ot} ({points} pts)")
```

**After (structured):**
```python
from nhl_api.nhl_client import client

standings = client.get_standings_structured()

# Find a specific team
bruins = standings.get_team_by_abbrev('BOS')

if bruins:
    print(f"{bruins.team.name.default}: {bruins.record} ({bruins.points} pts)")
```

**Benefits:**
- Built-in lookup helper
- TeamRecord has `__str__` method (formats as "W-L-OTL")
- Organized by conference automatically
- Much shorter code

### Example 4: Player Information

**Before (dict-based):**
```python
from nhl_api.data import get_player

player_data = get_player(8478402)  # McDavid

first = player_data['firstName']['default']
last = player_data['lastName']['default']
pos = player_data['position']
number = player_data['sweaterNumber']

stats = player_data.get('featuredStats', {}).get('regularSeason', {}).get('subSeason', {})
goals = stats.get('goals', 0)
assists = stats.get('assists', 0)
points = stats.get('points', 0)

print(f"#{number} {first} {last} ({pos})")
print(f"Stats: {goals}G {assists}A {points}P")
```

**After (structured):**
```python
from nhl_api.nhl_client import client

player = client.get_player_structured(8478402)  # McDavid

print(f"#{player.sweater_number} {player.name.full} ({player.position.value})")

if player.stats:
    print(f"Stats: {player.stats.goals}G {player.stats.assists}A {player.stats.points}P")
```

**Benefits:**
- `name.full` property handles formatting
- Clean stats access with Optional handling
- Position is an Enum (type-safe)
- No nested dict traversal

## Common Migration Patterns

### Pattern 1: Import Changes

```python
# OLD
from nhl_api.data import get_score_details, get_game_overview, get_player, get_standings

# NEW
from nhl_api.nhl_client import client
from nhl_api.models import Game, Player, Standings  # For type hints
```

### Pattern 2: Game State Methods → Properties

```python
# OLD - calling methods on Status class
if self.status.is_live(game['gameState']):
    # ...
if self.status.is_final(game['gameState']):
    # ...

# NEW - using properties on Game object
if game.is_live:
    # ...
if game.is_final:
    # ...
```

### Pattern 3: Nested Dict → Object Properties

```python
# OLD - nested dictionary access
home = game['homeTeam']['abbrev']
away = game['awayTeam']['abbrev']
home_score = game['homeTeam']['score']
away_score = game['awayTeam']['score']

# NEW - clean object properties
home = game.home_team.abbrev
away = game.away_team.abbrev
home_score = game.score.home
away_score = game.score.away
```

### Pattern 4: String Comparisons → Enum/Properties

```python
# OLD - manual string comparison
if game['gameState'] == 'LIVE' or game['gameState'] == 'CRIT':
    # handle live game

# NEW - property handles all cases
if game.is_live:
    # handle live game

# Or use enum for specific checks
from nhl_api.models import GameState
if game.state == GameState.LIVE:
    # specific state check
```

### Pattern 5: Manual Loops → Helper Methods

```python
# OLD - manual search
target_team = None
for team in standings_data['standings']:
    if team['teamAbbrev']['default'] == 'BOS':
        target_team = team
        break

# NEW - built-in helper
target_team = standings.get_team_by_abbrev('BOS')
```

## Troubleshooting

### Issue: AttributeError on dict

**Error:** `AttributeError: 'dict' object has no attribute 'is_live'`

**Cause:** Using structured model properties on a raw dict.

**Fix:** Make sure you're calling the structured function:
```python
# Wrong
game = get_game_overview(game_id)  # Returns dict
if game.is_live:  # ERROR

# Right
game = client.get_game_structured(game_id)  # Returns Game
if game.is_live:  # Works!
```

### Issue: TypeError 'not subscriptable'

**Error:** `TypeError: 'Game' object is not subscriptable`

**Cause:** Using dict syntax on a structured object.

**Fix:** Use object properties instead:
```python
# Wrong
game = client.get_game_structured(game_id)
team = game['homeTeam']  # ERROR

# Right
game = client.get_game_structured(game_id)
team = game.home_team  # Works!
```

### Issue: Property without parentheses

**Error:** Calling property as method: `game.is_live()`

**Fix:** Properties don't use parentheses:
```python
# Wrong
if game.is_live():  # ERROR - not a method

# Right
if game.is_live:  # Works - it's a property
```

### Issue: Timezone-aware datetime comparison

**Error:** `TypeError: can't compare offset-naive and offset-aware datetimes`

**Cause:** Comparing `game.game_date` (timezone-aware) with naive datetime.

**Fix:** Use timezone-aware datetime:
```python
from datetime import datetime, timezone

# Wrong
if game.game_date > datetime.now():  # ERROR

# Right
if game.game_date > datetime.now(timezone.utc):  # Works
```

## Testing After Migration

### 1. Syntax Check
```bash
python3 -m py_compile src/path/to/file.py
```

### 2. Import Check
```bash
cd src && python3 -c "from boards import your_module; print('OK')"
```

### 3. Run in Emulated Mode
```bash
uv run src/main.py --emulated --led-brightness=90 --led-rows=64 --led-cols=128 --loglevel="debug"
```

### 4. Check for Errors
Look for AttributeError, TypeError, or other exceptions related to your changes.

## Migration Checklist

Use this for each file you migrate:

```markdown
## Migrating: [filename]

- [ ] Identify API function calls being used
- [ ] Check if structured versions exist (see NHL_API.md)
- [ ] Update imports (client, models)
- [ ] Replace function calls with structured versions
- [ ] Replace dict access with object properties
- [ ] Replace status method calls with object properties
- [ ] Update type hints if applicable
- [ ] Run syntax check
- [ ] Test in emulated mode or on device
- [ ] Check logs for errors
- [ ] Commit changes

### Notes:
[Document any issues or questions]
```

## Best Practices

### DO ✅

- Use structured functions for all new code
- Add type hints: `def render(self, game: Game) -> None:`
- Use built-in properties: `game.is_live`, `game.is_final`
- Migrate one module at a time
- Test thoroughly after each migration
- Commit after successful migration

### DON'T ❌

- Don't migrate everything at once (too risky)
- Don't use dict access on structured objects: `game['homeTeam']`
- Don't call properties as methods: `game.is_live()`
- Don't mix old and new patterns in the same function (confusing)
- Don't skip testing

## Type Hints Example

With structured models, you get full type checking:

```python
from nhl_api.nhl_client import client
from nhl_api.models import Game, Standings, Player
from datetime import date
from typing import List, Optional

def get_live_games(game_date: date) -> List[Game]:
    """Get all live games for a specific date."""
    games: List[Game] = client.get_games_structured(game_date)
    return [game for game in games if game.is_live]

def find_division_leader(standings: Standings, division: str) -> Optional[TeamStanding]:
    """Find the division leader for a given division."""
    for team in standings.eastern.teams + standings.western.teams:
        if team.team.division_name == division and team.division_sequence == 1:
            return team
    return None

def format_game_summary(game: Game) -> str:
    """Format a game as a string."""
    return f"{game.away_team.abbrev} {game.score.away} @ {game.home_team.abbrev} {game.score.home}"
```

Enable type checking with mypy:
```bash
mypy src/your_module.py
```

## FAQ

**Q: Do I have to migrate all my code?**
A: No. Both APIs work simultaneously. Migrate gradually or only migrate new code.

**Q: What if I need raw dict data?**
A: Legacy functions still work. Use `get_score_details()`, `get_game_overview()`, etc.

**Q: Can I convert objects back to dicts?**
A: Yes, but rarely needed:
```python
import dataclasses
game_dict = dataclasses.asdict(game_obj)
```

**Q: What about performance?**
A: Model parsing has minimal overhead (~1ms). Caching, network, and rendering are the bottlenecks, not model instantiation.

**Q: Will structured functions always be available?**
A: Yes. Eventually the `_structured` suffix will be removed and they'll become the standard functions, but the models will remain.

## See Also

- [NHL_API.md](./NHL_API.md) - Complete API reference with all models and functions
- [../TODO.md](../TODO.md) - Current migration status and roadmap
- `src/nhl_api/models.py` - Full model definitions
- `src/nhl_api/nhl_client.py` - API client implementation
