#!/usr/bin/env python3
"""
Test script for penalty.py renderer
Run with: uv run tests/test_penalty_renderer.py --emulated --led-rows=32 --led-cols=64
"""

import sys
import logging
import argparse
from pathlib import Path
from threading import Event
from unittest.mock import Mock

# Add src to path (go up one directory from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import driver

# Parse arguments first to determine driver mode
def parse_args():
    parser = argparse.ArgumentParser(description="Test the penalty renderer with various configurations")

    # LED Matrix options (matching main.py)
    parser.add_argument("--led-rows", action="store", help="Display rows. 16 for 16x32, 32 for 32x32. (Default: 32)",
                        default=32, type=int)
    parser.add_argument("--led-cols", action="store", help="Panel columns. Typically 32 or 64. (Default: 64)",
                        default=64, type=int)
    parser.add_argument("--led-chain", action="store", help="Daisy-chained boards. (Default: 1)", default=1, type=int)
    parser.add_argument("--led-parallel", action="store",
                        help="For Plus-models or RPi2: parallel chains. 1..3. (Default: 1)", default=1, type=int)
    parser.add_argument("--led-pwm-bits", action="store", help="Bits used for PWM. Range 1..11. (Default: 11)",
                        default=11, type=int)
    parser.add_argument("--led-brightness", action="store", help="Sets brightness level. Range: 1..100. (Default: 100)",
                        default=100, type=int)
    parser.add_argument("--led-gpio-mapping", help="Hardware Mapping: regular, adafruit-hat, adafruit-hat-pwm",
                        choices=['regular', 'adafruit-hat', 'adafruit-hat-pwm'], type=str)
    parser.add_argument("--led-scan-mode", action="store",
                        help="Progressive or interlaced scan. 0 = Progressive, 1 = Interlaced. (Default: 1)", default=1,
                        choices=range(2), type=int)
    parser.add_argument("--led-pwm-lsb-nanoseconds", action="store",
                        help="Base time-unit for the on-time in the lowest significant bit in nanoseconds. (Default: 130)",
                        default=130, type=int)
    parser.add_argument("--led-pwm-dither-bits", action="store",
                        help="Time dithering of lower bits (Default: 0)",
                        default=0, type=int)
    parser.add_argument("--led-show-refresh", action="store_true",
                        help="Shows the current refresh rate of the LED panel.")
    parser.add_argument("--led-slowdown-gpio", action="store",
                        help="Slow down writing to GPIO. Range: 0..4. (Default: 1)", choices=range(5), type=int)
    parser.add_argument("--led-no-hardware-pulse", action="store", help="Don't use hardware pin-pulse generation.")
    parser.add_argument("--led-rgb-sequence", action="store",
                        help="Switch if your matrix has led colors swapped. (Default: RGB)", default="RGB", type=str)
    parser.add_argument("--led-pixel-mapper", action="store", help="Apply pixel mappers. e.g \"Rotate:90\"", default="",
                        type=str)
    parser.add_argument("--led-row-addr-type", action="store",
                        help="0 = default; 1 = AB-addressed panels; 2 = direct row select; 3 = ABC-addressed panels",
                        default=0, type=int, choices=[0, 1, 2, 3, 4, 5])
    parser.add_argument("--led-multiplexing", action="store",
                        help="Multiplexing type: 0 = direct; 1 = strip; 2 = checker; 3 = spiral",
                        default=0, type=int)
    parser.add_argument("--led-panel-type", action="store", help="Needed to initialize special panels. Supported: 'FM6126A'",
                        default="", type=str)
    parser.add_argument("--led-limit-refresh", action="store",
                        help="Limit refresh rate to this frequency in Hz. 0=no limit. Default: 0", default=0, type=int)
    parser.add_argument("--emulated", action="store_true", help="Run in software emulation mode.")

    # Custom test options
    parser.add_argument("--team", action="store", help="Team abbreviation (e.g., COL, BOS, TOR). (Default: COL)",
                        default="COL", type=str)
    parser.add_argument("--team-id", action="store", help="Team ID number (Default: same as team abbrev)",
                        default=None, type=str)
    parser.add_argument("--player-number", action="store", help="Player jersey number. (Default: 29)",
                        default=29, type=int)
    parser.add_argument("--player-last", action="store", help="Player last name. (Default: MacKinnon)",
                        default="MacKinnon", type=str)
    parser.add_argument("--period-time", action="store", help="Time in period. (Default: 12:34)",
                        default="12:34", type=str)
    parser.add_argument("--penalty-minutes", action="store", help="Penalty duration in minutes. (Default: 2)",
                        default=2, type=int)
    parser.add_argument("--severity", action="store", help="Penalty severity (MINOR, MAJOR, MISCONDUCT). (Default: MINOR)",
                        default="MINOR", type=str, choices=["MINOR", "MAJOR", "MISCONDUCT", "MATCH"])

    # Test flags (for ScoreboardConfig compatibility)
    parser.add_argument("--testScChampions", action="store", help="Test stanley cup champions board",
                        default=None, type=int)
    parser.add_argument("--test-goal-animation", action="store", help="Test goal animation flag",
                        default=None, type=bool)
    parser.add_argument("--testing-mode", action="store", help="Testing mode flag", default=None)
    parser.add_argument("--loglevel", action="store", help="Log level (DEBUG, INFO, WARN, ERROR, CRITICAL)",
                        default="INFO", type=str)
    parser.add_argument("--logtofile", action="store_true", help="Log to file", default=False)

    return parser.parse_args()

# Parse args before imports that depend on driver mode
commandArgs = parse_args()

# Set up logging
log_level = getattr(logging, commandArgs.loglevel.upper(), logging.INFO)
logging.basicConfig(level=log_level)

