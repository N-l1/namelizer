import time
import requests
from jinja2 import Template
from geopy.geocoders import Nominatim


def get_weather(dt, lat, lon, appid):
    weather = requests.get(url='https://api.openweathermap.org/'
                               'data/2.5/onecall/timemachine',
                           params={'dt': dt, 'lat': lat,
                                   'lon': lon, 'appid': appid},
                           timeout=5).json()
    return(weather.get("current"))


def get_location(activity):
    geocoder = Nominatim(user_agent="namelizer")
    return(geocoder.reverse(activity["start_latlng"].raw["address"]),
           geocoder.reverse(activity["end_latlng"].raw["address"]))


def format_template(name_template, des_template, activity, weather_api):
    weather = {}
    if (weather_api and
       ("weather" in name_template or "weather" in des_template)):
        weather = get_weather(
                int(time.mktime(time.strptime(activity["start_date_local"],
                                              r"%Y-%m-%dT%H:%M:%SZ"))),
                *activity.get("start_latlng"),
                weather_api)
    start_location, end_location = get_location(activity)
    return(tuple(Template(i).render(activity=activity,
                                    start_location=start_location,
                                    end_location=end_location,
                                    weather=weather)
                 for i in (name_template, des_template)))
