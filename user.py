import time
import requests
import webbrowser
from urllib import parse
from jinja2 import Template
from geopy.geocoders import Nominatim


class User:
    def __init__(self, config_data):
        self.__dict__.update(config_data)

    def get_activities(self):
        activities = requests.get(url='https://www.strava.com/'
                                      'api/v3/athlete/activities',
                                  headers={"Authorization":
                                           f'Bearer {self.access_token}'},
                                  params={"after": self.last_check},
                                  timeout=5).json()
        return(activities)

    def get_weather(self, activity):
        dt = int(time.mktime(time.strptime(activity["start_date_local"],
                                           r"%Y-%m-%dT%H:%M:%SZ")))
        lat, lon = activity["start_latlng"]
        weather = requests.get(url='https://api.openweathermap.org/'
                                   'data/2.5/onecall/timemachine',
                               params={'dt': dt, 'lat': lat,
                                       'lon': lon, 'appid': self.weather_api},
                               timeout=5).json()
        return(weather.get("current"))

    @staticmethod
    def get_location(activity):
        geocoder = Nominatim(user_agent="namelizer")
        return(geocoder.reverse(activity["start_latlng"]).raw["address"],
               geocoder.reverse(activity["end_latlng"]).raw["address"])

    def call_auth(self, auth_data):
        auth = requests.post(url="https://www.strava.com/oauth/token",
                             data={"client_id": self.client_id,
                                   "client_secret": self.client_secret,
                                   **auth_data},
                             timeout=5).json()
        self.access_token = auth["access_token"]
        self.refresh_token = auth["refresh_token"]
        self.expiration = auth["expires_at"]

    def refresh_auth(self):
        self.call_auth({"refresh_token": self.refresh_token,
                        "grant_type": "refresh_token"})

    def initial_auth(self):
        self.last_check = time.time()
        webbrowser.open('https://www.strava.com/oauth/authorize'
                        f'?client_id={self.client_id}'
                        '&redirect_uri=http://localhost/exchange_token'
                        '&response_type=code'
                        '&scope=activity:read_all,activity:write')
        code = parse.parse_qsl(parse.urlsplit(
                input("Please enter the return link: ")).query)[0][1]
        self.call_auth({"code": code, "grant_type": "authorization_code"})
        return("\nSuccess! You have been authenticated\n"
               "Running the script should now update any new activities\n")

    def update_name(self, activity):
        activity_id = activity["id"]
        new_name, new_des = self.format_template(activity)
        activity = requests.put(url="https://www.strava.com/"
                                    f"api/v3/activities/{activity_id}",
                                headers={"Authorization":
                                         f'Bearer {self.access_token}'},
                                data={"name": new_name,
                                      "description": new_des},
                                timeout=5).json()
        self.last_check = int(time.mktime(time.strptime(
                                            activity["start_date_local"],
                                            r"%Y-%m-%dT%H:%M:%SZ")))

    def format_template(self, activity):
        weather = {}
        if (self.weather_api and ("weather" in self.name_format
           or "weather" in self.des_format)):
            weather = self.get_weather(activity)
        start_location, end_location = User.get_location(activity)
        return(tuple(Template(i).render(activity=activity,
                                        start_location=start_location,
                                        end_location=end_location,
                                        weather=weather)
                     for i in (self.name_format, self.des_format)))
