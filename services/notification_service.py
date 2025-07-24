import logging
import requests
import io
from typing import Optional
from core.data_classes import LevelType, CandleData

class TelegramService:
    def __init__(self, config: dict):
        self.token = config.get('bot_token')
        self.chat_id = config.get('chat_id')
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.logger = logging.getLogger(__name__)

    def send_alert(self, message: str):
        url = f"{self.base_url}/sendMessage"
        params = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send Telegram message: {e}")

    def send_formatted_alert(self, asset_name: str, level_type: LevelType, level_value: float, candle: CandleData, chart_buffer: Optional[io.BytesIO] = None, symbol: str = ""):
        direction_emoji = "📈" if candle.close > candle.open else "📉"
        message = (
            f"🚨 *Level Alert: {asset_name}*\n\n"
            f"{direction_emoji} Touched *{level_type.value}* at `{level_value:.2f}`\n"
            f"Current Price: `{candle.close:.2f}`\n\n"
            f"Candle: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}"
        )

        if chart_buffer:
            self.send_photo(chart_buffer, caption=message)
        else:
            self.send_alert(message)

    def send_photo(self, photo_buffer: io.BytesIO, caption: str):
        url = f"{self.base_url}/sendPhoto"
        files = {'photo': ('chart.png', photo_buffer, 'image/png')}
        params = {'chat_id': self.chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
        try:
            response = requests.post(url, files=files, data=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send Telegram photo: {e}")