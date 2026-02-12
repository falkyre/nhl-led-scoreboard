"""
Base class for board modules to ensure consistent interface and enable dynamic loading.
"""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from config.file import ConfigFile
from config.files.layout import LayoutConfig
from renderer.matrix import Matrix

debug = logging.getLogger("scoreboard")
class BoardLayoutConfig(LayoutConfig):
    """
    Extended LayoutConfig that loads layout files from board directories (plugins or builtins).
    """
    def __init__(self, size, fonts, board_dir):
        self.board_dir = board_dir

        # Create ConfigFile instances that point to board layout files
        # Try to load generic layout.json first (may not exist for some boards)
        generic_layout_path = str(board_dir / 'layout.json')
        size_layout_path = str(board_dir / f'layout_{size[0]}x{size[1]}.json')

        self.layout = ConfigFile(generic_layout_path, size, False)
        self.dynamic_layout = ConfigFile(size_layout_path, size, False)

        # If generic layout failed to load but size-specific exists, use size-specific as base
        if not hasattr(self.layout, 'data') and hasattr(self.dynamic_layout, 'data'):
            self.layout = self.dynamic_layout
            # Create empty dynamic_layout to avoid issues with combine
            self.dynamic_layout = ConfigFile('nonexistent_file_path', size, False)
        elif hasattr(self.layout, 'data') and hasattr(self.dynamic_layout, 'data'):
            # Both exist, combine as normal
            self.layout.combine(self.dynamic_layout)

        # Use default system colors and logos (boards use system color schemes)
        self.logo_config = ConfigFile('config/layout/logos.json', size)
        self.dynamic_logo_config = ConfigFile('config/layout/logos_{}x{}.json'.format(size[0], size[1]), size, False)
        self.logo_config.combine(self.dynamic_logo_config)

        self.colors = ConfigFile('config/colors/layout.json')
        self.fonts = fonts


