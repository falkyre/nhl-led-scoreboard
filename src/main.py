# ruff: noqa: E402
"""NHL LED Scoreboard - Main Entry Point

This module initializes the LED matrix hardware, drops root privileges,
then imports and runs the main application logic.

Import order is critical:
1. Minimal imports for hardware initialization (as root)
2. Initialize hardware and drop privileges
3. Import remaining modules (as normal user, generating cache files with correct permissions)
"""

import os
import pwd
import sys
from pathlib import Path


def drop_privileges(to_user=None, umask=0o002):
    """Permanently drop privileges to `to_user` (hard drop; no way back).

    Args:
        to_user: Username to drop privileges to. If None, auto-detects the user who invoked sudo.
                Falls back to 'rpi' if detection fails.
        umask: File creation mask to set after dropping privileges.
    """
    if os.geteuid() != 0:
        # Not root → nothing to do
        return

    # Auto-detect the original user if not specified
    if to_user is None:
        # Try SUDO_USER first (most reliable when using sudo)
        to_user = os.environ.get('SUDO_USER')

        # Fallback to SUDO_UID if SUDO_USER not available
        if not to_user and 'SUDO_UID' in os.environ:
            try:
                pw = pwd.getpwuid(int(os.environ['SUDO_UID']))
                to_user = pw.pw_name
            except (ValueError, KeyError):
                pass

        # Final fallback to 'rpi' if we can't detect the original user
        if not to_user:
            to_user = 'rpi'
            print(f"Warning: Could not detect original user, falling back to '{to_user}'")

    try:
        pw = pwd.getpwnam(to_user)
    except KeyError:
        print(f"ERROR: User '{to_user}' does not exist on this system")
        sys.exit(1)

    target_uid, target_gid = pw.pw_uid, pw.pw_gid

    # Initialize groups for the user, then drop GID/UID
    os.setgid(target_gid)
    try:
        os.initgroups(pw.pw_name, target_gid)
    except Exception:
        # Fallback if initgroups not available
        os.setgroups([target_gid])
    os.setuid(target_uid)

    # Cooperative perms for new files/dirs
    os.umask(umask)

    # Safety: ensure we're no longer privileged
    assert os.geteuid() == target_uid and os.getegid() == target_gid


# Minimal imports needed for hardware initialization and argument parsing
import driver
from utils import args, led_matrix_options, stop_splash_service

# Get command line arguments early
commandArgs = args()

# Conditionally load the appropriate driver classes based on command line flags
if commandArgs.emulated:
    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
    driver.mode = driver.DriverMode.SOFTWARE_EMULATION
else:
    try:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions  # type: ignore
        driver.mode = driver.DriverMode.HARDWARE
    except ImportError:
        from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions  # noqa: F401
        driver.mode = driver.DriverMode.SOFTWARE_EMULATION


def initialize_hardware():
    """Initialize LED matrix hardware as root (if needed), then return matrix object."""
    from importlib import metadata

    SCRIPT_NAME = "NHL-LED-SCOREBOARD"

    try:
        SCRIPT_VERSION = metadata.version(SCRIPT_NAME)
    except metadata.PackageNotFoundError:
        with open(Path(__file__).parent / ".." / "VERSION") as f:
            SCRIPT_VERSION = f.read().strip()

    if driver.is_hardware():
        # Kill the splash screen if active
        stop_splash_service()

    # Check for led configuration arguments
    matrixOptions = led_matrix_options(commandArgs)
    matrixOptions.drop_privileges = False  # We'll handle privilege drop ourselves

    if driver.is_emulated():
        # Set up favico and tab title for browser emulator
        matrixOptions.emulator_title = f"{SCRIPT_NAME} v{SCRIPT_VERSION}"
        matrixOptions.icon_path = (Path(__file__).parent / ".." / "assets" / "images" / "favicon.ico").resolve()

    # Import Matrix class and initialize hardware
    from renderer.matrix import Matrix
    matrix = Matrix(RGBMatrix(options=matrixOptions))

    return matrix, SCRIPT_VERSION


