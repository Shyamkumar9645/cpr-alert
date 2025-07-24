import json
import os
import sys
import logging
from dotenv import load_dotenv

class ConfigManager:
    _config = None

    @staticmethod
    def load_config():
        if ConfigManager._config is None:
            load_dotenv()

            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
            except FileNotFoundError:
                logging.critical("CRITICAL ERROR: config.json not found.")
                sys.exit(1)
            except json.JSONDecodeError:
                logging.critical("CRITICAL ERROR: config.json is not valid.")
                sys.exit(1)

            config.setdefault('fyers_credentials', {})
            config.setdefault('telegram_credentials', {})

            # Populate the config with values from your .env file
            config['fyers_credentials']['app_id'] = os.getenv('FYERS_APP_ID')
            config['fyers_credentials']['secret_key'] = os.getenv('FYERS_SECRET_KEY')
            config['fyers_credentials']['redirect_uri'] = os.getenv('FYERS_REDIRECT_URI')
            config['fyers_credentials']['access_token'] = os.getenv('FYERS_ACCESS_TOKEN') # <-- ADDED THIS LINE

            config['telegram_credentials']['bot_token'] = os.getenv('TELEGRAM_BOT_TOKEN')
            config['telegram_credentials']['chat_id'] = os.getenv('TELEGRAM_CHAT_ID')

            ConfigManager._config = config
        return ConfigManager._config