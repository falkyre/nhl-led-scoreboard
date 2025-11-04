# TODO: NHL LED Scoreboard

## Completed

### ✅ NHL API Refactor (Phase 1 & 2)
**Status:** Complete - Ready for PR to beta

**Completed work:**
- [x] Migrated from `requests` to `httpx` with retry logic and exponential backoff
- [x] Centralized API calls in `NHLAPIClient` with error handling and timeouts
- [x] Migrated game state checks from `Status` class to structured `Game` model
- [x] Implemented inheritance pattern for `Scoreboard` and `GameSummaryBoard`
- [x] Removed dependency on third-party `nhl-api-py` package (now using native NHL API calls)
- [x] Dead code cleanup: removed 151+ lines of unused code
- [x] Deleted `src/nhl_api/object.py` (MultiLevelObject no longer needed)

**Result:** API layer is modernized and robust. Zero breaking changes.

**Next step:** Data structure migration (separate branch/PR)

---

## High Priority

### Migrate to Structured NHL API Models (Phase 3 - Data Layer)

**Why:** The new structured dataclass models (`src/nhl_api/models.py`) provide better type safety, easier maintenance, and isolation from NHL API changes. Currently, most code uses unstructured dictionaries.

**Current state:**
- API layer uses httpx and NHLAPIClient ✅ DONE
- Structured models exist (`_structured` functions) but are not yet consumed by application
- `src/data/data.py` fetches with new API but stores raw dicts
- Boards still consume dictionaries instead of typed models

**Benefits:**
- ✅ Type safety and IDE autocomplete
- ✅ Single place to update when NHL changes their API
- ✅ Self-documenting code
- ✅ Helper methods and properties
- ✅ Backwards compatibility layer

**Documentation:**
- API Reference: See [docs/NHL_API.md](docs/NHL_API.md)
- Migration Guide: See [docs/MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md)

**Areas to Migrate:**
1. **High Impact (do first):**
   - [ ] `src/data/data.py` - Switch from storing dicts to storing structured models
   - [ ] `src/renderer/main.py` - Accept typed models instead of dicts
   - [ ] `src/boards/scoreboard.py` - Already partially migrated, complete the transition
   - [ ] `src/boards/` - Update remaining boards that consume game/team data

2. **Medium Impact:**
   - [ ] `src/boards/standings.py` - Use `Standings` model
   - [ ] `src/boards/team_summary.py` - Use `Team` model
   - [ ] `src/boards/player_stats.py` - Use `Player` model

3. **Cleanup (after migration):**
   - [ ] Rename `_structured` functions to standard names (remove legacy dict-returning versions)
   - [ ] Deprecate/remove legacy wrappers in `src/nhl_api/info.py`
   - [ ] Simplify `src/nhl_api/game.py` using `Game` model

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
