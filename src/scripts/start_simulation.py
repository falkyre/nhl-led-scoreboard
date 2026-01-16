import sys
import os
import json
import logging
import httpx
import argparse
from datetime import datetime

# Add the src directory to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.append(src_dir)

from scripts.game_simulator import GameSimulator
import nhl_api.data
import nhl_api.nhl_client
import sys
import os
import json
import logging
import httpx
import argparse
from datetime import datetime

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SimulatorLauncher")

def fetch_game_id(team_abbr, date_str):
    """
    Fetches the schedule for the given team and date to find the Game ID.
    """
    url = f"https://api-web.nhle.com/v1/club-schedule/{team_abbr}/week/{date_str}"
    logger.info(f"Fetching schedule from: {url}")
    
    try:
        response = httpx.get(url)
        response.raise_for_status()
        data = response.json()
        
        target_date = date_str
        
        for game in data.get("games", []):
            if game.get("gameDate") == target_date:
                logger.info(f"Found Game ID: {game['id']} for {team_abbr} on {target_date}")
                return game["id"]
        
        logger.error(f"No game found for {team_abbr} on {target_date}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching schedule: {e}")
        return None

def fetch_play_by_play(game_id):
    """
    Fetches the play-by-play data for the given game ID.
    """
    url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    logger.info(f"Fetching play-by-play from: {url}")
    
    try:
        response = httpx.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching play-by-play: {e}")
        return None


# Valid Teams List from logo_editor.py
TEAMS = [
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", 
    "WSH", "WPG"
]

def run_simulation():
    print("--- NHL Game Simulator ---")
    
    # Parse arguments intended for the simulator
    parser = argparse.ArgumentParser(description="NHL Game Simulator", add_help=False)
    parser.add_argument("--team", type=str, help="Team Abbreviation (e.g. WPG)")
    parser.add_argument("--speed", type=float, default=1.0, help="Simulation Speed Multiplier (e.g. 2.0)")
    parser.add_argument("--stop-at-end", action="store_true", help="Stop the simulator when the game is finished")
    parser.add_argument("--date", type=str, help="Game Date (YYYY-MM-DD)")
    
    # Use parse_known_args to separate simulator args from scoreboard args
    args, remaining_argv = parser.parse_known_args()
    
    # Update sys.argv so main.py only sees the remaining arguments
    # We keep sys.argv[0] as the script name
    sys.argv = [sys.argv[0]] + remaining_argv
    
    if args.team:
        team = args.team.strip().upper()
    else:
        team = input("Enter Team Abbreviation (e.g. WPG): ").strip().upper()
    
    # Data Validation: Team
    if team not in TEAMS:
        print(f"Error: Invalid team abbreviation '{team}'. Must be one of: {', '.join(TEAMS)}")
        return

    if args.date:
        date_str = args.date.strip()
    else:
        date_str = input("Enter Game Date (YYYY-MM-DD): ").strip()

    # Data Validation: Date
    try:
        game_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        
        if game_date >= today:
            print(f"Error: Game date must be in the past. {date_str} is invalid.")
            return
            
    except ValueError:
        print(f"Error: Invalid date format. Please use YYYY-MM-DD.")
        return

    # 1. Get Game ID
    game_id = fetch_game_id(team, date_str)
    if not game_id:
        print("Could not find game. Exiting.")
        sys.exit(1)

    # 2. Get Play-by-Play
    pbp_data = fetch_play_by_play(game_id)
    if not pbp_data:
        print("Could not fetch game data. Exiting.")
        sys.exit(1)

    # 3. Initialize Simulator
    logger.info(f"Initializing simulator with speed x{args.speed}")
    simulator = GameSimulator(pbp_data, speed_multiplier=args.speed)

    # 4. Monkeypatch API and DateTime
    logger.info("Monkeypatching nhl_api.data and datetime...")
    
    def mocked_get_score_details(date_obj):
        logger.debug("Mocked get_score_details called")
        return {"games": [simulator.get_game_basic_info()]}

    def mocked_get_game_overview(g_id):
        logger.debug(f"Mocked get_game_overview called for {g_id}")
        overview = simulator.get_current_overview()
        
        if args.stop_at_end and overview.get("gameState") == "FINAL":
            logger.info("Game finished. Stopping simulation.")
            # Raising KeyboardInterrupt catches in main.run() and exits cleanly
            raise KeyboardInterrupt
            
        return overview

    # Apply API patches
    nhl_api.data.get_score_details = mocked_get_score_details
    nhl_api.data.get_game_overview = mocked_get_game_overview
    
    # DEEP PATCH: nhl_api.nhl_client.client
    # This ensures that even if get_game_overview is called via the client directly, it is mocked.
    nhl_api.nhl_client.client.get_score_details = mocked_get_score_details
    nhl_api.nhl_client.client.get_game_overview = mocked_get_game_overview
    
    # DateTime Mocking
    # We need to access the class *inside* the module src.data.data
    # Because src.data.data imports datetime as: "from datetime import date, datetime, timedelta"
    # We must patch the reference in that module.
    
    # Import the module to be patched
    import data.data
    
    # Define Mock Classes
    # We inherit from the real classes to ensure isinstance checks pass and methods like strptime work
    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # Return simulated time. 
            # Note: tz argument is ignored for simplicity here as our simulator uses a naive/UTC-ish object
            return simulator.get_current_time()

        @classmethod
        def today(cls):
            return simulator.get_current_time()
            
    class MockDate(datetime):
        @classmethod
        def today(cls):
            return simulator.get_current_time().date()

    # Apply DateTime Patches
    data.data.datetime = MockDatetime
    data.data.date = MockDate

    # 5. Start Main Application
    logger.info(f"Starting Scoreboard... Simulated Time: {simulator.get_current_time()}")
    
    import main
    try:
        main.run()
    except KeyboardInterrupt:
        print("\nSimulation stopped.")

if __name__ == "__main__":
    run_simulation()
