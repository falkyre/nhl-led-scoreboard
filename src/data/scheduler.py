import asyncio
import importlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from env_canada import ECWeather

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


def _resolve_callable(ref: Any) -> Optional[Callable]:
    """
    Resolve a callable reference.

    Accepts:
      - an actual callable (returned as-is)
      - a string reference in one of the common formats:
         - "package.module:callable"
         - "package.module.callable"
         - "package.module", when that module exposes a "main" callable (fallback)

    Returns a callable or None if resolution fails.
    """
    if callable(ref):
        return ref

    if not isinstance(ref, str):
        return None

    ref_str = ref.strip()
    # Try module:attr form first (common in APScheduler serialization)
    if ":" in ref_str:
        module_name, attr = ref_str.split(":", 1)
    elif "." in ref_str:
        # split last segment as attribute
        parts = ref_str.rsplit(".", 1)
        if len(parts) == 2:
            module_name, attr = parts
        else:
            module_name, attr = ref_str, None
    else:
        module_name, attr = ref_str, None

    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        sb_logger.debug(f"Unable to import module {module_name} while resolving callable {ref_str}: {e}")
        return None

    if attr:
        try:
            return getattr(module, attr)
        except Exception as e:
            sb_logger.debug(f"Module {module_name} does not have attribute {attr}: {e}")
            return None

    # If no attribute specified, try to return module.main (common pattern) or None
    if hasattr(module, "main") and callable(getattr(module, "main")):
        return getattr(module, "main")

    return None


