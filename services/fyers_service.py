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
            if isinstance(message, dict) and message.get('type') in ['sf', 'if']:
                on_message_callback(message)
            else:
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

    def get_ohlc_from_daily_data(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """
        Fetches OHLC data using daily resolution for more accurate results.
        Falls back to intraday method if daily data is not available.
        """
        # First try to get daily OHLC data
        data = {
            "symbol": symbol,
            "resolution": "D",  # Daily resolution
            "date_format": "1",
            "range_from": target_date.strftime('%Y-%m-%d'),
            "range_to": target_date.strftime('%Y-%m-%d'),
            "cont_flag": "1"
        }

        try:
            response = self.fyers.history(data=data)
            if response.get('code') == 200 and response.get('candles'):
                candles = response['candles']
                if candles and len(candles) > 0:
                    # Daily candle format: [timestamp, open, high, low, close, volume]
                    daily_candle = candles[0]  # Should be only one candle for the specific date

                    ohlc = OHLCData(
                        open=daily_candle[1],
                        high=daily_candle[2],
                        low=daily_candle[3],
                        close=daily_candle[4]
                    )

                    self.logger.info(f"Fetched daily OHLC for {symbol} on {target_date}: "
                                     f"O:{ohlc.open:.2f} H:{ohlc.high:.2f} L:{ohlc.low:.2f} C:{ohlc.close:.2f}")
                    return ohlc
                else:
                    self.logger.warning(f"No daily candle found for {symbol} on {target_date}")
            else:
                self.logger.warning(f"Daily data API response for {symbol}: {response.get('message', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"Exception while fetching daily data for {symbol}: {e}")

        # Fallback to intraday method if daily data is not available
        self.logger.info(f"Falling back to intraday method for {symbol}")
        return self.get_ohlc_from_intraday_fallback(symbol, target_date)

    def get_ohlc_from_intraday_fallback(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """
        Fallback method: Calculate OHLC from intraday data with improved accuracy.
        """
        # Use 1-minute data for more accuracy, fall back to 5-minute if needed
        for resolution in ["1", "5"]:
            data = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",
                "range_from": target_date.strftime('%Y-%m-%d'),
                "range_to": target_date.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }

            try:
                response = self.fyers.history(data=data)
                if response.get('code') == 200 and response.get('candles'):
                    candles = response['candles']
                    if not candles:
                        continue

                    # Filter candles to ensure they are within market hours (9:15 AM to 3:30 PM IST)
                    # Timestamps are in epoch seconds
                    import pytz
                    ist = pytz.timezone('Asia/Kolkata')

                    filtered_candles = []
                    for candle in candles:
                        # Convert timestamp to IST datetime
                        candle_time = pd.to_datetime(candle[0], unit='s', utc=True).tz_convert(ist)
                        candle_hour_min = candle_time.hour * 100 + candle_time.minute

                        # Market hours: 9:15 AM (915) to 3:30 PM (1530)
                        if 915 <= candle_hour_min <= 1530:
                            filtered_candles.append(candle)

                    if not filtered_candles:
                        self.logger.warning(f"No {resolution}-min candles found within market hours for {symbol} on {target_date}")
                        continue

                    # Calculate OHLC from filtered candles
                    day_open = filtered_candles[0][1]  # Open of first candle
                    day_high = max(c[2] for c in filtered_candles)  # Highest high
                    day_low = min(c[3] for c in filtered_candles)   # Lowest low
                    day_close = filtered_candles[-1][4]  # Close of last candle

                    ohlc = OHLCData(open=day_open, high=day_high, low=day_low, close=day_close)

                    self.logger.info(f"Calculated OHLC from {resolution}-min data for {symbol} on {target_date}: "
                                     f"O:{ohlc.open:.2f} H:{ohlc.high:.2f} L:{ohlc.low:.2f} C:{ohlc.close:.2f} "
                                     f"({len(filtered_candles)} candles)")
                    return ohlc

                else:
                    self.logger.warning(f"Failed to fetch {resolution}-min data for {symbol}: {response.get('message')}")

            except Exception as e:
                self.logger.error(f"Exception while fetching {resolution}-min data for {symbol}: {e}")
                import pandas as pd  # Import here to avoid issues if not available
                continue

        # If all methods fail
        self.logger.error(f"Failed to calculate OHLC for {symbol} on {target_date} using all methods")
        return None

    def get_ohlc_from_intraday(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """
        Main method to get OHLC data. Now uses the improved daily data method.
        """
        return self.get_ohlc_from_daily_data(symbol, target_date)

    def get_historical_data_for_chart(self, symbol: str) -> Optional[List[CandleData]]:
        """
        Fetches historical data ensuring we get at least 80-90 candles for charting.
        Will go back further in time if needed to get sufficient data.
        """
        chart_config = ConfigManager.load_config().get('chart_settings', {})
        target_candles = chart_config.get('target_candles', 85)  # Target 85 candles
        max_days_back = chart_config.get('max_days_back', 10)  # Maximum days to look back

        end_date = date.today()

        # Start with 3 days and progressively increase if we don't have enough candles
        for days_back in range(3, max_days_back + 1):
            start_date = end_date - timedelta(days=days_back)

            data = {
                "symbol": symbol,
                "resolution": "5",
                "date_format": "1",
                "range_from": start_date.strftime('%Y-%m-%d'),
                "range_to": end_date.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }

            try:
                response = self.fyers.history(data=data)
                if response.get('code') == 200 and response.get('candles'):
                    candles_data = [
                        CandleData(
                            timestamp=c[0],
                            open=c[1],
                            high=c[2],
                            low=c[3],
                            close=c[4],
                            volume=c[5]
                        ) for c in response['candles']
                    ]

                    # If we have enough candles, return them
                    if len(candles_data) >= target_candles:
                        return candles_data

                    # If this is our last attempt, return whatever we have
                    elif days_back == max_days_back:
                        self.logger.warning(f"Only found {len(candles_data)} candles for {symbol} after {days_back} days")
                        return candles_data

                else:
                    self.logger.error(f"API Error fetching chart data for {symbol}: {response.get('message')}")

            except Exception as e:
                self.logger.error(f"Error fetching chart data for {symbol} (attempt {days_back} days): {e}")

        # If all attempts failed, return None
        self.logger.error(f"Failed to fetch sufficient chart data for {symbol}")
        return None