# Set driver mode based on --emulated flag (matching main.py pattern)
if commandArgs.emulated:
    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
    driver.mode = driver.DriverMode.SOFTWARE_EMULATION
else:
    try:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions  # type: ignore
        driver.mode = driver.DriverMode.HARDWARE
    except ImportError:
        from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
        driver.mode = driver.DriverMode.SOFTWARE_EMULATION
        print("Warning: Hardware library not found, falling back to emulation mode")

# Now import modules that depend on driver mode
from renderer.penalty import PenaltyRenderer
from renderer.matrix import Matrix
from data.scoreboard_config import ScoreboardConfig
from utils import led_matrix_options
from nhl_api.info import TeamDetails, TeamInfo

# NHL Team ID mapping (abbreviation -> team ID)
TEAM_IDS = {
    "NJD": 1, "NYI": 2, "NYR": 3, "PHI": 4, "PIT": 5, "BOS": 6, "BUF": 7, "MTL": 8,
    "OTT": 9, "TOR": 10, "CAR": 12, "FLA": 13, "TBL": 14, "WSH": 15, "CHI": 16,
    "DET": 17, "NSH": 18, "STL": 19, "CGY": 20, "COL": 21, "EDM": 22, "VAN": 23,
    "ANA": 24, "DAL": 25, "LAK": 26, "SJS": 28, "CBJ": 29, "MIN": 30, "WPG": 52,
    "ARI": 53, "VGK": 54, "SEA": 55, "UTA": 59
}

def create_mock_penalty(args, team_id):
    """Create a mock penalty with realistic data from command-line args"""
    penalty = Mock()
    penalty.team_id = team_id
    penalty.periodTime = args.period_time
    penalty.penaltyMinutes = args.penalty_minutes
    penalty.severity = args.severity
    penalty.player = {
        "sweaterNumber": args.player_number,
        "lastName": {"default": args.player_last}
    }
    return penalty

def create_mock_team(args, team_id):
    """Create a mock team with penalties"""
    team = Mock()
    team.id = team_id
    team.abbrev = args.team.upper()
    team.penalties = [create_mock_penalty(args, team_id)]
    return team

def create_mock_team_info(args, team_id):
    """Create a TeamInfo object for the penalty team"""
    # Create TeamDetails
    team_details = TeamDetails(
        id=team_id,
        name=f"{args.team.upper()} Team",
        abbrev=args.team.upper()
    )

    # Create TeamInfo with empty standings (not used for penalty display)
    team_info = TeamInfo(standings=Mock(), team_details=team_details)
    return team_info

def main():
    cols = commandArgs.led_cols
    rows = commandArgs.led_rows

    print("Testing Penalty Renderer")
    print("=" * 60)
    print(f"Display size: {cols}x{rows}")
    print(f"Driver mode: {driver.mode.name}")
    print(f"Team: {commandArgs.team}")
    print(f"Player: #{commandArgs.player_number} {commandArgs.player_last}")
    print(f"Penalty: {commandArgs.penalty_minutes} min {commandArgs.severity} @ {commandArgs.period_time}")
    print("=" * 60)

    # Get team ID - use provided team_id, or look up from abbreviation
    if commandArgs.team_id:
        team_id = int(commandArgs.team_id)
    elif commandArgs.team.upper() in TEAM_IDS:
        team_id = TEAM_IDS[commandArgs.team.upper()]
    else:
        print(f"Warning: Unknown team '{commandArgs.team}', defaulting to team ID 21 (COL)")
        team_id = 21

    # Create mock data object
    data = Mock()

    # Load real configuration
    try:
        config = ScoreboardConfig("config", commandArgs, (cols, rows))
        data.config = config
        print(f"✓ Loaded configuration for {cols}x{rows} display")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        import traceback
        traceback.print_exc()
        return

    # Create a mock team with penalty data
    penalty_team = create_mock_team(commandArgs, team_id)
    print(f"✓ Created mock team: {penalty_team.abbrev}")
    print(f"  - Penalty on #{penalty_team.penalties[-1].player['sweaterNumber']} "
          f"{penalty_team.penalties[-1].player['lastName']['default']}")

    # Create teams_info dictionary with TeamInfo for the penalty team
    team_info = create_mock_team_info(commandArgs, team_id)
    data.teams_info = {team_id: team_info}
    print(f"✓ Created team info for team ID {team_id}")

    # Create matrix for rendering using led_matrix_options (matching main.py)
    try:
        matrixOptions = led_matrix_options(commandArgs)
        matrixOptions.drop_privileges = False

        if driver.is_emulated():
            # Set up window title for emulator
            matrixOptions.emulator_title = f"Penalty Renderer Test - {commandArgs.team}"
            matrixOptions.icon_path = (Path(__file__).parent.parent / "assets" / "images" / "favicon.ico").resolve()

        matrix = Matrix(RGBMatrix(options=matrixOptions))
        print(f"✓ Created matrix ({matrix.width}x{matrix.height})")
    except Exception as e:
        print(f"✗ Failed to create matrix: {e}")
        import traceback
        traceback.print_exc()
        return

    # Create sleep event
    sleepEvent = Event()
    sleepEvent.wait(3)

    # Create and render penalty
    try:
        print("\n" + "=" * 60)
        print("Rendering penalty animation...")
        print("=" * 60)

        penalty_renderer = PenaltyRenderer(data, matrix, sleepEvent, penalty_team)

        # Render the penalty animation
        penalty_renderer.render()

        print("\n✓ Penalty animation rendered successfully!")
        print("\nCheck the emulator window to see the output.")
        print("The display shows:")
        print("  - Penalty time")
        print("  - Team abbreviation with team colors")
        print("  - Player number and last name")
        print("  - Penalty duration and severity")

    except Exception as e:
        print(f"✗ Failed to render penalty: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
