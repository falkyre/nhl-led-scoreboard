import smbus2
import bme280
import debug
import datetime
import time
import requests
import sqlite3
from time import sleep

class envSensor(object):
    def __init__(self, data, sleepEvent):
        self.data = data
        self.sleepEvent = sleepEvent
        self.weather_frequency = data.config.weather_update_freq
        self.time_format = data.config.time_format
        self.altitude = 292 #altitude in office
        self.tempadj = 2.5 #adjustment for bme280 self heating
        self.port = 1
        self.address = 0x76
        self.bus = smbus2.SMBus(self.port)
        # For local storage
        self.dbfilename = '/home/dietpi/envsensor.sdb'
        self._create_table()
        self._create_indexes()

        # For thingspeak storage
        self.ts_api_key = "2VWPP22P04DS29VT"

        try:
            self.calibration_params = bme280.load_calibration_params(self.bus, self.address)
        except: 
            pass

    def _create_table(self):
        with sqlite3.connect(self.dbfilename) as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS samples ( \
                         id TEXT PRIMARY KEY, \
                         timestamp INTEGER, \
                         temperature REAL, \
                         pressure REAL, \
                         humidity REAL)")
            conn.commit()

    def _create_indexes(self):
        with sqlite3.connect(self.dbfilename) as conn:
            cur = conn.cursor()
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS \
                         idx_timestamp ON samples (timestamp)")
            conn.commit()

    def db_persist(self, data,pressure_sea):
        fields = [str(data.id), time.mktime(data.timestamp.timetuple()),
                  data.temperature - self.tempadj, data.pressure, data.humidity]

        with sqlite3.connect(self.dbfilename) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO samples VALUES (?,?,?,?,?)", fields)
            conn.commit()


    def ts_persist(self, data,pressure_sea):
        payload = {
            "api_key": self.ts_api_key,
            "field1": data.temperature - self.tempadj,
            "field2": data.humidity,
            "field3": data.pressure,
            "field4": pressure_sea
        }
        requests.post("https://api.thingspeak.com/update", payload)

    def run(self):

        while True:
            data = bme280.sample(self.bus, self.address, self.calibration_params)
            
            pressure_sea = data.pressure / pow(1 - (0.0065 * self.altitude) / (data.temperature + 0.0065 * self.altitude + 273.15), 5.257)

            #Save to local database
            self.db_persist(data,pressure_sea)

            #Save to thingspeak
            self.ts_persist(data,pressure_sea)

            # the compensated_reading class has the following attributes
            #print(data.id)
            #print(data.timestamp)
            #print(data.temperature)
            #print(data.pressure)
            #print(pressure_sea)
            #print(data.humidity)
            if self.data.config.weather_units == "metric":
                self.data.wx_units = ["C","kph","mm","miles","hPa","ca"]
            else:
                self.data.wx_units = ["F","mph","in","miles","MB","us"]

            if self.time_format == "%H:%M":
                wx_timestamp = datetime.datetime.now().strftime("%m/%d %H:%M")
            else:
                wx_timestamp = datetime.datetime.now().strftime("%m/%d %I:%M %p")

            #Convert readings to one decimal and add proper units
            wx_temp = str(round(data.temperature - self.tempadj,1)) + self.data.wx_units[0]
            wx_humidity = str(round(data.humidity,1)) + "%"
            wx_pressure = str(round(pressure_sea,1)) + " " + self.data.wx_units[4]

            self.data.wx_current_sensor = [wx_timestamp,wx_temp,wx_humidity,wx_pressure]

            debug.info(self.data.wx_current_sensor)


            sleep(60 * self.weather_frequency)

