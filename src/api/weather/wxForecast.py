#from pyowm.owm import OWM
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from api.weather.wx_utils import get_csv

debug = logging.getLogger("scoreboard")

class wxForecast(object):
    def __init__(self, data, scheduler):

        self.data = data
        self.scheduler = scheduler
        self.weather_frequency = data.config.weather_update_freq
        self.time_format = data.config.time_format
        self.icons = get_csv("ecIcons_utf8.csv")
        self.network_issues = data.network_issues
        self.currdate = datetime.now()

        self.apikey = data.config.weather_owm_apikey

        self.max_days = data.config.weather_forecast_days
        self.show_today = data.config.weather_forecast_show_today

        #if self.data.config.weather_data_feed.lower() == "owm":
        #    self.owm = OWM(self.apikey)
        #    self.owm_manager = self.owm.weather_manager()

        # Get forecast for next day, every forecast_update hours

        hour_update = '*/' + str(self.data.config.weather_forecast_update)

        scheduler.add_job(self.getForecast, 'cron', hour=hour_update,minute=0,id='forecast')
        #Check every 5 mins for testing only
        #scheduler.add_job(self.GetForecast, 'cron', minute='*/5')

        nextrun = scheduler.get_job('forecast').next_run_time
        debug.info("Updating weather forecast every {} hour(s) starting @ {}".format((self.data.config.weather_forecast_update),nextrun.strftime("%H:%M")))
        #debug.info(scheduler.print_jobs())

        #Set up units [temp, wind speed,precip, storm distance]
        #Use these eventhough some are included in data feed
        if self.data.config.weather_units.lower() not in ("metric", "imperial"):
            debug.info("Weather units not set correctly, defaulting to imperial")
            self.data.config.weather_units="imperial"

        if self.data.config.weather_units == "metric":
            self.data.wx_units = ["C","kph","mm","miles","hPa","ca"]
        else:
            self.data.wx_units = ["F","mph","in","miles","MB","us"]

        #Get initial forecast
        self.getForecast()


    def getForecast(self):

        #self.data.wx_forecast = []
        wx_forecast = []
        icon_code = None
        summary = None
        temp_high = None
        temp_low = None
        self.currdate = datetime.now()

        # For testing
        #self.data.wx_forecast = [['Tue 08/25', 'Mainly Clear', '\uf02e', '-29C', '-14C'], ['Wed 08/26', 'Light Rain Shower', '\uf02b', '27C', '18C'], ['Thu 08/27', 'Clear', '\uf02e', '23C', '13C']]  # noqa: E501

        if self.data.config.weather_data_feed.lower() == "ec":
            debug.info("Refreshing EC daily weather forecast")
            try:
                asyncio.run(self.data.ecData.update())
            except Exception as e:
                debug.error("Unable to update EC forecast. Error: {}".format(e))

            forecasts = []
            forecasts = self.data.ecData.daily_forecasts
            debug.debug(f"EC forecast raw: {forecasts}")

            if len(forecasts) > 0:
                forecasts_updated = True
            else:
                forecasts_updated = False
                debug.error("EC Forecast not updated.... ")

            #Loop through the data and create the forecast
            #Number of days to add to current day for the date string, this will be incremented
            if self.show_today:
                index = 0
                forecast_day = 0
            else:
                index = 1
                forecast_day = 1
            while index <= self.max_days and forecasts_updated:
            #Create the date
                nextdate = self.currdate + timedelta(days=forecast_day)
                currdate_name = self.currdate.strftime("%A")
                nextdate_name = nextdate.strftime("%A")
                nextdate = nextdate.strftime("%a %m/%d")
                forecast_day += 1

                #Loop through forecast and get the day equal to nextdate_name
                for day_forecast in forecasts:
                    for k,v in day_forecast.items():
                        if k == "period" and v == nextdate_name:
                            summary = day_forecast['text_summary']
                            icon_code = day_forecast['icon_code']
                            temp_high = str(day_forecast['temperature']) + self.data.wx_units[0]
                            # Get the nextdate_name + " night"

                            night_forecast = next((sub for sub in forecasts if sub['period'] == nextdate_name + " night"), None)

                            temp_low = str(night_forecast['temperature']) + self.data.wx_units[0]
                            break
                        else:
                            if k == "period" and v == f"{currdate_name} night" and self.show_today:
                                debug.debug(f"Not {nextdate_name}, it's {v}")
                                summary = day_forecast['text_summary']
                                icon_code = day_forecast['icon_code']
                                temp_low = str(day_forecast['temperature']) + self.data.wx_units[0]
                                temp_high = "--" + self.data.wx_units[0]
                                debug.debug(f"Tonight's low temp: {temp_low}")
                                break

                if icon_code is None:
                    wx_icon = '\uf07b'
                    wx_summary = "N/A"
                    #debug.warning("Forecasts returned: {}".format(forecasts))
                else:
                    #Get condition and icon from dictionary
                    #debug.warning("icons length {}".format(len(self.icons)))
                    for row in range(len(self.icons)):
                        if int(self.icons[row]["ForecastCode"]) == int(icon_code):
                            wx_icon = self.icons[row]['font']
                            wx_summary = self.icons[row]['Description']
                            break
                        else:
                            wx_icon = '\uf07b'
                            wx_summary = "N/A"

                if wx_summary == "N/A":
                    debug.error("Icon not found in icon spreadsheet:  EC icon code: {} : EC Summary {}.".format(icon_code,summary))

                if self.show_today  and index == 0:
                    if self.currdate.hour > 18:
                        nextdate = "* Night *"
                    else:
                        nextdate = "* Today *"


                wx_forecast.append([nextdate,wx_summary,wx_icon,temp_high,temp_low])
                index += 1



        if self.data.config.weather_data_feed.lower() == "owm":
            debug.info("Refreshing OWM daily weather forecast")
            lat = self.data.latlng[0]
            lon = self.data.latlng[1]
            one_call = None

            try:
                url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&units={self.data.config.weather_units}&appid={self.apikey}&exclude=alerts,minutely,hourly,current"
                response = httpx.get(url)
                one_call = response.json()
                debug.debug(f"OWM forecast raw: {one_call}")

            except Exception as e:
                debug.error("Unable to get OWM data error:{0}".format(e))
                self.data.forecast_updated = False
                self.network_issues = True
                return

            if self.show_today:
                index = 0
            else:
                index=1

            #forecast = []
            while index <= self.max_days:
                nextdate = self.currdate + timedelta(days=index)
                nextdate = nextdate.strftime("%a %m/%d")
                icon_code = int(one_call.get("daily")[index].get("weather")[0].get("id"))
                summary = one_call.get("daily")[index].get("weather")[0].get("description")
                # This is a long descriptive summary, not sure if will add this as an option yet
                #summary = one_call.get("daily")[index].get("summary")

                temp_high = one_call.get("daily")[index].get("temp").get('max', None)
                temp_low = one_call.get("daily")[index].get("temp").get('min', None)

                #Round high and low temps to two digits only (ie 25 and not 25.61)
                temp_hi = str(round(float(temp_high))) + self.data.wx_units[0]
                temp_lo = str(round(float(temp_low))) + self.data.wx_units[0]

                if icon_code in range(200,299):
                    # Thunderstorm Class
                    owm_icon = 200
                elif icon_code in range(300,399):
                    # Drizzle Class
                    owm_icon = 300
                elif icon_code in range(500,599):
                    # Rain Class
                    owm_icon = 500
                elif icon_code in range(600,699):
                    # Rain Class
                    owm_icon = 600
                elif icon_code in range(700,741):
                    # Rain Class
                    owm_icon = 741
                elif icon_code in range(800,805):
                    # Rain Class
                    owm_icon = 801
                else:
                    owm_icon = icon_code

                #Get the icon, only for the day
                if icon_code is None:
                    wx_icon = '\uf07b'
                    wx_summary = "N/A"
                else:
                    #Get condition and icon from dictionary
                    for row in range(len(self.icons)):
                        if int(self.icons[row]["OWMCode"]) == owm_icon:
                            wx_icon = self.icons[row]['font']
                            wx_summary = self.icons[row]['Description']
                            break
                        else:
                            wx_icon = '\uf07b'
                            wx_summary = "N/A"

                if self.show_today and index == 0:
                    nextdate = "* Today *"

                wx_forecast.append([nextdate,summary,wx_icon,temp_hi,temp_lo])
                index += 1

        debug.info("New forecast: {}".format(wx_forecast))

        if self.data.wx_forecast != wx_forecast:
            debug.info("Forecast has changed and been updated....")
            self.data.wx_forecast = wx_forecast
        else:
            debug.info("Forecast has not changed, no update needed....")

        self.data.forecast_updated = True
        self.network_issues = False

        debug.info(self.data.wx_forecast)
        nextrun = self.scheduler.get_job('forecast').next_run_time
        if nextrun == True:
            debug.info("Weather forecast next update @ {}".format(nextrun.strftime("%H:%M")))
