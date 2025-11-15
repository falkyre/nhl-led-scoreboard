"""
Base class for board modules to ensure consistent interface and enable dynamic loading.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
from pathlib import Path
from config.files.layout import LayoutConfig
from config.file import ConfigFile
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

    # Class attribute: indicates whether this board type requires early initialization
    # Set to True in subclasses that need to start data fetching before first render
    requires_early_initialization = False
    
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

        # Detect display size
        self.display_width, self.display_height = self._detect_display_size()

        # Load board-specific config and layout
        self.board_config = self._load_board_config()
        self.board_layout = self._create_board_layout_config()
    
    @abstractmethod
    def render(self):
        """
        Render the board content to the matrix.

        This method must be implemented by all board modules.
        It should handle the complete display logic for the board.
        """
        pass
    
    def _load_board_config(self) -> Dict[str, Any]:
        """
        Load board-specific configuration from config.json in the board directory.
        Works with both plugins and builtins directories.
        
        Returns:
            Dict containing board configuration, or empty dict if no config found.
        """
        try:
            # Get the module path to determine board location
            board_module = self.__class__.__module__
            
            # Handle both plugins and builtins (e.g., boards.plugins.name.board or boards.builtins.name.board)
            if '.plugins.' in board_module or '.builtins.' in board_module:
                # Extract board type and name from module path
                module_parts = board_module.split('.')
                if len(module_parts) >= 4:
                    board_type = module_parts[1]  # 'plugins' or 'builtins'
                    board_name = module_parts[2]  # board directory name
                    
                    config_path = Path(__file__).parent / board_type / board_name / 'config.json'
                    config_sample_path = Path(__file__).parent / board_type / board_name / 'config.sample.json'
                    
                    if config_path.exists():
                        with open(config_path, 'r') as f:
                            return json.load(f)
                    elif config_sample_path.exists():
                        debug.warning(f"{board_name}: Config not found, falling back to sample config")
                        with open(config_sample_path, 'r') as f:
                            return json.load(f)
        except Exception as e:
            debug.error(f"Error loading board config: {e}")
            pass
        
        return {}
    
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
    
    def cleanup(self):
        """
        Cleanup resources when board is unloaded.
        
        Override this method to implement custom cleanup logic.
        """
        pass
    
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

