import time
import yaml
from user import User


def main():
    updated = 0
    with open(r'config.yaml', 'r') as file:
        config = User(yaml.load(file, Loader=yaml.FullLoader))
    if not hasattr(config, "refresh_token"):
        print(config.initial_auth())
    elif time.time() >= config.expiration:
        config.refresh_auth()
    print("Searching for new activities...")
    for activity in config.get_activities():
        if activity["name"][0] == config.special_char:
            config.update_name(activity)
            updated += 1
    with open(r'config.yaml', 'w') as file:
        yaml.dump(config.__dict__, file)
    print(f"Updated {updated} activities")


if __name__ == '__main__':
    main()
