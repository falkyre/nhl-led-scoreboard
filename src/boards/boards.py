"""
A Board is simply a display object with specific parameters made to be shown on screen.
Board modules can be added by placing them in the src/boards/plugins/ or src/boards/builtins/ directories.
"""
import importlib
import inspect
import json
import logging
import sys
from pathlib import Path

from boards.christmas import Christmas
from boards.clock import Clock
from boards.ovi_tracker import OviTrackerRenderer
from boards.pbdisplay import pbDisplay
from boards.player_stats import PlayerStatsRenderer
from boards.scoreticker import Scoreticker
from boards.screensaver import screenSaver
from boards.seriesticker import Seriesticker
from boards.standings import Standings
from boards.stats_leaders import StatsLeaders
from boards.team_summary import TeamSummary
from boards.wxAlert import wxAlert
from boards.wxForecast import wxForecast
from boards.wxWeather import wxWeather

from .base_board import BoardBase

debug = logging.getLogger("scoreboard")
class Boards:
    def __init__(self):
        self._boards = {}
        self._board_instances = {}  # Cache for board instances
        self._load_boards()

    def _load_boards(self):
        """
        Dynamically load board modules from both plugins and builtins directories.
        
        Scans src/boards/plugins/ for third-party/user board modules and src/boards/builtins/
        for system builtin board modules. Both follow the same structure and loading mechanism.
        Each board directory should contain an __init__.py and a board.py with the board class.
        """
        # Load from plugins directory (third-party/user board modules)
        self._load_boards_from_directory('plugins', 'plugin')

        # Load from builtins directory (system board modules)
        self._load_boards_from_directory('builtins', 'builtin')

    def _load_boards_from_directory(self, directory_name: str, board_type: str):
        """
        Load boards from a specific directory.
        
        Args:
            directory_name: Name of the directory ('plugins' or 'builtins')
            board_type: Type description for logging ('plugin' or 'builtin')
        """
        boards_dir = Path(__file__).parent / directory_name

        if not boards_dir.exists():
            debug.info(f"No {directory_name} directory found, skipping {board_type} loading")
            return

        # Scan for board directories
        for board_dir in boards_dir.iterdir():
            if not board_dir.is_dir() or board_dir.name.startswith('_'):
                continue

            board_name = board_dir.name
            try:
                self._load_single_board(board_name, board_dir, directory_name, board_type)
            except Exception as e:
                debug.warning(f"Failed to load {board_type} '{board_name}': {e}")

    def _load_single_board(self, board_name: str, board_dir: Path, directory_name: str, board_type: str):
        """
        Load a single board from its directory using metadata-driven approach.

        Args:
            board_name: Name of the board (directory name)
            board_dir: Path to the board directory
            directory_name: Parent directory name ('plugins' or 'builtins')
            board_type: Type description for logging ('plugin' or 'builtin')
        """
        # 1. Load and validate plugin.json (REQUIRED)
        plugin_json = board_dir / 'plugin.json'
        if not plugin_json.exists():
            debug.warning(f"{board_type.capitalize()} '{board_name}' missing plugin.json, skipping")
            return

        try:
            with open(plugin_json) as f:
                metadata = json.load(f)
        except json.JSONDecodeError as e:
            debug.error(f"Invalid plugin.json in '{board_name}': {e}")
            return

        # 2. Check if enabled
        if not metadata.get("enabled", True):
            debug.info(f"{board_type.capitalize()} '{board_name}' is disabled")
            return

        # 3. Validate requirements
        if not self._validate_requirements(metadata.get("requirements", {}), board_name):
            debug.warning(f"{board_type.capitalize()} '{board_name}' requirements not met, skipping")
            return

        # 4. Load each board declared in metadata
        boards_list = metadata.get("boards", [])
        if not boards_list:
            debug.warning(f"{board_type.capitalize()} '{board_name}' declares no boards")
            return

        for board_config in boards_list:
            self._load_board_from_metadata(board_config, board_dir, directory_name, board_name, board_type)

    def _validate_requirements(self, requirements: dict, plugin_name: str) -> bool:
        """
        Validate plugin requirements before loading.

        Args:
            requirements: Dict with requirement specifications
            plugin_name: Name of the plugin being validated

        Returns:
            True if all requirements met, False otherwise.
        """
        # Check Python version
        if "python" in requirements:
            python_req = requirements["python"]
            current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            # Basic version check (simple string comparison for now)
            # TODO: Implement proper version comparison with packaging.version
            debug.debug(f"Plugin '{plugin_name}' requires Python {python_req}, current: {current_version}")

        # Check app version
        if "app_version" in requirements:
            # TODO: Compare against current app version when available
            debug.debug(f"Plugin '{plugin_name}' requires app version {requirements['app_version']}")

        # Check Python dependencies
        if "python_dependencies" in requirements:
            for dep in requirements["python_dependencies"]:
                # Extract package name (handle versions like "holidays>=0.35")
                pkg_name = dep.split('>=')[0].split('==')[0].split('<')[0].strip()
                try:
                    importlib.import_module(pkg_name)
                    debug.debug(f"Plugin '{plugin_name}' dependency '{pkg_name}' is available")
                except ImportError:
                    debug.error(f"Plugin '{plugin_name}' requires '{dep}' but it's not installed")
                    return False

        return True

    def _load_board_from_metadata(self, board_config: dict, board_dir: Path,
                                    directory_name: str, plugin_name: str, board_type: str):
        """
        Load a specific board using metadata configuration.

        Args:
            board_config: Dict with board metadata (id, class_name, module)
            board_dir: Path to plugin directory
            directory_name: 'plugins' or 'builtins'
            plugin_name: Name of the plugin
            board_type: Type description for logging ('plugin' or 'builtin')
        """
        board_id = board_config.get("id")
        class_name = board_config.get("class_name")
        module_name_short = board_config.get("module", "board")

        if not board_id or not class_name:
            debug.error(f"Board config missing 'id' or 'class_name' in {board_type} '{plugin_name}'")
            return

        # Import the module
        module_path = f'boards.{directory_name}.{plugin_name}.{module_name_short}'
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            debug.error(f"Failed to import {module_path}: {e}")
            return

        # Get the specific class by name
        if not hasattr(module, class_name):
            debug.error(f"Class '{class_name}' not found in {module_path}")
            return

        board_class = getattr(module, class_name)

        # Validate it's a BoardBase subclass
        if not (inspect.isclass(board_class) and
                issubclass(board_class, BoardBase) and
                board_class != BoardBase):
            debug.error(f"'{class_name}' is not a valid BoardBase subclass")
            return

        # Register the board
        self._boards[board_id] = board_class

        # Create dynamic method with caching
        def create_board_method(name, cls):
            def board_method(data, matrix, sleepEvent):
                if name not in self._board_instances:
                    self._board_instances[name] = cls(data, matrix, sleepEvent)
                    debug.info(f"Created new instance for board: {name}")
                return self._board_instances[name].render()
            return board_method

        setattr(self, board_id, create_board_method(board_id, board_class))

        debug.info(f"Loaded {board_type} board: {board_id} from '{plugin_name}' ({class_name})")

    def get_available_boards(self) -> dict:
        """
        Get information about all loaded board modules.
        
        Returns:
            Dict mapping board names to board classes
        """
        return self._boards.copy()

    def is_board_loaded(self, board_name: str) -> bool:
        """
        Check if a board module is loaded and available.

        Args:
            board_name: Name of the board to check

        Returns:
            True if board is loaded, False otherwise
        """
        return board_name in self._boards

    def _get_cached_board_instance(self, board_name: str, board_class, data, matrix, sleepEvent):
        """
        Get or create a cached instance of a legacy board.

        Args:
            board_name: Name of the board for caching
            board_class: Board class to instantiate
            data, matrix, sleepEvent: Board constructor arguments

        Returns:
            Cached board instance
        """
        if board_name not in self._board_instances:
            try:
                self._board_instances[board_name] = board_class(data, matrix, sleepEvent)
                debug.info(f"Created new instance for legacy board: {board_name}")
            except Exception:
                debug.error(f"Failed to load board: {board_name}. Board doesnt exist or typo in config.")
                return None
        else:
            debug.debug(f"Using cached instance for legacy board: {board_name}")
        return self._board_instances[board_name]

    def clear_board_cache(self, board_name: str = None):
        """
        Clear cached board instances and call cleanup.

        Args:
            board_name: Specific board to clear, or None to clear all
        """
        if board_name:
            if board_name in self._board_instances:
                board = self._board_instances[board_name]
                if hasattr(board, 'cleanup'):
                    board.cleanup()
                del self._board_instances[board_name]
                debug.info(f"Cleared cached instance for board: {board_name}")
        else:
            # Clear all cached instances
            for name, board in self._board_instances.items():
                if hasattr(board, 'cleanup'):
                    board.cleanup()
            self._board_instances.clear()
            debug.info("Cleared all cached board instances")

    def get_cached_boards(self) -> list:
        """
        Get list of currently cached board names.

        Returns:
            List of board names that have cached instances
        """
        return list(self._board_instances.keys())

    def initialize_boards_with_data_requirements(self, data, matrix, sleepEvent):
        """
        Pre-initialize boards that require early data fetching.

        This method checks board classes for requires_early_initialization = True and
        only instantiates those boards, allowing them to start background data fetching
        before the render loop begins.

        Args:
            data: Application data object
            matrix: Display matrix object
            sleepEvent: Threading event for sleep/wake control
        """
        debug.info("Boards: Pre-initializing boards with data requirements")
        initialized_count = 0

        for board_name, board_class in self._boards.items():
            try:
                # Check class attribute directly - no need to instantiate to check
                if getattr(board_class, 'requires_early_initialization', False):
                    # Only instantiate boards that actually need early initialization
                    board_instance = board_class(data, matrix, sleepEvent)
                    self._board_instances[board_name] = board_instance
                    debug.info(f"Boards: Pre-initialized board '{board_name}' for early data fetching")
                    initialized_count += 1

            except Exception as exc:
                debug.error(f"Boards: Failed to pre-initialize board '{board_name}': {exc}")

        debug.info(f"Boards: Pre-initialized {initialized_count} boards with data requirements")

    # Board handler for PushButton
    def _pb_board(self, data, matrix, sleepEvent):

        board = getattr(self, data.config.pushbutton_state_triggered1)
        board(data, matrix, sleepEvent)

    # Board handler for Weather Alert
    def _wx_alert(self, data, matrix, sleepEvent):

        board = getattr(self, "wxalert")
        board(data, matrix, sleepEvent)

    # Board handler for screensaver
    def _screensaver(self, data, matrix, sleepEvent):

        board = getattr(self, "screensaver")
        board(data, matrix, sleepEvent)

    # Board handler for Off day state
    def _off_day(self, data, matrix, sleepEvent):
        bord_index = 0
        while True:
            board = getattr(self, data.config.boards_off_day[bord_index], None)
            data.curr_board = data.config.boards_off_day[bord_index]
            debug.debug(f"Off Day Board Index: {bord_index} Board: {data.config.boards_off_day[bord_index]}")
            
            if data.pb_trigger:
                debug.info('PushButton triggered....will display ' + data.config.pushbutton_state_triggered1 + ' board ' + "Overriding off_day -> " + data.config.boards_off_day[bord_index])
                if not data.screensaver:
                    data.pb_trigger = False
                board = getattr(self,data.config.pushbutton_state_triggered1)
                data.curr_board = data.config.pushbutton_state_triggered1
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info('MQTT triggered....will display ' + data.mqtt_showboard + ' board ' + "Overriding off_day -> " + data.config.boards_off_day[bord_index])
                if not data.screensaver:
                    data.mqtt_trigger = False
                board = getattr(self,data.mqtt_showboard)
                data.curr_board = data.mqtt_showboard
                bord_index -= 1

            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info('Weather Alert triggered in off day loop....will display weather alert board')
                data.wx_alert_interrupt = False
                #Display the board from the config
                board = getattr(self,"wxalert")
                data.curr_board = "wxalert"
                bord_index -= 1

            # Display the Screensaver Board
            if data.screensaver:
                if not data.pb_trigger:
                    debug.info('Screensaver triggered in off day loop....')
                    #Display the board from the config
                    board = getattr(self,"screensaver")
                    data.curr_board = "screensaver"
                    data.prev_board = data.config.boards_off_day[bord_index]
                    bord_index -= 1
                else:
                    data.pb_trigger = False

            if board:
                debug.debug(f"Displaying Off Day Board: {data.config.boards_off_day[bord_index]}")
                board(data, matrix, sleepEvent)
            else :
                debug.error(f"Board not found: {data.config.boards_off_day[bord_index]}. Check board exists and config.json is correct")


            if bord_index >= (len(data.config.boards_off_day) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def _scheduled(self, data, matrix, sleepEvent):
        bord_index = 0
        while True:
            board = getattr(self, data.config.boards_scheduled[bord_index], None)
            data.curr_board = data.config.boards_scheduled[bord_index]
            if data.pb_trigger:
                debug.info('PushButton triggered....will display ' + data.config.pushbutton_state_triggered1 + ' board ' + "Overriding scheduled -> " + data.config.boards_scheduled[bord_index])
                if not data.screensaver:
                    data.pb_trigger = False
                board = getattr(self,data.config.pushbutton_state_triggered1)
                data.curr_board = data.config.pushbutton_state_triggered1
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info('MQTT triggered....will display ' + data.mqtt_showboard + ' board ' + "Overriding scheduled -> " + data.config.boards_off_day[bord_index])
                if not data.screensaver:
                    data.mqtt_trigger = False
                board = getattr(self,data.mqtt_showboard)
                data.curr_board = data.mqtt_showboard
                bord_index -= 1


            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info('Weather Alert triggered in scheduled loop....will display weather alert board')
                data.wx_alert_interrupt = False
                #Display the board from the config
                board = getattr(self,"wxalert")
                data.curr_board = "wxalert"
                bord_index -= 1

            # Display the Screensaver Board
            if data.screensaver:
                if not data.pb_trigger:
                    debug.info('Screensaver triggered in scheduled loop....')
                    #Display the board from the config
                    board = getattr(self,"screensaver")
                    data.curr_board = "screensaver"
                    data.prev_board = data.config.boards_off_day[bord_index]
                    bord_index -= 1
                else:
                    data.pb_trigger = False

            if board:
                board(data, matrix, sleepEvent)
            else :
                debug.error(f"Board not found: {data.config.boards_scheduled[bord_index]}. Check board exists and config.json is correct")

            if bord_index >= (len(data.config.boards_scheduled) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def _intermission(self, data, matrix, sleepEvent):
        bord_index = 0
        while True:
            board = getattr(self, data.config.boards_intermission[bord_index], None)
            data.curr_board = data.config.boards_intermission[bord_index]

            if data.pb_trigger:
                debug.info('PushButton triggered....will display ' + data.config.pushbutton_state_triggered1 + ' board ' + "Overriding intermission -> " + data.config.boards_intermission[bord_index])
                if not data.screensaver:
                    data.pb_trigger = False
                board = getattr(self,data.config.pushbutton_state_triggered1)
                data.curr_board = data.config.pushbutton_state_triggered1
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info('MQTT triggered....will display ' + data.mqtt_showboard + ' board ' + "Overriding intermission -> " + data.config.boards_off_day[bord_index])
                if not data.screensaver:
                    data.mqtt_trigger = False
                board = getattr(self,data.mqtt_showboard)
                data.curr_board = data.mqtt_showboard
                bord_index -= 1

            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info('Weather Alert triggered in intermission....will display weather alert board')
                data.wx_alert_interrupt = False
                #Display the board from the config
                board = getattr(self,"wxalert")
                data.curr_board = "wxalert"
                bord_index -= 1

            ## Don't Display the Screensaver Board in "live game mode"
            # if data.screensaver:
            #     if not data.pb_trigger:
            #         debug.info('Screensaver triggered in intermission loop....')
            #         #Display the board from the config
            #         board = getattr(self,"screensaver")
            #         data.curr_board = "screensaver"
            #         data.prev_board = data.config.boards_off_day[bord_index]
            #         bord_index -= 1
            #     else:
            #         data.pb_trigger = False

            if board:
                board(data, matrix, sleepEvent)
            else :
                debug.error(f"Board not found: {data.config.boards_intermission[bord_index]}. Check board exists and config.json is correct")


            if bord_index >= (len(data.config.boards_intermission) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def _post_game(self, data, matrix, sleepEvent):
        bord_index = 0
        while True:
            board = getattr(self, data.config.boards_post_game[bord_index], None)
            data.curr_board = data.config.boards_post_game[bord_index]

            if data.pb_trigger:
                debug.info('PushButton triggered....will display ' + data.config.pushbutton_state_triggered1 + ' board ' + "Overriding post_game -> " + data.config.boards_post_game[bord_index])
                if not data.screensaver:
                    data.pb_trigger = False
                board = getattr(self,data.config.pushbutton_state_triggered1)
                data.curr_board = data.config.pushbutton_state_triggered1
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info('MQTT triggered....will display ' + data.mqtt_showboard + ' board ' + "Overriding post_game -> " + data.config.boards_off_day[bord_index])
                if not data.screensaver:
                    data.mqtt_trigger = False
                board = getattr(self,data.mqtt_showboard)
                data.curr_board = data.mqtt_showboard
                bord_index -= 1

            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info('Weather Alert triggered in post game loop....will display weather alert board')
                data.wx_alert_interrupt = False
                #Display the board from the config
                board = getattr(self,"wxalert")
                data.curr_board = "wxalert"
                bord_index -= 1

            # Display the Screensaver Board
            if data.screensaver:
                if not data.pb_trigger:
                    debug.info('Screensaver triggered in post game loop....')
                    #Display the board from the config
                    board = getattr(self,"screensaver")
                    data.curr_board = "screensaver"
                    data.prev_board = data.config.boards_off_day[bord_index]
                    bord_index -= 1
                else:
                    data.pb_trigger = False


            if board:
                board(data, matrix, sleepEvent)
            else :
                debug.error(f"Board not found: {data.config.boards_post_game[bord_index]}. Check board exists and config.json is correct")

            if bord_index >= (len(data.config.boards_post_game) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def fallback(self, data, matrix, sleepEvent):
        Clock(data, matrix, sleepEvent)

    def scoreticker(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('scoreticker', Scoreticker, data, matrix, sleepEvent)
        board.render()

    # Since 2024, the playoff features are removed as we have not colected the new API endpoint for them.
    def seriesticker(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('seriesticker', Seriesticker, data, matrix, sleepEvent)
        board.render()

    # Since 2024, the playoff features are removed as we have not colected the new API endpoint for them.
    def stanley_cup_champions(self, data, matrix, sleepEvent):
        debug.info("stanley_cup_champions is disabled. This feature is not available right now")
        pass
        #StanleyCupChampions(data, matrix, sleepEvent).render()

    def standings(self, data, matrix, sleepEvent):
        #Try making standings a thread
        board = self._get_cached_board_instance('standings', Standings, data, matrix, sleepEvent)
        board.render()

    def team_summary(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('team_summary', TeamSummary, data, matrix, sleepEvent)
        board.render()

    def clock(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('clock', Clock, data, matrix, sleepEvent)
        board.render()

    def pbdisplay(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('pbdisplay', pbDisplay, data, matrix, sleepEvent)
        board.draw()

    def weather(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('weather', wxWeather, data, matrix, sleepEvent)
        board.render()

    def wxalert(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('wxalert', wxAlert, data, matrix, sleepEvent)
        board.render()

    def wxforecast(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('wxforecast', wxForecast, data, matrix, sleepEvent)
        board.render()

    def screensaver(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('screensaver', screenSaver, data, matrix, sleepEvent)
        board.render()

    def christmas(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('christmas', Christmas, data, matrix, sleepEvent)
        board.draw()

    def player_stats(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('player_stats', PlayerStatsRenderer, data, matrix, sleepEvent)
        board.render()

    def ovi_tracker(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('ovi_tracker', OviTrackerRenderer, data, matrix, sleepEvent)
        board.render()

    def stats_leaders(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance('stats_leaders', StatsLeaders, data, matrix, sleepEvent)
        board.render()

    def _get_board_list(self):
        boards = []

        # Add stats leaders board check
        if self.data.config.boards_enabled["stats_leaders"]:
            boards.append(self.stats_leaders)

        return boards
