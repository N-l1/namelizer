import time
import requests
import webbrowser
from urllib import parse


class UserConfig:
    def __init__(self, config_data):
        self.__dict__.update(config_data)

    def call_auth(self, auth_data):
        auth = requests.post(url="https://www.strava.com/oauth/token",
                             data={"client_id": self.client_id,
                                   "client_secret": self.client_secret,
                                   **auth_data},
                             timeout=5).json()
        self.access_token = auth["access_token"]
        self.refresh_token = auth["refresh_token"]
        self.expiration = auth["expires_at"]

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
        return("""Success! You have been authenticated.
               Running the script should now update any new activities.""")

    def refresh_auth(self):
        self.call_auth({"refresh_token": self.refresh_token,
                        "grant_type": "refresh_token"})

    def update_name(self, activity_id, new_name, new_des):
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

    def get_activities(self):
        activities = requests.get(url='https://www.strava.com/'
                                      'api/v3/athlete/activities',
                                  headers={"Authorization":
                                           f'Bearer {self.access_token}'},
                                  params={"after": self.last_check},
                                  timeout=5).json()
        return(activities)
