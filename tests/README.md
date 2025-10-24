# Test Scripts

This directory contains test scripts for manually testing specific components of the NHL LED Scoreboard.

## Available Tests

### test_goal_renderer.py

Tests the goal animation renderer that displays goal details on the LED matrix.

**Usage:**
```bash
# Basic test with emulated 64x32 display
uv run tests/test_goal_renderer.py --emulated

# Test with 128x64 display
uv run tests/test_goal_renderer.py --emulated --led-rows=64 --led-cols=128

# Test with custom team and player
uv run tests/test_goal_renderer.py --emulated --team=BOS --player-number=63 --player-first=Brad --player-last=Marchand

# Test unassisted goal
uv run tests/test_goal_renderer.py --emulated --no-assists

# Test with debug logging
uv run tests/test_goal_renderer.py --emulated --loglevel=DEBUG
```

**Options:**
- All standard LED matrix options (--led-rows, --led-cols, --led-brightness, etc.)
- `--team` - Team abbreviation (COL, BOS, TOR, etc.)
- `--player-number` - Jersey number
- `--player-first` - Player first name
- `--player-last` - Player last name
- `--period` - Period number
- `--period-time` - Time in period (e.g., "12:34")
- `--no-assists` - Test unassisted goal
- `--loglevel` - Log level (DEBUG, INFO, WARN, ERROR)

**Supported Teams:**
NJD, NYI, NYR, PHI, PIT, BOS, BUF, MTL, OTT, TOR, CAR, FLA, TBL, WSH, CHI, DET, NSH, STL, CGY, COL, EDM, VAN, ANA, DAL, LAK, SJS, CBJ, MIN, WPG, ARI, VGK, SEA, UTA

---

### test_penalty_renderer.py

Tests the penalty renderer that displays penalty details on the LED matrix.

**Usage:**
```bash
# Basic test with emulated 64x32 display
uv run tests/test_penalty_renderer.py --emulated

# Test with 128x64 display
uv run tests/test_penalty_renderer.py --emulated --led-rows=64 --led-cols=128

# Test with custom team and player
uv run tests/test_penalty_renderer.py --emulated --team=BOS --player-number=63 --player-last=Marchand

# Test major penalty
uv run tests/test_penalty_renderer.py --emulated --severity=MAJOR --penalty-minutes=5

# Test with different teams
uv run tests/test_penalty_renderer.py --emulated --team=TOR --player-number=34 --player-last=Matthews

# Test with debug logging
uv run tests/test_penalty_renderer.py --emulated --loglevel=DEBUG
```

**Options:**
- All standard LED matrix options (--led-rows, --led-cols, --led-brightness, etc.)
- `--team` - Team abbreviation (COL, BOS, TOR, etc.)
- `--player-number` - Jersey number (default: 29)
- `--player-last` - Player last name (default: MacKinnon)
- `--period-time` - Time in period (e.g., "12:34")
- `--penalty-minutes` - Penalty duration in minutes (default: 2)
- `--severity` - Penalty severity: MINOR, MAJOR, MISCONDUCT, MATCH (default: MINOR)
- `--loglevel` - Log level (DEBUG, INFO, WARN, ERROR)

**Supported Teams:**
NJD, NYI, NYR, PHI, PIT, BOS, BUF, MTL, OTT, TOR, CAR, FLA, TBL, WSH, CHI, DET, NSH, STL, CGY, COL, EDM, VAN, ANA, DAL, LAK, SJS, CBJ, MIN, WPG, ARI, VGK, SEA, UTA

---

## Adding New Tests

When creating new test scripts:
1. Place them in this `tests/` directory
2. Use the same command-line argument pattern as the main application
3. Document usage in this README
4. Follow the naming convention: `test_<component>_<description>.py`
