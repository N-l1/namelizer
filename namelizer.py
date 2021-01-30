import time
import yaml
import pickle
import requests
import webbrowser
from urllib import parse
from jinja2 import Template
from geopy.geocoders import Nominatim


class User:
    """
    Class to store user config to get and update Strava activities.

    Attributes:
        access_token (str): Your Strava access token.
        expires_at (int): Unix timestamp of when the access token expires.
        refresh_token (str): Your Strava refresh token.
        client_id (int): Your Strava APP Client ID.
        client_secret (str): Your Strava APP Client Secret.
        last_check (int): Unix timestamp of when last update happened.
        special_char (str): Character to check, if matched, will update.
        name_template (str): Jinja template of your activity name.
        des_template (str): Jinja template of your activity description.
        weather_api (str): OpenWeatherMap API key.
    """

    def __init__(self, config_data):
        """
        Constructs all the necessary attributes for the User object.

        Args:
            config_data: User's config read from config.yaml.
        """
        self.__dict__.update(config_data)
        self.check_required()

    def check_required(self):
        """
        Check if the user has specified required parameters.

        Raises:
            NameError - Required parameter not specified.
        """
        for i in (i for i in ("client_id", "client_secret")
                  if not hasattr(self, i)):
            raise NameError(f"'{i}' is required but not defined")
        if not any(hasattr(self, i)
                   for i in ("name_template", "des_template")):
            raise NameError("name_template or des_template is required")

    def get_activities(self, path="athlete/activities"):
        """
        List activities after the specified timestamp.
        Max is 30 activities.

        Returns:
            List of activities.
        """
        activities = requests.get(url='https://www.strava.com/'
                                  f'api/v3/{path}',
                                  headers={"Authorization":
                                           f'Bearer {self.access_token}'},
                                  params={"after": self.last_check},
                                  timeout=5).json()
        return activities

    def get_weather(self, activity):
        """
        Get the weather of a given activity.

        Args:
            activity: Dictionary of the activity to get weather.

        Returns:
            Dictionary of the weather at the start of the activity.
        """
        if not hasattr(self, "weather_api"):
            raise NameError("weather_api is required for weather data")
        dt = int(time.mktime(time.strptime(activity["start_date_local"],
                                           r"%Y-%m-%dT%H:%M:%SZ")))
        lat, lon = activity["start_latlng"]
        weather = requests.get(url='https://api.openweathermap.org/'
                               'data/2.5/onecall/timemachine',
                               params={'dt': dt, 'lat': lat,
                                       'lon': lon, 'appid': self.weather_api},
                               timeout=5).json()
        return weather.get("current")

    @ staticmethod
    def get_location(activity):
        """
        Get the start and end location of a given activity.

        Args:
            activity: Dictionary of the activity to get location.

        Returns:
            Tuple of dictionary of starting and ending address.
        """
        geocoder = Nominatim(user_agent="namelizer")
        return(geocoder.reverse(activity["start_latlng"]).raw["address"],
               geocoder.reverse(activity["end_latlng"]).raw["address"])

    def call_auth(self, auth_data):
        """
        Calls Strava's auth service to refresh or create new tokens.

        Args:
            auth_data: Dictionary of data POST should include.
        """
        auth = requests.post(url="https://www.strava.com/oauth/token",
                             data={"client_id": self.client_id,
                                   "client_secret": self.client_secret,
                                   **auth_data},
                             timeout=5).json()
        self.__dict__.update({i: auth[i] for i in ("access_token",
                                                   "refresh_token",
                                                   "expires_at")})

    def refresh_auth(self):
        """
        Get a new access token with a refresh token.
        """
        self.call_auth({"refresh_token": self.refresh_token,
                        "grant_type": "refresh_token"})

    def initial_auth(self):
        """
        Prompt the user to authenticate
        to get initial access token & refresh token.

        Returns:
            Message stating authentication was successful.
        """
        self.last_check = time.time()
        # Open browser to prompt the user to authorize
        webbrowser.open('https://www.strava.com/oauth/authorize'
                        f'?client_id={self.client_id}'
                        '&redirect_uri=http://localhost/exchange_token'
                        '&response_type=code'
                        '&scope=activity:read_all,activity:write')
        # Parse the return link
        code = parse.parse_qsl(parse.urlsplit(
            input("Please enter the return link: ")).query)[0][1]
        # Get access & refresh tokens
        self.call_auth({"code": code, "grant_type": "authorization_code"})
        return("\nSuccess! You have been authenticated\n"
               "Running the script should now update any new activities\n")

    def update_activity(self, activity, change):
        """
        Update an activity based on the user's name & description format.

        Args:
            activity: Dictionary of the activity to update.
            change: "name" or "description", the field to change.
        """
        new = self.format_template(activity, change)
        update_data = {change: new}
        activity = requests.put(url="https://www.strava.com/"
                                f'api/v3/activities/{activity["id"]}',
                                headers={"Authorization":
                                         f'Bearer {self.access_token}'},
                                data=update_data, timeout=5).json()
        self.last_check = int(time.mktime(time.strptime(
            activity["start_date_local"],
            r"%Y-%m-%dT%H:%M:%SZ")))
        self.activity_updated = True

    def format_template(self, activity, change):
        """
        Using Jinja to format user's name & description template.

        Args:
            activity: Dictionary of the activity to use data from.
            change: "name" or "description", the template to format.

        Returns:
            Tuple of formated versions of the name & des templates.
        """
        # Weather wether to update name or description
        if change == "name":
            temp = self.name_template
        elif change == "description":
            temp = self.des_template
        weather = start_location = end_location = None
        # Get weather data if used
        if "weather" in temp:
            weather = self.get_weather(activity)
        # Get location data if used
        if "location" in temp:
            start_location, end_location = User.get_location(activity)
        return Template(temp).render(activity=activity,
                                     start_location=start_location,
                                     end_location=end_location,
                                     weather=weather)

    def store_secrets(self):
        """
        Store tokens & timestamps in secret.pkl.
        """
        with open(r'secrets.pkl', "wb") as pickle_file:
            pickle.dump({k: v for k, v in self.__dict__.items()
                         if k in ("access_token", "refresh_token",
                                  "expires_at", "last_check")},
                        pickle_file)