def run():
    """Main application entry point."""
    # Step 1: Initialize hardware as root (if needed)
    matrix, SCRIPT_VERSION = initialize_hardware()

    # Step 2: Drop privileges BEFORE importing the rest of the application
    # This ensures all subsequent imports generate cache files as the normal user
    if driver.is_hardware():
        drop_privileges()

    # Step 3: NOW import everything else - cache files will be owned by the normal user
    import asyncio
    import logging
    import queue
    import threading

    import tzlocal
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
    from apscheduler.schedulers.background import BackgroundScheduler
    from env_canada import ECWeather
    from rich.logging import RichHandler
    from rich.traceback import install

    import debug
    from api.weather.ecAlerts import ecWxAlerts
    from api.weather.ecWeather import ecWxWorker
    from api.weather.nwsAlerts import nwsWxAlerts
    from api.weather.owmWeather import owmWxWorker
    from api.weather.wxForecast import wxForecast
    from data.data import Data
    from data.scoreboard_config import ScoreboardConfig
    from renderer.loading_screen import Loading
    from renderer.main import MainRenderer
    from sbio.dimmer import Dimmer
    from sbio.screensaver import screenSaver
    from update_checker import UpdateChecker
    from utils import get_or_create_cache, scheduler_event_listener

    get_or_create_cache()  # Ensure cache is initialized after privilege drop

    # Enable rich tracebacks
    install(show_locals=True)

    # Initialize logging after privilege drop
    debug.setup_logger(logtofile=commandArgs.logtofile)
    sb_logger = logging.getLogger("scoreboard")

    # Set up emulator logger if needed
    if driver.is_emulated():
        RGBME_logger = logging.getLogger("RGBME")
        RGBME_logger.propagate = False
        RGBME_logger.addHandler(RichHandler(rich_tracebacks=True))

    # Log the privilege drop - show which user we're running as
    if driver.is_hardware():
        current_user = pwd.getpwuid(os.geteuid()).pw_name
        sb_logger.info("Privilege drop complete: running as user '%s' (uid=%s gid=%s)",
                   current_user, os.geteuid(), os.getegid())
    else:
        sb_logger.info("Running in emulation mode as user '%s' (uid=%s gid=%s)",
                   pwd.getpwuid(os.geteuid()).pw_name, os.geteuid(), os.getegid())

    # Print some basic info on startup
    sb_logger.info("{} - v{} ({}x{})".format("NHL-LED-SCOREBOARD", SCRIPT_VERSION, matrix.width, matrix.height))

    loading = Loading(matrix, SCRIPT_VERSION)
    loading.render()

    # Read scoreboard options from config.json if it exists
    config = ScoreboardConfig("config", commandArgs, (matrix.width, matrix.height))

    # This data will get passed throughout the entirety of this program.
    # It initializes all sorts of things like current season, teams, helper functions
    data = Data(config)

    if data.latlng is not None:
        sb_logger.info(data.latlng_msg)
    else:
        sb_logger.error("Unable to find your location.")

    # If we pass the logging arguments on command line, override what's in the config.json,
    # else use what's in config.json (color will always be false in config.json)
    if commandArgs.loglevel is not None:
        debug.set_debug_status(config, loglevel=commandArgs.loglevel, logtofile=commandArgs.logtofile)
    else:
        debug.set_debug_status(config, loglevel=config.loglevel, logtofile=commandArgs.logtofile)

    # Event used to sleep when rendering
    # Allows Web API (coming in V2) and pushbutton to cancel the sleep
    # Will also allow for weather alert to interrupt display board if you want
    sleepEvent = threading.Event()

    # Start task scheduler, used for UpdateChecker and screensaver, forecast, dimmer and weather
    scheduler = BackgroundScheduler(timezone=str(tzlocal.get_localzone()), job_defaults={"misfire_grace_time": None})
    scheduler.add_listener(scheduler_event_listener, EVENT_JOB_MISSED | EVENT_JOB_ERROR)
    scheduler.start()

    # Add APScheduler to data object so it's accessible throughout the applicatoion
    data.scheduler = scheduler

    # Any tasks that are scheduled go below this line

    # Make sure we have a valid location for the data.latlng as the geocode can return a None
    # If there is no valid location, skip the weather boards

    # Create EC data feed handler
    if data.config.weather_enabled or data.config.wxalert_show_alerts:
        if data.config.weather_data_feed.lower() == "ec" or data.config.wxalert_alert_feed.lower() == "ec":
            data.ecData = ECWeather(coordinates=(tuple(data.latlng)))
            try:
                asyncio.run(data.ecData.update())
            except Exception as e:
                sb_logger.error("Unable to connect to EC .. will try on next refresh : {}".format(e))

    if data.config.weather_enabled:
        if data.config.weather_data_feed.lower() == "ec":
            ecWxWorker(data, scheduler)
        elif data.config.weather_data_feed.lower() == "owm":
            owmWxWorker(data, scheduler)
        else:
            sb_logger.error("No valid weather providers selected, skipping weather feed")
            data.config.weather_enabled = False

    if data.config.wxalert_show_alerts:
        if data.config.wxalert_alert_feed.lower() == "ec":
            ecWxAlerts(data, scheduler, sleepEvent)
        elif data.config.wxalert_alert_feed.lower() == "nws":
            nwsWxAlerts(data, scheduler, sleepEvent)
        else:
            debug.error("No valid weather alerts providers selected, skipping alerts feed")
            data.config.weather_show_alerts = False

    if data.config.weather_forecast_enabled and data.config.weather_enabled:
        wxForecast(data, scheduler)
    #
    # Run check for updates against github on a background thread on a scheduler
    #
    if commandArgs.updatecheck:
        data.UpdateRepo = commandArgs.updaterepo
        UpdateChecker(data, scheduler, commandArgs.ghtoken)

    # If the driver is running on actual hardware, these files contain libs that should be installed.
    # For other platforms, they probably don't exist and will crash.
    screensaver = None

    if data.config.dimmer_enabled:
        Dimmer(data, matrix, scheduler)

    if data.config.screensaver_enabled:
        screensaver = screenSaver(data, matrix, sleepEvent, scheduler)

    if driver.is_hardware():
        from sbio.motionsensor import Motion
        from sbio.pushbutton import PushButton

        if data.config.screensaver_motionsensor:
            motionsensor = Motion(data, matrix, sleepEvent, scheduler, screensaver)
            motionsensorThread = threading.Thread(target=motionsensor.run, args=())
            motionsensorThread.daemon = True
            motionsensorThread.start()

        if data.config.pushbutton_enabled:
            pushbutton = PushButton(data, matrix, sleepEvent)
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
            sb_logger.error(
                "MQTT (paho-mqtt): is disabled.  Unable to import module: {}  Did you install paho-mqtt?".format(e)
            )
            pahoAvail = False

        if pahoAvail:
            sbmqtt = sbMQTT(data, matrix, sleepEvent, sbQueue, screensaver)
            sbmqttThread = threading.Thread(target=sbmqtt.run, args=())
            sbmqttThread.daemon = True
            sbmqttThread.start()

    MainRenderer(matrix, data, sleepEvent, sbQueue).render()


if __name__ == "__main__":
    try:
        run()

    except KeyboardInterrupt:
        print("Exiting NHL-LED-SCOREBOARD\n")
        from utils import get_or_create_cache
        get_or_create_cache().close()
        sys.exit(0)
