import logging
import time
from datetime import datetime, timedelta
import copy

# Configure logger
logger = logging.getLogger("GameSimulator")

class GameSimulator:
    def __init__(self, full_data, speed_multiplier=1.0):
        """
        Initialize the simulator with the full game data (play-by-play).
        
        Args:
            full_data (dict): The complete JSON response from the gamecenter play-by-play endpoint.
            speed_multiplier (float): Speed factor for simulation (1.0 = real time).
        """
        self.full_data = full_data
        self.speed_multiplier = speed_multiplier
        
        self.plays = full_data.get("plays", [])
        logger.info(f"Simulator loaded {len(self.plays)} plays.")
        
        self.current_play_index = 0
        
        # Game State
        self.start_wall_time = time.time()
        
        # Determine Simulation Start Time (Game Start)
        try:
            start_str = self.full_data.get("startTimeUTC")
            if start_str.endswith("Z"):
                start_str = start_str[:-1]
            self.game_start_dt = datetime.fromisoformat(start_str)
        except Exception as e:
            logger.error(f"Could not parse startTimeUTC: {e}. Defaulting to now.")
            self.game_start_dt = datetime.now()
            
        self.simulated_time = self.game_start_dt
        
        # Pre-calculate timestamps for all plays to avoid doing it in tick
        self._calculate_play_timestamps()

        self.processed_plays = []
        
        # Base structures to return
        self.base_overview = copy.deepcopy(full_data)
        self.base_overview["plays"] = []
        self.base_overview["linescore"] = {"byPeriod": [], "totals": {"away": 0, "home": 0}}
        self.base_overview["gameState"] = "LIVE"
        
        # Initial Clock
        self.base_overview["clock"] = {"timeRemaining": "20:00", "secondsRemaining": 1200, "running": True, "inIntermission": False}
        self.base_overview["periodDescriptor"] = {"number": 1, "periodType": "REG", "maxRegulationPeriods": 3}
            
        # Set initial team scores to 0
        if "awayTeam" in self.base_overview:
            self.base_overview["awayTeam"]["score"] = 0
            self.base_overview["awayTeam"]["sog"] = 0
        if "homeTeam" in self.base_overview:
            self.base_overview["homeTeam"]["score"] = 0
            self.base_overview["homeTeam"]["sog"] = 0
            
        logger.info(f"Simulator initialized for Game ID {self.full_data.get('id')}")
        logger.info(f"Simulation Start Time: {self.simulated_time}")

    def _calculate_play_timestamps(self):
        """
        Iterate through plays and assign an absolute simulated timestamp to each.
        Assumption:
        Period 1: Starts at game_start_dt
        Period 2: Starts at game_start_dt + 20m play + 18m intermission
        Period 3: ...
        """
        # Base offsets in minutes from game start
        # P1: 0
        # P2: 20 (P1) + 18 (Int) = 38
        # P3: 38 + 20 (P2) + 18 (Int) = 76
        # OT: 76 + 20 (P3) + 15 (Int) = 111 (approx)
        
        period_offsets = {
            1: 0,
            2: 38,
            3: 76,
            4: 114, # OT
            5: 130  # SO?
        }
        
        for play in self.plays:
            period = play.get("periodDescriptor", {}).get("number", 1)
            time_in_period = play.get("timeInPeriod", "00:00")
            m, s = map(int, time_in_period.split(":"))
            total_seconds_in_period = m * 60 + s
            
            offset_minutes = period_offsets.get(period, (period-1)*38) 
            
            # Calculate absolute timestamp of this play
            play_dt = self.game_start_dt + timedelta(minutes=offset_minutes, seconds=total_seconds_in_period)
            play["_simulated_timestamp"] = play_dt

    def _parse_time_str(self, time_str):
        """Convert MM:SS to seconds."""
        try:
            m, s = map(int, time_str.split(":"))
            return m * 60 + s
        except ValueError:
            return 0

    def get_current_time(self):
        """Return the current simulated datetime."""
        return self.simulated_time

    def tick(self):
        """
        Advance the simulation state based on wall clock time.
        """
        now = time.time()
        delta_seconds = (now - self.start_wall_time) * self.speed_multiplier
        self.start_wall_time = now
        
        # Advance simulated time
        self.simulated_time += timedelta(seconds=delta_seconds)

    def get_current_overview(self):
        """
        Returns the game overview dictionary representing the current state.
        """
        self.tick()
        
        # Process available plays based on time
        while self.current_play_index < len(self.plays):
            next_play = self.plays[self.current_play_index]
            play_time = next_play.get("_simulated_timestamp")
            
            # If we haven't reached this play's time yet, stop processing
            if play_time and self.simulated_time < play_time:
                break
                
            # Emit Play
            self.processed_plays.append(next_play)
            self.current_play_index += 1
            
            # Update Clock/Period from Play
            if "timeRemaining" in next_play:
                self.base_overview["clock"]["timeRemaining"] = next_play["timeRemaining"]
                self.base_overview["clock"]["secondsRemaining"] = self._parse_time_str(next_play["timeRemaining"])
            
            if "periodDescriptor" in next_play:
                self.base_overview["periodDescriptor"] = next_play["periodDescriptor"]

            # Update Score/Stats if it's a Goal or Shot
            full_update = False
            if "details" in next_play:
                details = next_play["details"]
                
                # Update Scores
                if "awayScore" in details:
                    self.base_overview["awayTeam"]["score"] = details["awayScore"]
                if "homeScore" in details:
                    self.base_overview["homeTeam"]["score"] = details["homeScore"]
                
                # Update SOG (Shots on Goal)
                # API V1 usually provides awaySOG and homeSOG in shot/goal events
                if "awaySOG" in details:
                    old_sog = self.base_overview["awayTeam"].get("sog", 0)
                    new_sog = details["awaySOG"]
                    if new_sog != old_sog:
                        self.base_overview["awayTeam"]["sog"] = new_sog
                        logger.info(f"SOG UPDATE: Away {new_sog}")

                if "homeSOG" in details:
                    old_sog = self.base_overview["homeTeam"].get("sog", 0)
                    new_sog = details["homeSOG"]
                    if new_sog != old_sog:
                        self.base_overview["homeTeam"]["sog"] = new_sog
                        logger.info(f"SOG UPDATE: Home {new_sog}")

            if next_play["typeDescKey"] == "goal":
                logger.info(f"GOAL! {self.base_overview['awayTeam']['score']}-{self.base_overview['homeTeam']['score']}")
            
        # Check if Game Over (all plays processed AND sufficient time passed?)
        if self.current_play_index >= len(self.plays):
            last_play = self.plays[-1] if self.plays else None
            if last_play:
                end_time = last_play.get("_simulated_timestamp")
                # Wait 2 minutes after last play before ending
                if end_time and self.simulated_time > end_time + timedelta(minutes=2):
                    self.base_overview["gameState"] = "FINAL"
                    self.base_overview["clock"] = {"timeRemaining": "00:00", "secondsRemaining": 0, "running": False, "inIntermission": False}

        self.base_overview["plays"] = self.processed_plays
        return self.base_overview

    def get_game_basic_info(self):
        """
        Returns the basic game info for the schedule list.
        """
        basic = {
            "id": self.full_data["id"],
            "season": self.full_data.get("season"),
            "gameState": self.base_overview.get("gameState", "LIVE"),
            "startTimeUTC": self.full_data.get("startTimeUTC", datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')),
            "gameDate": self.full_data.get("gameDate"),
            "awayTeam": self.full_data["awayTeam"],
            "homeTeam": self.full_data["homeTeam"]
        }
        
        if "score" not in basic["awayTeam"]:
            basic["awayTeam"]["score"] = self.base_overview["awayTeam"]["score"]
        if "score" not in basic["homeTeam"]:
            basic["homeTeam"]["score"] = self.base_overview["homeTeam"]["score"]
            
        # Polyfill legacy "name" field if missing, based on "commonName"
        # The V1 API uses "commonName": {"default": "Jets"}, but old code expects "name": {"default": "Jets"}
        if "name" not in basic["awayTeam"] and "commonName" in basic["awayTeam"]:
             basic["awayTeam"]["name"] = basic["awayTeam"]["commonName"]
             
        if "name" not in basic["homeTeam"] and "commonName" in basic["homeTeam"]:
             basic["homeTeam"]["name"] = basic["homeTeam"]["commonName"]
             
        return basic
