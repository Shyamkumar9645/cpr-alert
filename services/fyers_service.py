import logging
from fyers_apiv3 import fyersModel

class FyersService:
    """
    Service to interact with the Fyers API for fetching data and managing sessions.
    """
    def __init__(self, fyers_config):
        """
        Initializes the FyersModel client.
        """
        self.client = fyersModel.FyersModel(
            client_id=fyers_config['app_id'],
            token=fyers_config['access_token'],
            log_path=fyers_config.get('log_path', 'logs/')
        )
        self.logger = logging.getLogger(__name__)

    def get_profile(self):
        """Fetches user profile to validate the connection."""
        try:
            response = self.client.get_profile()
            if response.get('s') == 'ok':
                self.logger.info("Fyers API connection successful.")
                return response.get('data')
            else:
                self.logger.error(f"Fyers API connection failed: {response.get('message')}")
                return None
        except Exception as e:
            self.logger.exception(f"Exception during Fyers profile fetch: {e}")
            return None

    def get_historical_data(self, symbol: str, timeframe: str, date_from, date_to):
        """
        Fetches historical candle data for a given symbol.
        """
        data = {
            "symbol": symbol,
            "resolution": timeframe,
            "date_format": "1",
            "range_from": date_from.strftime('%Y-%m-%d'),
            "range_to": date_to.strftime('%Y-%m-%d'),
            "cont_flag": "1"
        }
        try:
            response = self.client.history(data=data)
            if response.get('s') == 'ok':
                return response.get('candles', [])
            else:
                self.logger.error(f"Failed to fetch history for {symbol}: {response.get('message')}")
                return []
        except Exception as e:
            self.logger.exception(f"Exception fetching history for {symbol}: {e}")
            return []

    def get_quotes(self, symbols: list):
        """
        Fetches live quotes for a list of symbols.
        """
        data = {"symbols": ",".join(symbols)}
        try:
            response = self.client.quotes(data=data)
            if response.get('s') == 'ok':
                return response.get('d', [])
            else:
                self.logger.error(f"Failed to fetch quotes: {response.get('message')}")
                return []
        except Exception as e:
            self.logger.exception(f"Exception fetching quotes: {e}")
            return []