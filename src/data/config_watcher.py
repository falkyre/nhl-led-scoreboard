import logging
import os
import threading

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

debug = logging.getLogger("scoreboard")

class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, scoreboard_config, scheduler_manager, main_renderer=None):
        super().__init__()
        self.scoreboard_config = scoreboard_config
        self.scheduler_manager = scheduler_manager
        self.main_renderer = main_renderer

    def on_modified(self, event):
        # Only react if the file modified is config.json
        config_path = self.scoreboard_config.config_file_path
        if event.src_path == config_path:
            debug.info(f"Detected change in {event.src_path}, attempting to reload config...")
            self.scoreboard_config._reload_config()
            self.scheduler_manager.schedule_jobs()

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

    def on_modified(self, event):
        # Only react to config.json files in plugin/builtin directories
        if event.is_directory or not event.src_path.endswith('config.json'):
            return

        # Extract board_id from path: src/boards/plugins/nfl_board/config.json -> nfl_board
        try:
            path_parts = event.src_path.split(os.sep)
            # Find 'plugins' or 'builtins' in path
            if 'plugins' in path_parts:
                idx = path_parts.index('plugins')
                board_id = path_parts[idx + 1]
            elif 'builtins' in path_parts:
                idx = path_parts.index('builtins')
                board_id = path_parts[idx + 1]
            else:
                return  # Not a plugin/builtin config

            debug.info(f"Plugin config changed: {board_id} ({event.src_path})")

            # Cleanup the board - next render will reinitialize with new config
            if board_id in self.board_manager.get_initialized_boards():
                debug.info(f"Reinitializing board '{board_id}' due to config change")
                self.board_manager.cleanup_board(board_id)
            else:
                debug.debug(f"Board '{board_id}' not initialized, no action needed")

        except Exception as e:
            debug.error(f"Error handling plugin config change for {event.src_path}: {e}")

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

    if os.path.exists(plugins_dir):
        observer.schedule(event_handler, path=plugins_dir, recursive=True)
        debug.info(f"Started watchdog for plugin configs: {plugins_dir}")

    if os.path.exists(builtins_dir):
        observer.schedule(event_handler, path=builtins_dir, recursive=True)
        debug.info(f"Started watchdog for builtin configs: {builtins_dir}")

    thread = threading.Thread(target=observer.start, daemon=True)
    thread.start()

    return observer, thread, event_handler

def start_config_watcher(scoreboard_config, scheduler_manager, main_renderer=None):
    """
    Start a watchdog observer thread on config/config.json for changes,
    calling _reload_config if file is reloaded and validated.

    Args:
        scoreboard_config: The ScoreboardConfig instance
        scheduler_manager: The SchedulerManager instance
        main_renderer: Optional MainRenderer instance for board sync

    Returns:
        tuple: (observer, thread, event_handler) for lifecycle management
    """
    config_path = scoreboard_config.config_file_path
    config_dir = os.path.dirname(config_path)
    event_handler = ConfigReloadHandler(scoreboard_config, scheduler_manager, main_renderer)
    observer = Observer()
    observer.schedule(event_handler, path=config_dir, recursive=False)
    thread = threading.Thread(target=observer.start, daemon=True)
    thread.start()
    debug.info(f"Started watchdog thread for {config_path}")
    return observer, thread, event_handler
