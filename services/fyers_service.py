import logging
import os
from datetime import date, timedelta
from typing import Optional, List
from fyers_apiv3 import fyersModel

from core.data_classes import OHLCData, CandleData
from utils.config_manager import ConfigManager

class FyersService:
    def __init__(self, config: dict):
        self.config = config
        self.client_id = config.get('app_id')
        self.secret_key = config.get('secret_key')
        self.redirect_uri = config.get('redirect_uri')
        self.access_token = config.get('access_token') # Get token from config
        self.log_path = config.get('log_path', './logs')
        self.fyers = self._create_client()
        self.logger = logging.getLogger(__name__)

    def _create_client(self) -> fyersModel.FyersModel:
        # The client is now created directly with the access token
        return fyersModel.FyersModel(
            client_id=self.client_id,
            token=self.access_token,
            log_path=self.log_path
        )

    def generate_access_token(self) -> Optional[str]:
        """
        Guides the user to generate a new access token and returns it.
        It no longer writes to a file.
        """
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        auth_url = session.generate_authcode()
        print(f"Login URL: {auth_url}")

        try:
            auth_code = input("Please enter the auth code generated after logging in: ")
        except EOFError:
            self.logger.error("Could not read auth code. Please run in an interactive terminal.")
            return None

        session.set_token(auth_code)
        response = session.generate_token()

        if response and 'access_token' in response:
            return response['access_token']
        else:
            self.logger.error(f"Token generation failed: {response.get('message', 'Unknown error')}")
            return None

    # --- All other functions (get_ohlc_from_intraday, etc.) remain the same ---

    def get_ohlc_from_intraday(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        data = {
            "symbol": symbol, "resolution": "5", "date_format": "1",
            "range_from": target_date.strftime('%Y-%m-%d'),
            "range_to": target_date.strftime('%Y-%m-%d'),
            "cont_flag": "1"
        }
        try:
            response = self.fyers.history(data=data)
            if response.get('code') == 200 and response.get('candles'):
                candles = response['candles']
                if not candles:
                    self.logger.warning(f"No intraday candles found for {symbol} on {target_date}.")
                    return None

                day_open = candles[0][1]
                day_high = max(c[2] for c in candles)
                day_low = min(c[3] for c in candles)
                day_close = candles[-1][4]

                return OHLCData(open=day_open, high=day_high, low=day_low, close=day_close)
            else:
                self.logger.error(f"API Error fetching intraday for {symbol}: {response.get('message')}")
                return None
        except Exception as e:
            self.logger.error(f"Exception while fetching intraday for {symbol}: {e}", exc_info=True)
            return None

    def get_latest_candle(self, symbol: str) -> Optional[CandleData]:
        end_date = date.today()
        start_date = end_date - timedelta(days=2)
        data = {
            "symbol": symbol, "resolution": "5", "date_format": "1",
            "range_from": start_date.strftime('%Y-%m-%d'),
            "range_to": end_date.strftime('%Y-%m-%d'),
            "cont_flag": "1"
        }
        try:
            response = self.fyers.history(data=data)
            if response.get('code') == 200 and response.get('candles'):
                latest = response['candles'][-1]
                return CandleData(timestamp=latest[0], open=latest[1], high=latest[2], low=latest[3], close=latest[4], volume=latest[5])
        except Exception as e:
            self.logger.error(f"Error fetching latest candle for {symbol}: {e}")
            return None

    def get_historical_data_for_chart(self, symbol: str) -> Optional[List[CandleData]]:
        chart_config = ConfigManager.load_config().get('chart_settings', {})
        days_to_fetch = chart_config.get('historical_days', 2)
        end_date = date.today()
        start_date = end_date - timedelta(days=days_to_fetch)
        data = {
            "symbol": symbol, "resolution": "5", "date_format": "1",
            "range_from": start_date.strftime('%Y-%m-%d'),
            "range_to": end_date.strftime('%Y-%m-%d'),
            "cont_flag": "1"
        }
        try:
            response = self.fyers.history(data=data)
            if response.get('code') == 200 and response.get('candles'):
                return [CandleData(timestamp=c[0], open=c[1], high=c[2], low=c[3], close=c[4], volume=c[5]) for c in response['candles']]
        except Exception as e:
            self.logger.error(f"Error fetching chart data for {symbol}: {e}")
            return None