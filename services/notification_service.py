import requests
import logging

class NotificationService:
    """
    Service for sending notifications, currently implemented for Telegram.
    """
    def __init__(self, telegram_config):
        """
        Initializes the notification service with Telegram credentials.
        """
        self.bot_token = telegram_config['bot_token']
        self.chat_id = telegram_config['chat_id']
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.logger = logging.getLogger(__name__)

    def send_message(self, message: str, photo_path: str = None):
        """
        Sends a message and an optional photo to the configured Telegram chat.
        """
        if photo_path:
            self._send_photo(message, photo_path)
        else:
            self._send_text(message)

    def _send_text(self, message: str):
        """Sends a text-only message."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()
            self.logger.info("Successfully sent text message to Telegram.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send text message to Telegram: {e}")

    def _send_photo(self, caption: str, photo_path: str):
        """Sends a photo with a caption."""
        url = f"{self.base_url}/sendPhoto"
        payload = {
            'chat_id': self.chat_id,
            'caption': caption,
            'parse_mode': 'Markdown'
        }
        try:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                response = requests.post(url, data=payload, files=files)
                response.raise_for_status()
            self.logger.info(f"Successfully sent photo '{photo_path}' to Telegram.")
        except FileNotFoundError:
            self.logger.error(f"Photo file not found: {photo_path}. Sending text caption instead.")
            self._send_text(caption)
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send photo to Telegram: {e}")