import json
import os
from dotenv import load_dotenv
from pathlib import Path

class ConfigManager:
    """
    Manages loading and accessing configuration settings from JSON and .env files.
    """
    def __init__(self, config_path='config.json', env_path='.env'):
        """
        Initializes the ConfigManager by loading configurations.
        """
        # Load environment variables from .env file
        env_file = Path(env_path)
        if not env_file.is_file():
            raise FileNotFoundError(f"CRITICAL: .env file not found at {env_file.resolve()}. Please run scripts/setup_security.py")
        load_dotenv(dotenv_path=env_file)

        # Load settings from config.json
        config_file = Path(config_path)
        if not config_file.is_file():
             raise FileNotFoundError(f"CRITICAL: config.json not found at {config_file.resolve()}. Please ensure it exists.")
        with open(config_file, 'r') as f:
            self.settings = json.load(f)

        # Populate credentials from environment variables
        self.settings['fyers_credentials']['app_id'] = os.getenv('FYERS_APP_ID')
        self.settings['fyers_credentials']['secret_key'] = os.getenv('FYERS_SECRET_KEY')
        self.settings['fyers_credentials']['redirect_uri'] = os.getenv('FYERS_REDIRECT_URI')
        self.settings['fyers_credentials']['access_token'] = os.getenv('FYERS_ACCESS_TOKEN')
        self.settings['telegram_credentials']['bot_token'] = os.getenv('TELEGRAM_BOT_TOKEN')
        self.settings['telegram_credentials']['chat_id'] = os.getenv('TELEGRAM_CHAT_ID')

        self._validate_config()

    def _validate_config(self):
        """
        Validates that all necessary configuration keys are present.
        """
        required_fyers = ['app_id', 'secret_key', 'access_token', 'redirect_uri']
        required_telegram = ['bot_token', 'chat_id']

        for key in required_fyers:
            if not self.settings['fyers_credentials'].get(key):
                raise ValueError(f"Missing required Fyers credential in .env: FYERS_{key.upper()}")

        for key in required_telegram:
            if not self.settings['telegram_credentials'].get(key):
                 raise ValueError(f"Missing required Telegram credential in .env: TELEGRAM_{key.upper()}")

    def get_config(self):
        """
        Returns the fully populated configuration dictionary.
        """
        return self.settings

    def get_fyers_credentials(self):
        return self.settings['fyers_credentials']

    def get_telegram_credentials(self):
        return self.settings['telegram_credentials']

    def get_alert_settings(self):
        return self.settings['alert_settings']