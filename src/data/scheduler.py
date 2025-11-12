import asyncio
import logging

from env_canada import ECWeather

import driver
from api.weather.ecAlerts import ecWxAlerts
from api.weather.ecWeather import ecWxWorker
from api.weather.nwsAlerts import nwsWxAlerts
from api.weather.owmWeather import owmWxWorker
from api.weather.wxForecast import wxForecast
from sbio.dimmer import Dimmer
from sbio.screensaver import screenSaver
from update_checker import UpdateChecker
from utils import args

sb_logger = logging.getLogger("scoreboard")

class SchedulerManager:
    def __init__(self, data, matrix, sleep_event):
        self.data = data
        self.matrix = matrix
        self.sleep_event = sleep_event
        self.commandArgs = args()

    def schedule_jobs(self):
        sb_logger.info("Scheduling jobs...")
        self.data.scheduler.remove_all_jobs()

        if self.data.config.weather_enabled or self.data.config.wxalert_show_alerts:
            if self.data.config.weather_data_feed.lower() == "ec" or self.data.config.wxalert_alert_feed.lower() == "ec":  # noqa: E501
                self.data.ecData = ECWeather(coordinates=(tuple(self.data.latlng)))
                try:
                    asyncio.run(self.data.ecData.update())
                except Exception as e:
                    sb_logger.error(f"Unable to connect to EC .. will try on next refresh : {e}")

        if self.data.config.weather_enabled:
            if self.data.config.weather_data_feed.lower() == "ec":
                ecWxWorker(self.data, self.data.scheduler)
            elif self.data.config.weather_data_feed.lower() == "owm":
                owmWxWorker(self.data, self.data.scheduler)
            else:
                sb_logger.error("No valid weather providers selected, skipping weather feed")
                self.data.config.weather_enabled = False

        if self.data.config.wxalert_show_alerts:
            if self.data.config.wxalert_alert_feed.lower() == "ec":
                ecWxAlerts(self.data, self.data.scheduler, self.sleep_event)
            elif self.data.config.wxalert_alert_feed.lower() == "nws":
                nwsWxAlerts(self.data, self.data.scheduler, self.sleep_event)
            else:
                sb_logger.error("No valid weather alerts providers selected, skipping alerts feed")
                self.data.config.weather_show_alerts = False

        if self.data.config.weather_forecast_enabled and self.data.config.weather_enabled:
            wxForecast(self.data, self.data.scheduler)

        if self.commandArgs.updatecheck:
            self.data.UpdateRepo = self.commandArgs.updaterepo
            UpdateChecker(self.data, self.data.scheduler, self.commandArgs.ghtoken)

        if self.data.config.dimmer_enabled:
            Dimmer(self.data, self.matrix, self.data.scheduler)

        if self.data.config.screensaver_enabled:
            screenSaver(self.data, self.matrix, self.sleep_event, self.data.scheduler)

        if driver.is_hardware():
            if self.data.config.screensaver_motionsensor:
                from sbio.motionsensor import Motion
                screensaver_manager = screenSaver(self.data, self.matrix, self.sleep_event, self.data.scheduler)
                motion_sensor = Motion(self.data, self.matrix, self.sleep_event, self.data.scheduler, screensaver_manager)  # noqa: E501
                motion_sensor.start()

        if self.data.config.mqtt_enabled:
            try:
                from sbio.sbMQTT import sbMQTT
                screensaver_manager = screenSaver(self.data, self.matrix, self.sleep_event, self.data.scheduler)
                sbmqtt = sbMQTT(self.data, self.matrix, self.sleep_event, self.data.sbQueue, screensaver_manager)
                sbmqtt.start()
            except ImportError as e:
                sb_logger.error(f"MQTT (paho-mqtt): is disabled.  Unable to import module: {e}  Did you install paho-mqtt?")  # noqa: E501

        sb_logger.info("Jobs scheduled.")

    def add_job(self, func, trigger, **kwargs):
        """
        Adds a new job to the scheduler.

        Parameters:
            func (callable): The function to schedule.
            trigger (str): The type of trigger (e.g., 'interval', 'cron', etc.).
            kwargs: Any other arguments accepted by the scheduler's add_job.
        Returns:
            job: The scheduled job object.
        """
        sb_logger.info(f"Adding job: {func} with trigger: {trigger}, args: {kwargs}")
        try:
            job = self.data.scheduler.add_job(func, trigger, **kwargs)
            sb_logger.info(f"Job added: {job}")
            return job
        except Exception as e:
            sb_logger.error(f"Failed to add job: {e}")
            return None

    def pause_job(self, job_id):
        """
        Pauses a job by its job_id.
        
        Parameters:
            job_id (str): The job id to pause.
        Returns:
            bool: True if paused, False if failed.
        """
        sb_logger.info(f"Pausing job: {job_id}")
        try:
            self.data.scheduler.pause_job(job_id)
            sb_logger.info(f"Job {job_id} paused.")
            return True
        except Exception as e:
            sb_logger.error(f"Could not pause job {job_id}: {e}")
            return False

    def pause_all_jobs(self):
        """
        Pauses all scheduled jobs.
        """
        sb_logger.info("Pausing all jobs.")
        try:
            self.data.scheduler.pause()
            sb_logger.info("All jobs have been paused.")
            return True
        except Exception as e:
            sb_logger.error(f"Could not pause all jobs: {e}")
            return False