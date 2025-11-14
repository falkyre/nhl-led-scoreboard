import logging
import threading
import queue

from driver import is_hardware

sb_logger = logging.getLogger("scoreboard")

class ThreadManager:
    def __init__(self, data, matrix, sleep_event, sb_queue, screensaver):
        self.data = data
        self.matrix = matrix
        self.sleep_event = sleep_event
        self.sb_queue = sb_queue
        self.screensaver = screensaver
        self.threads = {
            "motionsensor": None,
            "mqtt": None,
            "pushbutton": None
        }

    def update_threads(self):
        """
        Checks the config and starts threads if they are enabled and not already running.
        """
        from driver import is_hardware

        # Motion Sensor Thread
        if self.data.config.screensaver_motionsensor and is_hardware():
            if self.threads["motionsensor"] is None or not self.threads["motionsensor"].is_alive():
                try:
                    from sbio.motionsensor import Motion
                    motionsensor = Motion(self.data, self.matrix, self.sleep_event, self.data.scheduler, self.screensaver)
                    motionsensor_thread = threading.Thread(target=motionsensor.run, args=())
                    motionsensor_thread.daemon = True
                    motionsensor_thread.start()
                    self.threads["motionsensor"] = motionsensor_thread
                    sb_logger.info("Motion sensor thread started.")
                except Exception as e:
                    sb_logger.error(f"Failed to start motion sensor thread: {e}")
        
        # MQTT Thread
        if self.data.config.mqtt_enabled:
            if self.threads["mqtt"] is None or not self.threads["mqtt"].is_alive():
                try:
                    from sbio.sbMQTT import sbMQTT
                    sbmqtt = sbMQTT(self.data, self.matrix, self.sleep_event, self.sb_queue, self.screensaver)
                    mqtt_thread = threading.Thread(target=sbmqtt.run, args=())
                    mqtt_thread.daemon = True
                    mqtt_thread.start()
                    self.threads["mqtt"] = mqtt_thread
                    sb_logger.info("MQTT thread started.")
                except ImportError:
                    sb_logger.error("MQTT is enabled in config, but 'paho-mqtt' is not installed.")
                except Exception as e:
                    sb_logger.error(f"Failed to start MQTT thread: {e}")

        # Pushbutton Thread
        if self.data.config.pushbutton_enabled and is_hardware():
            if self.threads["pushbutton"] is None or not self.threads["pushbutton"].is_alive():
                try:
                    from sbio.pushbutton import PushButton
                    pushbutton = PushButton(self.data, self.matrix, self.sleep_event)
                    pushbutton_thread = threading.Thread(target=pushbutton.run, args=())
                    pushbutton_thread.daemon = True
                    pushbutton_thread.start()
                    self.threads["pushbutton"] = pushbutton_thread
                    sb_logger.info("Pushbutton thread started.")
                except Exception as e:
                    sb_logger.error(f"Failed to start pushbutton thread: {e}")