class BoardBase(ABC):
    """
    Abstract base class for all board modules.

    All board modules (plugins and builtins) must inherit from this class and implement the required methods.
    This ensures a consistent interface for the board loading system.
    """

    def __init__(self, data, matrix: Matrix, sleepEvent):
        """
        Initialize the board module.

        Args:
            data: Application data object containing config and state
            matrix: Display matrix object for rendering
            sleepEvent: Threading event for sleep/wake control
        """
        self.data = data
        self.matrix = matrix
        self.sleepEvent = sleepEvent

        # Board metadata (should be overridden by subclasses)
        self.board_name = self.__class__.__name__
        self.board_version = "1.0.0"
        self.board_description = "A board module"

        # Track scheduled jobs for automatic cleanup (optional - boards can use this)
        self._scheduled_job_ids = []

        # Detect display size
        self.display_width, self.display_height = self._detect_display_size()

        # Load board-specific config sources and layout
        self._board_defaults, self._board_user_config = self._parse_config_files()
        # Merged view for backward compatibility with direct board_config access
        self.board_config = {**self._board_defaults, **self._board_user_config}
        self.board_layout = self._create_board_layout_config()

    @abstractmethod
    def render(self):
        """
        Render the board content to the matrix.

        This method must be implemented by all board modules.
        It should handle the complete display logic for the board.
        """
        pass

    def _parse_config_files(self) -> tuple:
        """
        Parse board configuration files from the board directory.
        Works with both plugins and builtins directories.

        Loads defaults and user config as separate dicts for per-item resolution
        in get_config_value(). Both builtins and plugins check for config.defaults.json
        and config.sample.json (defaults takes priority over sample).

        Returns:
            Tuple of (defaults_dict, user_config_dict).
        """
        defaults = {}
        user_config = {}

        try:
            board_module = self.__class__.__module__

            if '.plugins.' in board_module or '.builtins.' in board_module:
                module_parts = board_module.split('.')
                if len(module_parts) >= 4:
                    board_type = module_parts[1]  # 'plugins' or 'builtins'
                    board_name = module_parts[2]  # board directory name
                    board_dir = Path(__file__).parent / board_type / board_name

                    config_path = board_dir / 'config.json'
                    config_defaults_path = board_dir / 'config.defaults.json'
                    config_sample_path = board_dir / 'config.sample.json'

                    # Load defaults: sample first (lowest), then defaults on top (higher priority)
                    if config_sample_path.exists():
                        with open(config_sample_path, 'r') as f:
                            defaults.update(json.load(f))
                    if config_defaults_path.exists():
                        with open(config_defaults_path, 'r') as f:
                            defaults.update(json.load(f))

                    # Load user overrides
                    if config_path.exists():
                        with open(config_path, 'r') as f:
                            user_config = json.load(f)
        except Exception as e:
            debug.error(f"Error loading board config: {e}")

        return defaults, user_config

    def _detect_display_size(self) -> tuple:
        """
        Detect the display size from matrix or config.

        Returns:
            Tuple of (width, height) as integers
        """
        # Try to get size from matrix object first
        if hasattr(self.matrix, 'width') and hasattr(self.matrix, 'height'):
            return (self.matrix.width, self.matrix.height)

        # Try to get from data config
        if hasattr(self.data, 'config'):
            # Look for common config patterns
            if hasattr(self.data.config, 'matrix'):
                if hasattr(self.data.config.matrix, 'width') and hasattr(self.data.config.matrix, 'height'):
                    return (self.data.config.matrix.width, self.data.config.matrix.height)

            # Look for layout config that might contain size info
            if hasattr(self.data.config, 'layout'):
                if hasattr(self.data.config.layout, 'width') and hasattr(self.data.config.layout, 'height'):
                    return (self.data.config.layout.width, self.data.config.layout.height)

        # Default to most common size if detection fails
        return (128, 64)

    def _create_board_layout_config(self) -> Optional[LayoutConfig]:
        """
        Create a LayoutConfig instance for this board using the system layout infrastructure.

        This allows both plugins and builtins to use the same layout system as the main application,
        with support for size-specific layouts, relative positioning, etc.

        Returns:
            LayoutConfig instance if board has layout files, None otherwise
        """
        try:
            # Get the module path to determine board location
            board_module = self.__class__.__module__

            # Handle both plugins and builtins
            if '.plugins.' in board_module or '.builtins.' in board_module:
                # Extract board type and name from module path
                module_parts = board_module.split('.')
                if len(module_parts) >= 4:
                    board_type = module_parts[1]  # 'plugins' or 'builtins'
                    board_name = module_parts[2]  # board directory name

                    board_dir = Path(__file__).parent / board_type / board_name

                    # Check if board has layout files
                    size_layout_path = board_dir / f'layout_{self.display_width}x{self.display_height}.json'
                    generic_layout_path = board_dir / 'layout.json'

                    if size_layout_path.exists() or generic_layout_path.exists():
                        # Create a LayoutConfig that points to board layout files
                        layout_config = BoardLayoutConfig(
                            size=(self.display_width, self.display_height),
                            fonts=self.data.config.config.fonts,
                            board_dir=board_dir
                        )
                        return layout_config

        except Exception as e:
            debug.error(f"Error loading board layout: {e}")
            pass

        return None

    def get_board_info(self) -> Dict[str, str]:
        """
        Get board metadata information.

        Returns:
            Dict containing board name, version, and description.
        """
        return {
            'name': self.board_name,
            'version': self.board_version,
            'description': self.board_description,
        }

    def validate_config(self) -> bool:
        """
        Validate board configuration.

        Override this method to implement custom configuration validation.

        Returns:
            True if configuration is valid, False otherwise.
        """
        return True

    def get_config_value(self, key: str, default=None):
        """
        Get a configuration value with priority resolution:
            1. Central app config (config/config.json)
            2. Board user config (board dir config.json)
            3. Board defaults (board dir config.defaults.json / config.sample.json)
            4. Code-provided default

        Args:
            key: The config key to look up (e.g., 'rotation_rate', 'categories')
            default: Default value if key not found anywhere

        Returns:
            The config value from the highest priority source
        """
        # Extract board name from module path for central config lookup
        board_module = self.__class__.__module__
        board_name = None

        if '.plugins.' in board_module or '.builtins.' in board_module:
            module_parts = board_module.split('.')
            if len(module_parts) >= 3:
                board_name = module_parts[2]  # e.g., 'stats_leaders', 'season_countdown'

        log_name = board_name or self.board_name

        # Priority 1: Central app config - only if the user explicitly set this key
        if board_name and hasattr(self.data, 'config'):
            boards_raw = getattr(self.data.config, '_boards_raw', {})
            board_section = boards_raw.get(board_name, {})
            if key in board_section:
                value = board_section[key]
                debug.debug(f"{log_name}: Using central config for '{key}': {value}")
                return value

        # Priority 2: Board user config (config.json in board directory)
        if key in self._board_user_config:
            value = self._board_user_config[key]
            debug.debug(f"{log_name}: Using board user config for '{key}': {value}")
            return value

        # Priority 3: Board defaults (config.defaults.json / config.sample.json)
        if key in self._board_defaults:
            value = self._board_defaults[key]
            debug.debug(f"{log_name}: Using board defaults for '{key}': {value}")
            return value

        # Priority 4: Code-provided default
        debug.debug(f"{log_name}: Using code default for '{key}': {default}")
        return default

    def cleanup(self):
        """
        Cleanup resources when board is unloaded.

        This base implementation automatically removes any tracked scheduled jobs.
        If you override this method, call super().cleanup() to ensure jobs are cleaned up.
        """
        # Automatically cleanup any tracked scheduled jobs
        self._cleanup_scheduled_jobs()

    def _cleanup_scheduled_jobs(self):
        """
        Remove all tracked scheduled jobs from the scheduler.

        This is called automatically during cleanup.
        """
        if hasattr(self.data, 'scheduler_manager') and self._scheduled_job_ids:
            debug.info(f"{self.board_name}: Cleaning up {len(self._scheduled_job_ids)} scheduled jobs")
            for job_id in self._scheduled_job_ids[:]:  # Copy list to avoid modification during iteration
                try:
                    self.data.scheduler_manager.remove_job(job_id)
                    self._scheduled_job_ids.remove(job_id)
                except Exception as e:
                    debug.warning(f"{self.board_name}: Failed to remove job {job_id}: {e}")

    def add_scheduled_job(self, func, trigger, job_id=None, **kwargs):
        """
        Add a scheduled job and track it for automatic cleanup.

        This is a convenience wrapper around scheduler_manager.add_job() that
        automatically tracks the job ID for cleanup when the board is unloaded.

        Args:
            func: The function to schedule
            trigger: The type of trigger ('interval', 'cron', etc.)
            job_id: Optional job ID (if not provided, scheduler will generate one)
            **kwargs: Additional arguments for the scheduler

        Returns:
            The scheduled job object or None if failed

        Example:
            self.add_scheduled_job(
                self.fetch_data,
                'interval',
                job_id='my_board_fetch',
                minutes=5
            )
        """
        if not hasattr(self.data, 'scheduler_manager'):
            debug.error(f"{self.board_name}: scheduler_manager not available")
            return None

        # Add job_id to kwargs if provided
        if job_id:
            kwargs['id'] = job_id

        job = self.data.scheduler_manager.add_job(func, trigger, **kwargs)

        if job:
            # Track the job ID for cleanup
            actual_job_id = job.id if hasattr(job, 'id') else job_id
            if actual_job_id and actual_job_id not in self._scheduled_job_ids:
                self._scheduled_job_ids.append(actual_job_id)
                debug.debug(f"{self.board_name}: Tracking scheduled job: {actual_job_id}")

        return job

    # Layout helper methods

    def get_board_layout(self, board_name: str = None):
        """
        Get the layout configuration for this board.

        Args:
            board_name: Name of the board layout to get (defaults to board name)

        Returns:
            Layout object compatible with matrix renderer, or None if no layout
        """
        if not self.board_layout:
            return None

        if board_name is None:
            # Use board class name as board name
            board_name = self.__class__.__name__.lower().replace('plugin', '').replace('board', '')

        return self.board_layout.get_board_layout(board_name)

    def has_layout(self) -> bool:
        """
        Check if board has a layout configuration loaded.

        Returns:
            True if layout config exists, False otherwise
        """
        return self.board_layout is not None

