import json
import logging
from datetime import datetime

import httpx

from api.weather.wx_utils import degrees_to_direction, dew_point, get_csv, temp_f, usaheatindex, wind_chill, wind_kmph
from utils import sb_cache

debug = logging.getLogger("scoreboard")

class owmWxWorker(object):
    def __init__(self, data, scheduler):
        self.data = data
        self.weather_frequency = data.config.weather_update_freq
        self.time_format = data.config.time_format
        self.icons = get_csv("ecIcons_utf8.csv")
        self.apikey = data.config.weather_owm_apikey
        self.network_issues = False

        scheduler.add_job(self.getWeather, 'interval', minutes=self.weather_frequency, jitter=60, id='owmWeather')

        if self.data.config.weather_units.lower() not in ("metric", "imperial"):
            debug.info("Weather units not set correctly, defaulting to imperial")
            self.data.config.weather_units = "imperial"

        self.getWeather()

    def getWeather(self):
        if self.data.config.weather_units == "metric":
           self.data.wx_units = ["C", "kph", "mm", "miles", "hPa", "ca"]
        else:
            self.data.wx_units = ["F", "mph", "in", "miles", "MB", "us"]

        lat = self.data.latlng[0]
        lon = self.data.latlng[1]
        try:
            # Check cache first
            wx_cache, expiration_time = sb_cache.get("weather", expire_time=True)
            if wx_cache is None:
                debug.info("Refreshing OWM current observations weather")

                # Fetch weather data using httpx
                url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&units={self.data.config.weather_units}&appid={self.apikey}&exclude=minutely,hourly,daily,alerts"
                response = httpx.get(url)
                wx = response.json()

                # If the API request fails, raise an error
                if response.status_code != 200:
                    raise Exception(f"Error fetching weather data: {response.status_code} - {response.text}")

                self.network_issues = False
                self.data.wx_updated = True

                # Store in cache and expire after weather_frequency minutes less 1 second
                expiretime = (self.weather_frequency * 60) - 1
                sb_cache.set("weather", json.dumps(wx, indent=4), expire=expiretime)
            else:
                current_time = datetime.now().timestamp()
                remaining_time_seconds = int(max(0, int(expiration_time) - current_time))

                debug.info(f"Loading weather from cache... cache expires in {remaining_time_seconds} seconds")
                wx = json.loads(wx_cache)
                self.network_issues = False
                self.data.wx_updated = True

        except Exception as e:
            debug.error(f"Unable to get OWM data error: {e}")
            self.data.wx_updated = False
            self.network_issues = True
            pass

        if not self.network_issues:
            wx_timestamp = datetime.now().strftime("%m/%d %H:%M" if self.time_format == "%H:%M" else "%m/%d %I:%M %p")
            wx_code = wx.get("current").get("weather")[0].get("id")
            owm_icon = self.getWeatherIcon(wx_code)

            #Get condition and icon from dictionary
            for row in range(len(self.icons)):
                if int(self.icons[row]["OWMCode"]) == owm_icon:
                    wx_icon = self.icons[row]['font']
                    break
                else:
                    wx_icon = '\uf07b'

            wx_summary = wx.get("current").get("weather")[0].get("description")

            owm_windspeed = wx.get("current").get("wind_speed")
            owm_windgust = wx.get("current").get("wind_gust", 0)

            # Convert m/s to km/h or mph
            if self.data.config.weather_units == "metric":
                owm_windspeed = wind_kmph(owm_windspeed)
                owm_windgust = wind_kmph(owm_windgust)

            # Wind direction
            owm_winddir = wx.get("current").get("wind_deg", 0.0)
            winddir = degrees_to_direction(owm_winddir)

            wx_windgust = str(round(owm_windgust, 1)) + self.data.wx_units[1]
            wx_windspeed = str(round(owm_windspeed, 1)) + self.data.wx_units[1]

            # Temperature data
            owm_temp = wx.get("current")['temp']
            owm_app_temp = wx.get("current")['feels_like']

            if self.data.config.weather_units == "metric":
                check_windchill = 10.0
            else:
                check_windchill = 50.0

            if owm_app_temp is None:
                if float(owm_temp) < check_windchill:
                    windchill = round(wind_chill(float(owm_temp), float(owm_windspeed), "mps"), 1)
                    wx_app_temp = str(windchill) + self.data.wx_units[0]
                    wx_temp = str(round(owm_temp, 1)) + self.data.wx_units[0]
                else:
                    if self.data.config.weather_units == "metric":
                        wx_app_temp = wx.get('main')['humidity']
                    else:
                        wx_app_temp = wx.get('main')['heat_index']
                        if wx_app_temp is None:
                            app_temp = usaheatindex(float(owm_temp), wx.get('main')['humidity'])
                            wx_app_temp = str(round(temp_f(app_temp), 1)) + self.data.wx_units[0]
            else:
                wx_app_temp = str(round(owm_app_temp, 1)) + self.data.wx_units[0]

            wx_temp = str(round(owm_temp, 1)) + self.data.wx_units[0]
            wx_humidity = str(wx.get('current')['humidity']) + "%"

            # Other weather data
            wx_dewpoint = str(round(dew_point(float(owm_temp), wx.get('current')['humidity']), 1)) + self.data.wx_units[0]
            wx_pressure = str(wx.get('current')['pressure']) + " " + self.data.wx_units[4]

            vis_distance = wx.get('visibility', 10000)  # Default to 10km
            if self.data.config.weather_units == "metric":
                owm_visibility = round(vis_distance / 1000, 1)
                wx_visibility = str(owm_visibility) + " km"
            else:
                owm_visibility = round(vis_distance * 0.000621371, 1)
                wx_visibility = str(owm_visibility) + " mi"

            self.data.wx_current = [wx_timestamp, wx_icon, wx_summary, wx_temp, wx_app_temp, wx_humidity, wx_dewpoint]
            self.data.wx_curr_wind = [wx_windspeed, winddir[0], winddir[1], wx_windgust, wx_pressure, '\uf07b', wx_visibility]

            debug.info(self.data.wx_current)
            debug.info(self.data.wx_curr_wind)

    def getWeatherIcon(self, wx_code):
        # Map the OpenWeatherMap weather codes to icons
        if wx_code in range(200, 299):
            return 200  # Thunderstorm
        elif wx_code in range(300, 399):
            return 300  # Drizzle
        elif wx_code in range(500, 599):
            return 500  # Rain
        elif wx_code in range(600, 699):
            return 600  # Snow
        elif wx_code in range(700, 799):
            return 741  # Atmosphere
        elif wx_code == 800:
            return 800  # Clear Sky
        elif wx_code == 801:
            return 801  # Few Clouds
        else:
            return wx_code  # Default icon for other conditions
