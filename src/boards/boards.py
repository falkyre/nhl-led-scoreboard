"""
A Board is simply a display object with specific parameters made to be shown on screen.
Board modules can be added by placing them in the src/boards/plugins/ or src/boards/builtins/ directories.
"""

import importlib
import inspect
import json
import logging
import os
import re
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_package_version
from pathlib import Path

from packaging import version

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
from .board_manager import BoardManager

debug = logging.getLogger("scoreboard")


class Boards:
    def __init__(self):
        self._boards = {}
        self._board_instances = {}  # Deprecated: kept for backward compatibility
        self._app_version = self._get_app_version()
        self._register_legacy_boards()
        self._load_boards()
        # Initialize the BoardManager after boards are discovered/registered
        self.board_manager = BoardManager(self)

    def _get_app_version(self) -> str:
        """
        Get the application version from VERSION file.

        Returns:
            Version string, or "0.0.0" if not found
        """
        version_file = Path(os.getcwd()) / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text().strip()
            except Exception as e:
                debug.warning(f"Could not read VERSION file: {e}")
        return "0.0.0"

    def _register_legacy_boards(self):
        """
        Register legacy built-in boards in the main registry.

        These are boards that were originally imported directly and have
        explicit methods. By registering them in _boards, they work with
        the unified render_board() method.
        """
        legacy_boards = {
            "scoreticker": Scoreticker,
            "seriesticker": Seriesticker,
            "standings": Standings,
            "team_summary": TeamSummary,
            "clock": Clock,
            "pbdisplay": pbDisplay,
            "weather": wxWeather,
            "wxalert": wxAlert,
            "wxforecast": wxForecast,
            "screensaver": screenSaver,
            "christmas": Christmas,
            "player_stats": PlayerStatsRenderer,
            "ovi_tracker": OviTrackerRenderer,
            "stats_leaders": StatsLeaders,
        }

        for board_id, board_class in legacy_boards.items():
            self._boards[board_id] = board_class
            debug.debug(f"Registered legacy board: {board_id}")

        debug.info(f"Registered {len(legacy_boards)} legacy boards")

    def _load_boards(self):
        """
        Dynamically load board modules from both plugins and builtins directories.

        Scans src/boards/plugins/ for third-party/user board modules and src/boards/builtins/
        for system builtin board modules. Both follow the same structure and loading mechanism.
        Each board directory should contain an __init__.py and a board.py with the board class.
        """
        # Load from plugins directory (third-party/user board modules)
        self._load_boards_from_directory("plugins", "plugin")

        # Load from builtins directory (system board modules)
        self._load_boards_from_directory("builtins", "builtin")

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
            if not board_dir.is_dir() or board_dir.name.startswith("_"):
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
        plugin_json = board_dir / "plugin.json"
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
            current_python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

            if not self._check_version_requirement(current_python, python_req):
                debug.error(
                    f"Plugin '{plugin_name}' requires Python {python_req}, but current version is {current_python}"
                )
                return False

            debug.debug(f"Plugin '{plugin_name}' Python requirement {python_req} satisfied (current: {current_python})")

        # Check app version
        if "app_version" in requirements:
            app_req = requirements["app_version"]

            if not self._check_version_requirement(self._app_version, app_req):
                debug.error(
                    f"Plugin '{plugin_name}' requires app version {app_req}, but current version is {self._app_version}"
                )
                return False

            debug.debug(f"Plugin '{plugin_name}' app requirement {app_req} satisfied (current: {self._app_version})")

        # Check Python dependencies
        if "python_dependencies" in requirements:
            for dep in requirements["python_dependencies"]:
                # Extract package name (handle versions like "holidays>=0.35")
                pkg_name = dep.split(">=")[0].split("==")[0].split("<")[0].strip()
                try:
                    # Check if package is installed using pip package name (e.g., "pillow" not "PIL")
                    get_package_version(pkg_name)
                    debug.debug(f"Plugin '{plugin_name}' dependency '{pkg_name}' is available")
                except PackageNotFoundError:
                    debug.error(f"Plugin '{plugin_name}' requires '{dep}' but it's not installed")
                    return False

        return True

    def _check_version_requirement(self, current: str, requirement: str) -> bool:
        """
        Check if current version meets requirement.

        Args:
            current: Current version string (e.g., "2025.10.1")
            requirement: Requirement string (e.g., ">=2025.09.00", "==1.0.0")

        Returns:
            True if requirement is met, False otherwise
        """
        try:
            current_ver = version.parse(current)

            # Parse requirement (e.g., ">=2025.09.00")
            match = re.match(r"^\s*(>=|>|<=|<|==|!=)\s*(.+)$", requirement)
            if not match:
                debug.warning(f"Invalid version requirement format: {requirement}")
                return True  # Don't block if format is invalid

            operator, required_version = match.groups()
            required_ver = version.parse(required_version.strip())

            # Check based on operator
            if operator == ">=":
                return current_ver >= required_ver
            elif operator == ">":
                return current_ver > required_ver
            elif operator == "<=":
                return current_ver <= required_ver
            elif operator == "<":
                return current_ver < required_ver
            elif operator == "==":
                return current_ver == required_ver
            elif operator == "!=":
                return current_ver != required_ver
            else:
                debug.warning(f"Unknown operator in requirement: {requirement}")
                return True

        except Exception as e:
            debug.warning(f"Could not parse version requirement '{requirement}': {e}")
            return True  # Don't block on parsing errors

    def _load_board_from_metadata(
        self, board_config: dict, board_dir: Path, directory_name: str, plugin_name: str, board_type: str
    ):
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
        module_path = f"boards.{directory_name}.{plugin_name}.{module_name_short}"
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
        if not (inspect.isclass(board_class) and issubclass(board_class, BoardBase) and board_class != BoardBase):
            debug.error(f"'{class_name}' is not a valid BoardBase subclass")
            return

        # Register the board in the registry
        self._boards[board_id] = board_class

        debug.info(f"Loaded {board_type} board: {board_id} from '{plugin_name}' ({class_name})")

    def render_board(self, board_id: str, data, matrix, sleepEvent):
        """
        Render any board by ID with automatic lazy initialization.

        This is the preferred way to render boards loaded from plugins/builtins
        and legacy boards. Delegates to BoardManager for lifecycle management.

        Args:
            board_id: The board identifier (from plugin.json or legacy board name)
            data: Application data object
            matrix: Display matrix object
            sleepEvent: Threading event for sleep/wake control

        Returns:
            Result of the board's render() or draw() method

        Raises:
            ValueError: If board_id is not found in registry
        """
        # Delegate to BoardManager
        return self.board_manager.render_board(board_id, data, matrix, sleepEvent)


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

        Delegates to BoardManager for lifecycle management.

        Args:
            board_name: Specific board to clear, or None to clear all
        """
        if board_name:
            self.board_manager.cleanup_board(board_name)
        else:
            self.board_manager.clear_all_boards()

    def get_cached_boards(self) -> list:
        """
        Get list of currently initialized board names.

        Delegates to BoardManager.

        Returns:
            List of board names that have initialized instances
        """
        return self.board_manager.get_initialized_boards()

    # Board handler for PushButton
    def _pb_board(self, data, matrix, sleepEvent):
        self.render_board(data.config.pushbutton_state_triggered1, data, matrix, sleepEvent)

    # Board handler for Weather Alert
    def _wx_alert(self, data, matrix, sleepEvent):
        self.render_board("wxalert", data, matrix, sleepEvent)

    # Board handler for screensaver
    def _screensaver(self, data, matrix, sleepEvent):
        self.render_board("screensaver", data, matrix, sleepEvent)

    # Board handler for Off day state
    def _off_day(self, data, matrix, sleepEvent):
        # Snapshot the board list to avoid issues if config changes mid-loop
        boards_list = list(data.config.boards_off_day)
        bord_index = 0
        while True:
            board_id = boards_list[bord_index]
            data.curr_board = board_id
            debug.debug(f"Off Day Board Index: {bord_index} Board: {board_id}")

            if data.pb_trigger:
                debug.info(
                    "PushButton triggered....will display "
                    + data.config.pushbutton_state_triggered1
                    + " board "
                    + "Overriding off_day -> "
                    + board_id
                )
                if not data.screensaver:
                    data.pb_trigger = False
                board_id = data.config.pushbutton_state_triggered1
                data.curr_board = board_id
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info(
                    "MQTT triggered....will display "
                    + data.mqtt_showboard
                    + " board "
                    + "Overriding off_day -> "
                    + boards_list[bord_index]
                )
                if not data.screensaver:
                    data.mqtt_trigger = False
                board_id = data.mqtt_showboard
                data.curr_board = board_id
                bord_index -= 1

            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info("Weather Alert triggered in off day loop....will display weather alert board")
                data.wx_alert_interrupt = False
                # Display the board from the config
                board_id = "wxalert"
                data.curr_board = "wxalert"
                bord_index -= 1

            # Display the Screensaver Board
            if data.screensaver:
                if not data.pb_trigger:
                    debug.info("Screensaver triggered in off day loop....")
                    # Display the board from the config
                    board_id = "screensaver"
                    data.curr_board = "screensaver"
                    data.prev_board = boards_list[bord_index]
                    bord_index -= 1
                else:
                    data.pb_trigger = False

            # Render the selected board
            try:
                debug.debug(f"Displaying Off Day Board: {board_id}")
                self.render_board(board_id, data, matrix, sleepEvent)
            except ValueError:
                debug.error(
                    f"Board not found: {board_id}. "
                    "Check board exists and config.json is correct"
                )

            if bord_index >= (len(boards_list) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def _scheduled(self, data, matrix, sleepEvent):
        # Snapshot the board list to avoid issues if config changes mid-loop
        boards_list = list(data.config.boards_scheduled)
        bord_index = 0
        while True:
            board_id = boards_list[bord_index]
            data.curr_board = board_id

            if data.pb_trigger:
                debug.info(
                    "PushButton triggered....will display "
                    + data.config.pushbutton_state_triggered1
                    + " board "
                    + "Overriding scheduled -> "
                    + board_id
                )
                if not data.screensaver:
                    data.pb_trigger = False
                board_id = data.config.pushbutton_state_triggered1
                data.curr_board = board_id
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info(
                    "MQTT triggered....will display "
                    + data.mqtt_showboard
                    + " board "
                    + "Overriding scheduled -> "
                    + boards_list[bord_index]
                )
                if not data.screensaver:
                    data.mqtt_trigger = False
                board_id = data.mqtt_showboard
                data.curr_board = board_id
                bord_index -= 1

            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info("Weather Alert triggered in scheduled loop....will display weather alert board")
                data.wx_alert_interrupt = False
                # Display the board from the config
                board_id = "wxalert"
                data.curr_board = "wxalert"
                bord_index -= 1

            # Display the Screensaver Board
            if data.screensaver:
                if not data.pb_trigger:
                    debug.info("Screensaver triggered in scheduled loop....")
                    # Display the board from the config
                    board_id = "screensaver"
                    data.curr_board = "screensaver"
                    data.prev_board = boards_list[bord_index]
                    bord_index -= 1
                else:
                    data.pb_trigger = False

            # Render the selected board
            try:
                self.render_board(board_id, data, matrix, sleepEvent)
            except ValueError:
                debug.error(
                    f"Board not found: {board_id}. "
                    "Check board exists and config.json is correct"
                )

            if bord_index >= (len(boards_list) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def _intermission(self, data, matrix, sleepEvent):
        # Snapshot the board list to avoid issues if config changes mid-loop
        boards_list = list(data.config.boards_intermission)
        bord_index = 0
        while True:
            board_id = boards_list[bord_index]
            data.curr_board = board_id

            if data.pb_trigger:
                debug.info(
                    "PushButton triggered....will display "
                    + data.config.pushbutton_state_triggered1
                    + " board "
                    + "Overriding intermission -> "
                    + board_id
                )
                if not data.screensaver:
                    data.pb_trigger = False
                board_id = data.config.pushbutton_state_triggered1
                data.curr_board = board_id
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info(
                    "MQTT triggered....will display "
                    + data.mqtt_showboard
                    + " board "
                    + "Overriding intermission -> "
                    + boards_list[bord_index]
                )
                if not data.screensaver:
                    data.mqtt_trigger = False
                board_id = data.mqtt_showboard
                data.curr_board = board_id
                bord_index -= 1

            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info("Weather Alert triggered in intermission....will display weather alert board")
                data.wx_alert_interrupt = False
                # Display the board from the config
                board_id = "wxalert"
                data.curr_board = "wxalert"
                bord_index -= 1

            ## Don't Display the Screensaver Board in "live game mode"
            # if data.screensaver:
            #     if not data.pb_trigger:
            #         debug.info('Screensaver triggered in intermission loop....')
            #         #Display the board from the config
            #         board_id = "screensaver"
            #         data.curr_board = "screensaver"
            #         data.prev_board = boards_list[bord_index]
            #         bord_index -= 1
            #     else:
            #         data.pb_trigger = False

            # Render the selected board
            try:
                self.render_board(board_id, data, matrix, sleepEvent)
            except ValueError:
                debug.error(
                    f"Board not found: {board_id}. "
                    "Check board exists and config.json is correct"
                )

            if bord_index >= (len(boards_list) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def _post_game(self, data, matrix, sleepEvent):
        # Snapshot the board list to avoid issues if config changes mid-loop
        boards_list = list(data.config.boards_post_game)
        bord_index = 0
        while True:
            board_id = boards_list[bord_index]
            data.curr_board = board_id

            if data.pb_trigger:
                debug.info(
                    "PushButton triggered....will display "
                    + data.config.pushbutton_state_triggered1
                    + " board "
                    + "Overriding post_game -> "
                    + board_id
                )
                if not data.screensaver:
                    data.pb_trigger = False
                board_id = data.config.pushbutton_state_triggered1
                data.curr_board = board_id
                bord_index -= 1

            if data.mqtt_trigger:
                debug.info(
                    "MQTT triggered....will display "
                    + data.mqtt_showboard
                    + " board "
                    + "Overriding post_game -> "
                    + boards_list[bord_index]
                )
                if not data.screensaver:
                    data.mqtt_trigger = False
                board_id = data.mqtt_showboard
                data.curr_board = board_id
                bord_index -= 1

            # Display the Weather Alert board
            if data.wx_alert_interrupt:
                debug.info("Weather Alert triggered in post game loop....will display weather alert board")
                data.wx_alert_interrupt = False
                # Display the board from the config
                board_id = "wxalert"
                data.curr_board = "wxalert"
                bord_index -= 1

            # Display the Screensaver Board
            if data.screensaver:
                if not data.pb_trigger:
                    debug.info("Screensaver triggered in post game loop....")
                    # Display the board from the config
                    board_id = "screensaver"
                    data.curr_board = "screensaver"
                    data.prev_board = boards_list[bord_index]
                    bord_index -= 1
                else:
                    data.pb_trigger = False

            # Render the selected board
            try:
                self.render_board(board_id, data, matrix, sleepEvent)
            except ValueError:
                debug.error(
                    f"Board not found: {board_id}. "
                    "Check board exists and config.json is correct"
                )

            if bord_index >= (len(boards_list) - 1):
                return
            else:
                if not data.pb_trigger or not data.wx_alert_interrupt or not data.screensaver or not data.mqtt_trigger:
                    bord_index += 1

    def fallback(self, data, matrix, sleepEvent):
        Clock(data, matrix, sleepEvent)

    def scoreticker(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("scoreticker", Scoreticker, data, matrix, sleepEvent)
        board.render()

    # Since 2024, the playoff features are removed as we have not colected the new API endpoint for them.
    def seriesticker(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("seriesticker", Seriesticker, data, matrix, sleepEvent)
        board.render()

    # Since 2024, the playoff features are removed as we have not colected the new API endpoint for them.
    def stanley_cup_champions(self, data, matrix, sleepEvent):
        debug.info("stanley_cup_champions is disabled. This feature is not available right now")
        pass
        # StanleyCupChampions(data, matrix, sleepEvent).render()

    def standings(self, data, matrix, sleepEvent):
        # Try making standings a thread
        board = self._get_cached_board_instance("standings", Standings, data, matrix, sleepEvent)
        board.render()

    def team_summary(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("team_summary", TeamSummary, data, matrix, sleepEvent)
        board.render()

    def clock(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("clock", Clock, data, matrix, sleepEvent)
        board.render()

    def pbdisplay(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("pbdisplay", pbDisplay, data, matrix, sleepEvent)
        board.draw()

    def weather(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("weather", wxWeather, data, matrix, sleepEvent)
        board.render()

    def wxalert(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("wxalert", wxAlert, data, matrix, sleepEvent)
        board.render()

    def wxforecast(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("wxforecast", wxForecast, data, matrix, sleepEvent)
        board.render()

    def screensaver(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("screensaver", screenSaver, data, matrix, sleepEvent)
        board.render()

    def christmas(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("christmas", Christmas, data, matrix, sleepEvent)
        board.draw()

    def player_stats(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("player_stats", PlayerStatsRenderer, data, matrix, sleepEvent)
        board.render()

    def ovi_tracker(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("ovi_tracker", OviTrackerRenderer, data, matrix, sleepEvent)
        board.render()

    def stats_leaders(self, data, matrix, sleepEvent):
        board = self._get_cached_board_instance("stats_leaders", StatsLeaders, data, matrix, sleepEvent)
        board.render()

    def _get_board_list(self):
        boards = []

        # Add stats leaders board check
        if self.data.config.boards_enabled["stats_leaders"]:
            boards.append(self.stats_leaders)

        return boards