def main():
    """
    Updates new activity names & descriptions in Strava
    using specified format if the special character is found.
    """
    updated_activities = 0

    # Read the user input from config.yaml
    with open(r'config.yaml', 'r') as file:
        yaml_config = yaml.load(file, Loader=yaml.FullLoader)
    try:
        # Read data previously stored at secret.pkl
        with open(r'secrets.pkl', "rb") as pickle_file:
            pickle_data = pickle.load(pickle_file)
            pickle_data.update(yaml_config)
            config = User(pickle_data)
    # Initial authorization if it is
    # the first time the script has been run
    except FileNotFoundError:
        config = User(yaml_config)
        print(config.initial_auth())
        config.store_secrets()
        return "Initial auth successful"

    # If the access token expires,
    # refresh using refresh token
    if time.time() >= config.expires_at:
        config.refresh_auth()

    # Go through the most recent activities.
    print("Searching for new activities...")
    for activity in config.get_activities():
        config.activity_updated = False
        activity = config.get_activities(f'activities/{activity["id"]}')

        # Special character found in description, update description
        if hasattr(config, "name_template"):
            if (not hasattr(config, "special_char") or not config.special_char
                    or activity["name"][0] == config.special_char):
                config.update_activity(activity, "name")

        # Special character found in description, update description
        if hasattr(config, "des_template"):
            if (not hasattr(config, "special_char") or not config.special_char
                    or (activity.get("description") and
                        activity["description"][0] == config.special_char)):
                config.update_activity(activity, "description")

        # Count how many activities were updated
        if config.activity_updated:
            updated_activities += 1

    # Store new data
    config.store_secrets()
    print(f"Updated {updated_activities} activities")


if __name__ == '__main__':
    main()
