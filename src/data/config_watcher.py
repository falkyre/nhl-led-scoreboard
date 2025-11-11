import logging
import threading

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

debug = logging.getLogger("scoreboard")

class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, scoreboard_config, scheduler_manager):
        super().__init__()
        self.scoreboard_config = scoreboard_config
        self.scheduler_manager = scheduler_manager

    def on_modified(self, event):
        # Only react if the file modified is config.json
        config_path = self.scoreboard_config.config_file_path
        if event.src_path == config_path:
            debug.info(f"Detected change in {event.src_path}, attempting to reload config...")
            self.scoreboard_config._reload_config()
            self.scheduler_manager.schedule_jobs()

def start_config_watcher(scoreboard_config, scheduler_manager):
    """
    Start a watchdog observer thread on config/config.json for changes,
    calling _reload_config if file is reloaded and validated.
    """
    import os
    config_path = scoreboard_config.config_file_path
    config_dir = os.path.dirname(config_path)
    event_handler = ConfigReloadHandler(scoreboard_config, scheduler_manager)
    observer = Observer()
    observer.schedule(event_handler, path=config_dir, recursive=False)
    thread = threading.Thread(target=observer.start, daemon=True)
    thread.start()
    debug.info(f"Started watchdog thread for {config_path}")
    return observer, thread
