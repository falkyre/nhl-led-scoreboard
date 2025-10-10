# TODO: NHL LED Scoreboard

## High Priority

### Migrate to Structured NHL API Models

**Why:** The new structured dataclass models (`src/nhl_api/models.py`) provide better type safety, easier maintenance, and isolation from NHL API changes. Currently, most code uses unstructured dictionaries.

**Benefits:**
- ✅ Type safety and IDE autocomplete
- ✅ Single place to update when NHL changes their API
- ✅ Self-documenting code
- ✅ Helper methods and properties
- ✅ Backwards compatibility layer

**Migration Guide:** See `docs/NHL_API_MODELS.md`

**Areas to Migrate:**
1. **High Impact (do first):**
   - [ ] `src/boards/` - All board classes that consume game/team data
   - [ ] `src/renderer/main.py` - Main renderer that displays games
   - [ ] `src/data/data.py` - Central data management class

2. **Medium Impact:**
   - [ ] `src/boards/standings.py` - Use `Standings` model
   - [ ] `src/boards/team_summary.py` - Use `Team` model
   - [ ] `src/boards/scoreboard.py` - Use `Game` model
   - [ ] `src/boards/player_stats.py` - Use `Player` model

3. **Low Impact (optional):**
   - [ ] `src/nhl_api/info.py` - Consider deprecating in favor of models
   - [ ] `src/nhl_api/game.py` - Simplify using `Game` model

**Migration Pattern:**
```python
# Before (unstructured dict)
from nhl_api.data import get_score_details
data = get_score_details(date.today())
for game in data['games']:
    home = game['homeTeam']['abbrev']
    score = game['homeTeam']['score']

# After (structured model)
from nhl_api.nhl_client import client
games = client.get_games_structured(date.today())
for game in games:
    home = game.home_team.abbrev
    score = game.score.home
```

**Notes:**
- Can be done gradually - both approaches work simultaneously
- No breaking changes - structured models are additive
- Focus on one module at a time
- Add type hints as you migrate: `def render(self, game: Game) -> None:`

---

## Other Tasks

(Add other TODO items below as needed)
