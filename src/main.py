import logging
import queue
import sys
import threading
from importlib import metadata
from pathlib import Path

import tzlocal
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.schedulers.background import BackgroundScheduler
from rich.logging import RichHandler
from rich.traceback import install

import debug
import driver
from data.config_watcher import start_config_watcher, start_plugin_config_watcher
from data.data import Data
from data.scheduler import SchedulerManager
from data.scoreboard_config import ScoreboardConfig
from renderer.loading_screen import Loading
from renderer.main import MainRenderer
from renderer.matrix import Matrix
from utils import args, led_matrix_options, sb_cache, scheduler_event_listener, stop_splash_service

install(show_locals=True)

SCRIPT_NAME = "NHL-LED-SCOREBOARD"

try:
    SCRIPT_VERSION = metadata.version(SCRIPT_NAME)
except metadata.PackageNotFoundError:
    with open(Path(__file__).parent / ".." / "VERSION") as f:
        SCRIPT_VERSION = f.read().strip()

# Initialize the logger with default settings
# If loglevel is provided on command line, use it from the start
if args().loglevel:
    debug.setup_logger(loglevel=args().loglevel, debug=(args().loglevel.lower() == 'debug'), logtofile=args().logtofile)
else:
    debug.setup_logger(logtofile=args().logtofile)

sb_logger = logging.getLogger("scoreboard")

# Conditionally load the appropriate driver classes and set the global driver mode based on command line flags

if args().emulated:
    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions

    driver.mode = driver.DriverMode.SOFTWARE_EMULATION
    RGBME_logger = logging.getLogger("RGBME")
    RGBME_logger.propagate = False
    RGBME_logger.addHandler(RichHandler(rich_tracebacks=True))

else:
    try:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions  # type: ignore

        from utils import stop_splash_service

        driver.mode = driver.DriverMode.HARDWARE
    except ImportError:
        from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions  # noqa: F401

        driver.mode = driver.DriverMode.SOFTWARE_EMULATION

def run():
    # Get supplied command line arguments

    commandArgs = args()
    if driver.is_hardware():
        # Kill the splash screen if active
        stop_splash_service()

    # Check for led configuration arguments
    matrixOptions = led_matrix_options(commandArgs)
    matrixOptions.drop_privileges = False

    if driver.is_emulated():
        # Set up favico and tab title for browser emulator
        matrixOptions.emulator_title = f"{SCRIPT_NAME} v{SCRIPT_VERSION}"
        matrixOptions.icon_path = (Path(__file__).parent / ".." / "assets" / "images" / "favicon.ico").resolve()
        sb_logger.debug(matrixOptions.emulator_title)
        sb_logger.debug(f"Favicon path: {matrixOptions.icon_path}")

    # Initialize the matrix
    matrix = Matrix(RGBMatrix(options = matrixOptions))

    loading = Loading(matrix,SCRIPT_VERSION)
    loading.render()

    # Read scoreboard options from config.json if it exists
    config = ScoreboardConfig("config", commandArgs, (matrix.width, matrix.height))

    # This data will get passed throughout the entirety of this program.
    # It initializes all sorts of things like current season, teams, helper functions

    data = Data(config)

    #If we pass the logging arguments on command line, override what's in the config.json, else use what's in
    # config.json (color will always be false in config.json)
    if commandArgs.loglevel is not None:
        debug.set_debug_status(config,loglevel=commandArgs.loglevel,logtofile=commandArgs.logtofile)
    else:
        debug.set_debug_status(config,loglevel=config.loglevel,logtofile=commandArgs.logtofile)

    # Print some basic info on startup
    sb_logger.info("{} - v{} ({}x{})".format(SCRIPT_NAME, SCRIPT_VERSION, matrix.width, matrix.height))

    if data.latlng is not None:
        sb_logger.info(data.latlng_msg)
    else:
        sb_logger.error("Unable to find your location.")

    # Event used to sleep when rendering
    # Allows Web API (coming in V2) and pushbutton to cancel the sleep
    # Will also allow for weather alert to interrupt display board if you want
    sleepEvent = threading.Event()

    # Start task scheduler, used for UpdateChecker and screensaver, forecast, dimmer and weather and board plugins
    scheduler = BackgroundScheduler(timezone=str(tzlocal.get_localzone()), job_defaults={'misfire_grace_time': None})
    scheduler.add_listener(scheduler_event_listener, EVENT_JOB_MISSED | EVENT_JOB_ERROR)
    scheduler.start()

    # Add APScheduler to data object so it's accessible throughout the application
    data.scheduler = scheduler

    # Any tasks that are scheduled go below this line
    scheduler_manager = SchedulerManager(data, matrix, sleepEvent)
    screensaver = scheduler_manager.schedule_jobs()

    observer, watcher_thread, config_handler = start_config_watcher(config, scheduler_manager)
    sb_logger.info("ScoreboardConfig loaded; watcher active for config/config.json changes.")

    if driver.is_hardware():
        from sbio.pushbutton import PushButton
        from sbio.motionsensor import Motion
        
        if data.config.screensaver_motionsensor:
            motionsensor = Motion(data,matrix,sleepEvent,scheduler,screensaver)
            motionsensorThread = threading.Thread(target=motionsensor.run, args=())
            motionsensorThread.daemon = True
            motionsensorThread.start()

        if data.config.pushbutton_enabled:
            pushbutton = PushButton(data,matrix,sleepEvent)
            pushbuttonThread = threading.Thread(target=pushbutton.run, args=())
            pushbuttonThread.daemon = True
            pushbuttonThread.start()

    mqtt_enabled = data.config.mqtt_enabled
    # Create a queue for scoreboard events and info to be sent to an MQTT broker
    sbQueue = queue.Queue()
    pahoAvail = False
    if mqtt_enabled:
        # Only import if we are actually using mqtt, that way paho_mqtt doesn't need to be installed
        try:
            from sbio.sbMQTT import sbMQTT
            pahoAvail = True
        except Exception as e:
            sb_logger.error("MQTT (paho-mqtt): is disabled.  Unable to import module: {}  Did you install paho-mqtt?".format(e))  # noqa: E501
            pahoAvail = False

        if pahoAvail:
            sbmqtt = sbMQTT(data,matrix,sleepEvent,sbQueue,screensaver)
            sbmqttThread = threading.Thread(target=sbmqtt.run, args=())
            sbmqttThread.daemon = True
            sbmqttThread.start()

    # Create the MainRenderer and register it with the config watcher for board sync
    main_renderer = MainRenderer(matrix, data, sleepEvent, sbQueue)
    config_handler.set_main_renderer(main_renderer)

    # Start plugin config watcher to detect changes to plugin/builtin configs
    plugin_observer, plugin_thread, plugin_handler = start_plugin_config_watcher(
        main_renderer.boards.board_manager
    )
    sb_logger.info("Plugin config watcher active for board config changes.")

    # Start the render loop
    main_renderer.render()


if __name__ == "__main__":
    try:
        run()

    except KeyboardInterrupt:
        sb_logger.info("Exiting NHL-LED-SCOREBOARD")
        sb_cache.close()
        sys.exit(0)