class SchedulerManager:
    # Known job ids used by various workers/managers in the system.
    # screenSaver uses ids that start with "screenSaver" (e.g. "screenSaverON"/"screenSaverOFF")
    KNOWN_JOB_IDS = {
        "ecWxWorker": "ecWeather",
        "owmWxWorker": "owmWeather",
        "ecWxAlerts": "ecAlerts",
        "nwsWxAlerts": "nwsAlerts",
        "wxForecast": "forecast",
        "UpdateChecker": "updatecheck",
        "Dimmer": "Dimmer",
        "screenSaver_prefix": "screenSaver",
    }

    def __init__(self, data, matrix, sleep_event):
        self.data = data
        self.matrix = matrix
        self.sleep_event = sleep_event
        self.commandArgs = args()

    def _get_existing_job_ids(self) -> List[str]:
        """Return list of job ids currently in the scheduler (defensive)."""
        jobs = self.list_jobs()
        return [j["id"] for j in jobs if j.get("id")]

    def _job_exists(self, job_id: str, existing_ids: Optional[List[str]] = None) -> bool:
        """Check whether a job with the given id already exists in the scheduler."""
        if existing_ids is None:
            existing_ids = self._get_existing_job_ids()
        return job_id in existing_ids

    def _job_prefix_exists(self, prefix: str, existing_ids: Optional[List[str]] = None) -> bool:
        """Check whether any job id starts with the given prefix."""
        if existing_ids is None:
            existing_ids = self._get_existing_job_ids()
        return any(jid.startswith(prefix) for jid in existing_ids if jid)

    def schedule_jobs(self, jobs_json: Optional[str] = None) -> Optional[Any]:
        """
        Schedule jobs.

        If jobs_json is None, schedule jobs normally (the previous behavior) but
        only add jobs that are not already present in the scheduler's jobstore.
        If jobs_json is a JSON string or a Python list, attempt to use the scheduler's
        import API (if present). If the scheduler does not expose an import API,
        reconstruct jobs from the JSON and add them via add_job.

        Returns:
            screensaver_manager object if a screensaver manager was created by this call,
            otherwise None. Note: if a screensaver job already existed and no new manager
            was created, None is returned.
        """
        sb_logger.info("Scheduling jobs...")

        screensaver_manager: Optional[Any] = None

        # Normalize jobs_json to Python list if provided
        jobs_list: Optional[List[Dict]] = None
        if jobs_json:
            if isinstance(jobs_json, str):
                try:
                    jobs_list = json.loads(jobs_json)
                except Exception as e:
                    sb_logger.error(f"Failed to decode jobs_json: {e}")
                    jobs_list = None
            elif isinstance(jobs_json, list):
                jobs_list = jobs_json
            else:
                sb_logger.error("jobs_json provided but is neither JSON string nor list; ignoring and using normal scheduling.")
                jobs_list = None

        # If jobs_list provided, try to import via scheduler API or reconstruct jobs
        if jobs_list:
            sb_logger.info("Scheduling jobs from provided job list (import mode).")
            # Clear existing jobs first to mirror import intent (import should replace)
            try:
                self.data.scheduler.remove_all_jobs()
            except Exception as e:
                sb_logger.debug(f"Unable to remove all jobs before import: {e}")

            # If the scheduler provides a direct import API, use it
            if hasattr(self.data.scheduler, "import_jobs"):
                try:
                    # Many scheduler implementations expect an iterable of serialized jobs
                    self.data.scheduler.import_jobs(jobs_list)
                    sb_logger.info("Imported jobs using scheduler.import_jobs()")
                except Exception as e:
                    sb_logger.error(f"Scheduler.import_jobs() failed: {e}. Falling back to manual add.")
                    self._manual_add_jobs(jobs_list)
            else:
                # Fallback: reconstruct jobs manually
                self._manual_add_jobs(jobs_list)

            # After import/add, log what jobs are scheduled
            try:
                sb_logger.debug(f"Scheduled jobs after import: {self.list_jobs()}")
            except Exception:
                sb_logger.debug("Scheduled jobs after import: (unable to list jobs)")
            sb_logger.info("Jobs scheduled (import mode).")
            # In import mode we can't reliably reconstruct a screensaver manager to return
            return None

        # No jobs_json provided: add jobs only if they are not already present.
        sb_logger.info("Scheduling jobs using normal configuration (adding missing jobs only).")

        # Build current job id set once and keep it updated as we add jobs
        existing_ids = self._get_existing_job_ids()
        sb_logger.debug(f"Existing job ids before scheduling: {existing_ids}")

        # WEATHER PROVIDERS / ALERTS
        if self.data.config.weather_enabled or self.data.config.wxalert_show_alerts:
            # If EC feed is configured for either weather or alerts we attempt an immediate EC
            # data fetch (this does not schedule a job by itself)
            if (
                self.data.config.weather_data_feed.lower() == "ec"
                or self.data.config.wxalert_alert_feed.lower() == "ec"
            ):
                self.data.ecData = ECWeather(coordinates=(tuple(self.data.latlng)))
                try:
                    asyncio.run(self.data.ecData.update())
                except Exception as e:
                    sb_logger.error(f"Unable to connect to EC .. will try on next refresh : {e}")

        # weather worker
        if self.data.config.weather_enabled:
            if self.data.config.weather_data_feed.lower() == "ec":
                job_id = self.KNOWN_JOB_IDS["ecWxWorker"]
                if not self._job_exists(job_id, existing_ids):
                    ecWxWorker(self.data, self.data.scheduler)
                    existing_ids.append(job_id)
                    sb_logger.info(f"Scheduled EC weather worker (id={job_id})")
                else:
                    sb_logger.debug(f"EC weather worker already scheduled (id={job_id}), skipping add.")
            elif self.data.config.weather_data_feed.lower() == "owm":
                job_id = self.KNOWN_JOB_IDS["owmWxWorker"]
                if not self._job_exists(job_id, existing_ids):
                    owmWxWorker(self.data, self.data.scheduler)
                    existing_ids.append(job_id)
                    sb_logger.info(f"Scheduled OWM weather worker (id={job_id})")
                else:
                    sb_logger.debug(f"OWM weather worker already scheduled (id={job_id}), skipping add.")
            else:
                sb_logger.error("No valid weather providers selected, skipping weather feed")
                self.data.config.weather_enabled = False

        # weather alerts
        if self.data.config.wxalert_show_alerts:
            if self.data.config.wxalert_alert_feed.lower() == "ec":
                job_id = self.KNOWN_JOB_IDS["ecWxAlerts"]
                if not self._job_exists(job_id, existing_ids):
                    ecWxAlerts(self.data, self.data.scheduler, self.sleep_event)
                    existing_ids.append(job_id)
                    sb_logger.info(f"Scheduled EC alerts worker (id={job_id})")
                else:
                    sb_logger.debug(f"EC alerts worker already scheduled (id={job_id}), skipping add.")
            elif self.data.config.wxalert_alert_feed.lower() == "nws":
                job_id = self.KNOWN_JOB_IDS["nwsWxAlerts"]
                if not self._job_exists(job_id, existing_ids):
                    nwsWxAlerts(self.data, self.data.scheduler, self.sleep_event)
                    existing_ids.append(job_id)
                    sb_logger.info(f"Scheduled NWS alerts worker (id={job_id})")
                else:
                    sb_logger.debug(f"NWS alerts worker already scheduled (id={job_id}), skipping add.")
            else:
                sb_logger.error("No valid weather alerts providers selected, skipping alerts feed")
                self.data.config.weather_show_alerts = False

        # weather forecast
        if self.data.config.weather_forecast_enabled and self.data.config.weather_enabled:
            job_id = self.KNOWN_JOB_IDS["wxForecast"]
            if not self._job_exists(job_id, existing_ids):
                wxForecast(self.data, self.data.scheduler)
                existing_ids.append(job_id)
                sb_logger.info(f"Scheduled weather forecast (id={job_id})")
            else:
                sb_logger.debug(f"Weather forecast already scheduled (id={job_id}), skipping add.")

        # update checker
        if self.commandArgs.updatecheck:
            job_id = self.KNOWN_JOB_IDS["UpdateChecker"]
            if not self._job_exists(job_id, existing_ids):
                self.data.UpdateRepo = self.commandArgs.updaterepo
                UpdateChecker(self.data, self.data.scheduler, self.commandArgs.ghtoken)
                existing_ids.append(job_id)
                sb_logger.info(f"Scheduled update checker (id={job_id})")
            else:
                sb_logger.debug(f"Update checker already scheduled (id={job_id}), skipping add.")

        # dimmer
        if self.data.config.dimmer_enabled:
            job_id = self.KNOWN_JOB_IDS["Dimmer"]
            if not self._job_exists(job_id, existing_ids):
                Dimmer(self.data, self.matrix, self.data.scheduler)
                existing_ids.append(job_id)
                sb_logger.info(f"Scheduled dimmer (id={job_id})")
            else:
                sb_logger.debug(f"Dimmer already scheduled (id={job_id}), skipping add.")

        # screensaver
        if self.data.config.screensaver_enabled:
            # screenSaver job ids use a prefix; check if any such job exists
            prefix = self.KNOWN_JOB_IDS["screenSaver_prefix"]
            if not self._job_prefix_exists(prefix, existing_ids):
                # create and keep a reference to the screensaver manager so it can be returned
                try:
                    screensaver_manager = screenSaver(self.data, self.matrix, self.sleep_event, self.data.scheduler)
                    existing_ids.append(prefix)
                    sb_logger.info("Scheduled screensaver (prefix=screenSaver)")
                except Exception as e:
                    sb_logger.error(f"Failed to create screensaver manager: {e}")
                    screensaver_manager = None
            else:
                sb_logger.debug("Screensaver job already scheduled (prefix=screenSaver), skipping add.")

        # Note: Motion sensor and MQTT startup have been removed from this module.
        # They should be started by the application boot logic (outside of schedule_jobs)
        # where their lifecycle can be managed separately from scheduler population.

        # Log the list of scheduled jobs at debug level after attempting to add missing jobs
        try:
            sb_logger.debug(f"Scheduled jobs after add/skip: {self.list_jobs()}")
        except Exception as e:
            sb_logger.debug(f"Scheduled jobs after add/skip: (unable to list jobs: {e})")

        sb_logger.info("Jobs scheduled.")

        # Return the screensaver manager (or None) as requested.
        return screensaver_manager

    def _manual_add_jobs(self, jobs: List[Dict]):
        """
        Reconstruct and add jobs manually using scheduler.add_job for schedulers
        that don't expose an import API. This attempts to be compatible with
        common APScheduler exported job metadata.
        """
        for j in jobs:
            try:
                job_id = j.get("id")
                # APScheduler serialized jobs often use 'func_ref' or 'func' to indicate the callable
                func_ref = j.get("func_ref") or j.get("func") or j.get("funcname") or j.get("callable")
                func = _resolve_callable(func_ref)

                if func is None:
                    sb_logger.error(f"Could not resolve callable for job id {job_id} (ref={func_ref}); skipping job.")
                    continue

                # Trigger can be either a string like 'interval' or a dict with type and args
                trigger = None
                trigger_args = {}
                t = j.get("trigger")
                if isinstance(t, str):
                    trigger = t
                elif isinstance(t, dict):
                    # expect {'type': 'interval', ...}
                    trigger = t.get("type")
                    # copy other keys as trigger args
                    trigger_args = {k: v for k, v in t.items() if k != "type"}

                args = j.get("args") or []
                kwargs = j.get("kwargs") or {}

                # Add the job; APScheduler add_job accepts trigger as first or keyword arg
                add_kwargs = {}
                if job_id:
                    add_kwargs["id"] = job_id
                # Respect replace_existing if present
                if "replace_existing" in j:
                    add_kwargs["replace_existing"] = bool(j.get("replace_existing"))

                # name (scheduler-dependent)
                if "name" in j:
                    add_kwargs["name"] = j.get("name")

                sb_logger.debug(f"Adding job from import: id={job_id}, func={func}, trigger={trigger}, trigger_args={trigger_args}, args={args}, kwargs={kwargs}")  # noqa: E501

                if trigger:
                    self.data.scheduler.add_job(func, trigger, args=args, kwargs=kwargs, **trigger_args, **add_kwargs)
                else:
                    # If no trigger provided, attempt to add as a regular callable (may execute immediately or raise)
                    self.data.scheduler.add_job(func, args=args, kwargs=kwargs, **add_kwargs)

                sb_logger.info(f"Added imported job {job_id}")
            except Exception as e:
                sb_logger.error(f"Failed to add imported job {j.get('id', '(unknown)')}: {e}")

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

    def remove_job(self, job_id):
        """
        Removes a job from the scheduler by its job_id.

        This is useful for boards that schedule background jobs and need to
        clean them up when the board is unloaded.

        Parameters:
            job_id (str): The job id to remove.
        Returns:
            bool: True if removed, False if failed.
        """
        sb_logger.info(f"Removing job: {job_id}")
        try:
            self.data.scheduler.remove_job(job_id)
            sb_logger.info(f"Job {job_id} removed.")
            return True
        except Exception as e:
            sb_logger.error(f"Could not remove job {job_id}: {e}")
            return False

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

    def resume_job(self, job_id):
        """
        Resumes a paused job by its job_id.

        Parameters:
            job_id (str): The job id to resume.
        Returns:
            bool: True if resumed, False if failed.
        """
        sb_logger.info(f"Resuming job: {job_id}")
        try:
            self.data.scheduler.resume_job(job_id)
            sb_logger.info(f"Job {job_id} resumed.")
            return True
        except Exception as e:
            sb_logger.error(f"Could not resume job {job_id}: {e}")
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

    def list_jobs(self):
        """
        Return a list of scheduled jobs with basic metadata.

        The returned value is a list of dicts:
          - id: job id (if available)
          - next_run_time: next scheduled run time (if available)
          - trigger: trigger description / object (if available)

        This method is defensive: if the scheduler doesn't expose get_jobs()
        it will attempt common alternatives and always return a list.
        """
        try:
            # APScheduler provides get_jobs()
            if hasattr(self.data.scheduler, "get_jobs"):
                jobs = self.data.scheduler.get_jobs()
            # Some schedulers might expose jobs property
            elif hasattr(self.data.scheduler, "jobs"):
                jobs = getattr(self.data.scheduler, "jobs")
            else:
                sb_logger.debug("Scheduler does not provide job enumeration API.")
                return []

            job_list = []
            for job in jobs:
                job_list.append({
                    "id": getattr(job, "id", None),
                    "name": getattr(job, "name", None),
                    "next_run_time": getattr(job, "next_run_time", None),
                    "trigger": getattr(job, "trigger", None),
                })
            return job_list
        except Exception as e:
            sb_logger.error(f"Unable to list jobs: {e}")
            return []