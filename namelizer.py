import time
import yaml
import templating
from user import UserConfig


def main():
    updated = 0
    with open(r'config.yaml', 'r') as file:
        config = UserConfig(yaml.load(file, Loader=yaml.FullLoader))
    if not hasattr(config, "refresh_token"):
        print(config.initial_auth())
    elif time.time() >= config.expiration:
        config.refresh_auth()
    print("Searching for new activities...")
    for activity in config.get_activities():
        if activity["name"][0] == config.special_char:
            config.update_name(activity["id"],
                               *templating.format_template(
                                               config.name_format,
                                               config.des_format,
                                               activity,
                                               config.weather_api))
            updated += 1
    with open(r'config.yaml', 'w') as file:
        yaml.dump(config.__dict__, file)
    print(f"Updated {updated} activities")


if __name__ == '__main__':
    main()
