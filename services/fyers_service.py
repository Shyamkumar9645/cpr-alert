import logging
import os
from datetime import date, timedelta
from typing import Optional, List, Callable
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket

from core.data_classes import OHLCData, CandleData
from utils.config_manager import ConfigManager

class FyersService:
    def __init__(self, config: dict):
        self.config = config
        self.client_id = config.get('app_id')
        self.secret_key = config.get('secret_key')
        self.redirect_uri = config.get('redirect_uri')
        self.access_token = config.get('access_token')
        self.log_path = config.get('log_path', './logs')
        self.fyers = self._create_client()
        self.websocket = None
        self.logger = logging.getLogger(__name__)

    def _create_client(self) -> fyersModel.FyersModel:
        return fyersModel.FyersModel(
            client_id=self.client_id,
            token=self.access_token,
            log_path=self.log_path
        )

    def start_websocket(self, symbols: List[str], on_message_callback: Callable):
        """Initializes and connects to the Fyers Data WebSocket."""
        if not self.access_token:
            self.logger.error("Cannot start WebSocket without an access token.")
            return

        ws_access_token = f"{self.client_id}:{self.access_token}"
        data_type = "SymbolUpdate"

        def on_message(message):
            # --- MODIFIED LINE ---
            # Process messages if they are for Stocks ('sf') or Indices ('if')
            if isinstance(message, dict) and message.get('type') in ['sf', 'if']:
                on_message_callback(message)
            else:
                # Log other messages (like connection status) for info, but don't process
                self.logger.info(f"WEBSOCKET INFO: {message.get('message', message)}")

        def on_error(message):
            self.logger.error(f"WebSocket Error: {message}")

        def on_close(message):
            self.logger.warning(f"WebSocket Connection Closed: {message}")

        def on_open():
            self.logger.info("WebSocket connection established. Subscribing to symbols...")
            self.websocket.subscribe(symbols=symbols, data_type=data_type)
            self.websocket.keep_running()

        self.websocket = FyersDataSocket(
            access_token=ws_access_token,
            log_path=self.log_path,
            on_connect=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message
        )

        self.websocket.connect()

    def generate_access_token(self) -> Optional[str]:
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