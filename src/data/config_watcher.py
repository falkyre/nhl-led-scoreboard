import logging
import os
import threading

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

debug = logging.getLogger("scoreboard")

class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, scoreboard_config, scheduler_manager, thread_manager=None, main_renderer=None):
        super().__init__()
        self.scoreboard_config = scoreboard_config
        self.scheduler_manager = scheduler_manager
        self.thread_manager = thread_manager
        self.main_renderer = main_renderer

    def on_modified(self, event):
        # Only react if the file modified is config.json
        config_path = self.scoreboard_config.config_file_path
        if event.src_path == config_path:
            debug.info(f"Detected change in {event.src_path}, attempting to reload config...")
            self.scoreboard_config._reload_config()
            self.scheduler_manager.schedule_jobs()

            if self.thread_manager:
                self.thread_manager.update_threads()

            # Sync boards with new config if renderer is available
            if self.main_renderer:
                # Clear all boards to ensure they reinitialize with new config
                self.main_renderer.boards.board_manager.clear_all_boards()
                debug.info("ConfigReloadHandler: Cleared all boards for config reload")
                self.main_renderer.sync_boards_with_config()

    def set_main_renderer(self, main_renderer):
        """
        Set the MainRenderer instance after it's created.

        This allows the config watcher to sync boards when config changes.
        """
        self.main_renderer = main_renderer
        debug.info("ConfigReloadHandler: MainRenderer registered for board sync")

class PluginConfigHandler(FileSystemEventHandler):
    """
    Watches plugin/builtin board config files and reinitializes boards when their configs change.
    """
    def __init__(self, board_manager):
        super().__init__()
        self.board_manager = board_manager

    def _handle_config_change(self, event):
        # Only react to config.json files in plugin/builtin directories
        if event.is_directory or not event.src_path.endswith('config.json'):
            return

        # Extract board_id from path
        # For /path/to/nfl_board/config.json -> board_id is 'nfl_board' (parent dir name)
        try:
            src_path = event.src_path
            debug.debug(f"PluginConfigHandler: Detected modification to {src_path}")

            # Get the directory name containing config.json (this is the board_id)
            board_dir = os.path.dirname(src_path)
            board_id = os.path.basename(board_dir)

            debug.info(f"Plugin config changed: {board_id} ({src_path})")

            # Cleanup the board - next render will reinitialize with new config
            if board_id in self.board_manager.get_initialized_boards():
                debug.info(f"Reinitializing board '{board_id}' due to config change")
                self.board_manager.cleanup_board(board_id)
            else:
                debug.debug(f"Board '{board_id}' not initialized, no action needed")

        except Exception as e:
            debug.error(f"Error handling plugin config change for {event.src_path}: {e}", exc_info=True)

    def on_modified(self, event):
        """Handle file modification events."""
        self._handle_config_change(event)

    def on_created(self, event):
        """Handle file creation events (for editors that create new files)."""
        self._handle_config_change(event)

def start_plugin_config_watcher(board_manager, boards_base_dir='src/boards'):
    """
    Start a watchdog observer for plugin and builtin board config files.

    Watches src/boards/plugins/ and src/boards/builtins/ recursively for config.json changes.

    Args:
        board_manager: The BoardManager instance
        boards_base_dir: Base directory for boards (default: 'src/boards')

    Returns:
        tuple: (observer, thread, event_handler) for lifecycle management
    """
    event_handler = PluginConfigHandler(board_manager)
    observer = Observer()

    # Watch both plugins and builtins directories recursively
    plugins_dir = os.path.join(boards_base_dir, 'plugins')
    builtins_dir = os.path.join(boards_base_dir, 'builtins')

    # Watch plugins directory - follow symlinks for development setups
    if os.path.exists(plugins_dir):
        # Resolve symlinks and watch actual directories
        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            # Resolve symlink to actual path
            real_path = os.path.realpath(item_path)
            if os.path.isdir(real_path):
                observer.schedule(event_handler, path=real_path, recursive=True)
                if item_path != real_path:
                    debug.info(f"Started watchdog for plugin '{item}': {real_path} (symlinked from {item_path})")
                else:
                    debug.info(f"Started watchdog for plugin '{item}': {real_path}")

    # Watch builtins directory - follow symlinks for development setups
    if os.path.exists(builtins_dir):
        for item in os.listdir(builtins_dir):
            item_path = os.path.join(builtins_dir, item)
            # Resolve symlink to actual path
            real_path = os.path.realpath(item_path)
            if os.path.isdir(real_path):
                observer.schedule(event_handler, path=real_path, recursive=True)
                if item_path != real_path:
                    debug.info(f"Started watchdog for builtin '{item}': {real_path} (symlinked from {item_path})")
                else:
                    debug.info(f"Started watchdog for builtin '{item}': {real_path}")

    thread = threading.Thread(target=observer.start, daemon=True)
    thread.start()

    return observer, thread, event_handler

def start_config_watcher(scoreboard_config, scheduler_manager, thread_manager=None, main_renderer=None):
    """
    Start a watchdog observer thread on config/config.json for changes,
    calling _reload_config if file is reloaded and validated.

    Args:
        scoreboard_config: The ScoreboardConfig instance
        scheduler_manager: The SchedulerManager instance
        thread_manager: The ThreadManager instance
        main_renderer: Optional MainRenderer instance for board sync

    Returns:
        tuple: (observer, thread, event_handler) for lifecycle management
    """
    config_path = scoreboard_config.config_file_path
    config_dir = os.path.dirname(config_path)
    event_handler = ConfigReloadHandler(scoreboard_config, scheduler_manager, thread_manager, main_renderer)
    observer = Observer()
    observer.schedule(event_handler, path=config_dir, recursive=False)
    thread = threading.Thread(target=observer.start, daemon=True)
    thread.start()
    debug.info(f"Started watchdog thread for {config_path}")
    return observer, thread, event_handler
