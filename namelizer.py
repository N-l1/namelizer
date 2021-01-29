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
        expiration (int): Unix timestamp of when the access token expires.
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
        return(activities)

    def get_weather(self, activity):
        """
        Get the weather of a given activity.

        Args:
            activity: Dictionary of the activity to get weather.

        Returns:
            Dictionary of the weather at the start of the activity.
        """
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
        self.call_auth({"code": code, "grant_type": "authorization_code"})
        return("\nSuccess! You have been authenticated\n"
               "Running the script should now update any new activities\n")

    def update_activity(self, activity):
        """
        Update an activity based on the user's name & description format.

        Args:
            activity: Dictionary of the activity to update.

        Returns:
            Returns 1, indicating it has updated one activity.
        """
        new_name, new_des = self.format_template(activity)
        update_data = {}
        # Update name if special character found in name
        if (not hasattr(self, "special_char") or
           (new_name and activity["name"][0] == self.special_char)):
            update_data["name"] = new_name
        # Update description if special character found in description
        # Both will be updated if special character not specified
        if (not hasattr(self, "special_char") or
           (new_des and activity["description"] and
           activity["description"][0] == self.special_char)):
            update_data["description"] = new_des
        activity = requests.put(url="https://www.strava.com/"
                                    f'api/v3/activities/{activity["id"]}',
                                headers={"Authorization":
                                         f'Bearer {self.access_token}'},
                                data=update_data, timeout=5).json()
        self.last_check = int(time.mktime(time.strptime(
                                        activity["start_date_local"],
                                        r"%Y-%m-%dT%H:%M:%SZ")))
        return 1

    def format_template(self, activity):
        """
        Using Jinja to format user's name & description template.

        Args:
            activity: Dictionary of the activity to use data from.

        Returns:
            Tuple of formated versions of the name & des templates.
        """
        weather = start_location = end_location = None
        name_template, des_template = [getattr(self, i, "")
                                       for i in ("name_template",
                                                 "des_template")]
        # Get weather data if used
        if (hasattr(self, "weather_api") and
           "weather" in name_template + des_template):
            weather = self.get_weather(activity)
        # Get location data if used
        print(name_template + des_template)
        if "location" in name_template + des_template:
            start_location, end_location = User.get_location(activity)
        return(tuple(Template(i).render(activity=activity,
                                        start_location=start_location,
                                        end_location=end_location,
                                        weather=weather)
                     for i in (name_template, des_template)))

    def store_secrets(self):
        # Store tokens & timestamps in secret.pkl
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
    updated = 0
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
    print("Searching for new activities...")
    # Go through the most recent activities.
    for activity in config.get_activities():
        activity = config.get_activities(f'activities/{activity["id"]}')
        # Special character not specfied, update all activities
        if not hasattr(config, "special_char") or not config.special_char:
            updated += config.update_activity(activity)
        # Else if any match the special character,
        # update the name/description
        elif (activity["name"][0] == config.special_char or
              (activity.get("description") and
              activity["description"][0] == config.special_char)):
            updated += config.update_activity(activity)
    print(f"Updated {updated} activities")
    # Store new data
    config.store_secrets()


if __name__ == '__main__':
    main()
