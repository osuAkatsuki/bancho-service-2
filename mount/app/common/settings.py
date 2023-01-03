from dotenv import load_dotenv

import os

load_dotenv()

LOG_LEVEL = int(os.environ["LOG_LEVEL"])

DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])

DISCORD_GENERAL_ANTICHEAT_WEBHOOK = os.environ["DISCORD_GENERAL_ANTICHEAT_WEBHOOK"]
DISCORD_CONFIDENTIAL_ANTICHEAT_WEBHOOK = os.environ[
    "DISCORD_CONFIDENTIAL_ANTICHEAT_WEBHOOK"
]

LOGIN_NOTIFICATION = os.environ.get("LOGIN_NOTIFICATION", None)
MAINTENANCE_MODE = bool(os.environ.get("MAINTENANCE_MODE", False))

MAIN_MENU_ICON_URL = os.environ.get("MAIN_MENU_ICON_URL", None)
MAIN_MENU_ON_CLICK_URL = os.environ.get("MAIN_MENU_ON_CLICK_URL", None)

GEOLOCATION_DB_PATH = os.environ["GEOLOCATION_DB_PATH"]
