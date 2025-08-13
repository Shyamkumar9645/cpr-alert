import logging
import os
from datetime import date, timedelta
from typing import Optional, List, Callable
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket

from core.data_classes import OHLCData, CandleData
from utils.config_manager import ConfigManager
from utils.auto_token_manager import AutoTokenManager

class FyersService:
    def __init__(self, config: dict):
        self.config = config
        self.client_id = config.get('app_id')
        self.secret_key = config.get('secret_key')
        self.redirect_uri = config.get('redirect_uri')
        self.log_path = config.get('log_path', './logs')

        # Initialize token manager
        self.token_manager = AutoTokenManager()
        self.access_token = None
        self.fyers = None
        self.websocket = None
        self.logger = logging.getLogger(__name__)

        # Get valid token on initialization
        self._ensure_valid_token()

    def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token."""
        try:
            self.access_token = self.token_manager.get_valid_token()
            if self.access_token:
                self.fyers = self._create_client()
                self.logger.info("✅ Valid Fyers token obtained")
                return True
            else:
                self.logger.error("❌ Failed to obtain valid Fyers token")
                return False
        except Exception as e:
            self.logger.error(f"Error ensuring valid token: {e}")
            return False

    def _create_client(self) -> fyersModel.FyersModel:
        """Create Fyers client with current access token."""
        return fyersModel.FyersModel(
            client_id=self.client_id,
            token=self.access_token,
            log_path=self.log_path
        )

    def _refresh_token_if_needed(self):
        """Refresh token if API calls are failing."""
        self.logger.info("Attempting to refresh access token...")
        old_token = self.access_token

        if self._ensure_valid_token() and self.access_token != old_token:
            self.logger.info("✅ Token refreshed successfully")
            return True

        self.logger.error("❌ Token refresh failed")
        return False

    def _make_api_call_with_retry(self, api_call_func, *args, **kwargs):
        """Make API call with automatic token refresh on failure."""
        try:
            # First attempt
            result = api_call_func(*args, **kwargs)

            # Check if the call was successful
            if isinstance(result, dict) and result.get('s') == 'ok':
                return result
            elif isinstance(result, dict) and result.get('code') == 200:
                return result
            else:
                # API call failed, might be due to expired token
                self.logger.warning(f"API call failed: {result}")

                # Try to refresh token and retry once
                if self._refresh_token_if_needed():
                    self.logger.info("Retrying API call with new token...")
                    return api_call_func(*args, **kwargs)
                else:
                    return result

        except Exception as e:
            self.logger.error(f"API call exception: {e}")

            # Try to refresh token and retry once
            if "token" in str(e).lower() or "auth" in str(e).lower():
                if self._refresh_token_if_needed():
                    self.logger.info("Retrying API call after token refresh...")
                    try:
                        return api_call_func(*args, **kwargs)
                    except Exception as retry_e:
                        self.logger.error(f"Retry failed: {retry_e}")
                        raise retry_e
            raise e

    def start_websocket(self, symbols: List[str], on_message_callback: Callable):
        """Initializes and connects to the Fyers Data WebSocket."""
        if not self._ensure_valid_token():
            self.logger.error("Cannot start WebSocket without a valid access token.")
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

            # If it's a token-related error, try to refresh and reconnect
            if "token" in str(message).lower() or "auth" in str(message).lower():
                self.logger.info("Token-related WebSocket error. Attempting to reconnect...")
                if self._refresh_token_if_needed():
                    # Reconnect with new token
                    self.start_websocket(symbols, on_message_callback)

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
        """Legacy method - now uses automated token manager."""
        return self.token_manager.get_valid_token()

    def get_ohlc_from_daily_data(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """
        Fetches OHLC data using daily resolution with automatic token refresh.
        """
        data = {
            "symbol": symbol,
            "resolution": "D",
            "date_format": "1",
            "range_from": target_date.strftime('%Y-%m-%d'),
            "range_to": target_date.strftime('%Y-%m-%d'),
            "cont_flag": "1"
        }

        try:
            response = self._make_api_call_with_retry(self.fyers.history, data=data)

            if response.get('code') == 200 and response.get('candles'):
                candles = response['candles']
                if candles and len(candles) > 0:
                    daily_candle = candles[0]

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

        # Fallback to intraday method
        self.logger.info(f"Falling back to intraday method for {symbol}")
        return self.get_ohlc_from_intraday_fallback(symbol, target_date)

    def get_ohlc_from_intraday_fallback(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """Fallback method with automatic token refresh."""
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
                response = self._make_api_call_with_retry(self.fyers.history, data=data)

                if response.get('code') == 200 and response.get('candles'):
                    candles = response['candles']
                    if not candles:
                        continue

                    # Filter candles within market hours
                    import pytz
                    import pandas as pd

                    ist = pytz.timezone('Asia/Kolkata')
                    filtered_candles = []

                    for candle in candles:
                        candle_time = pd.to_datetime(candle[0], unit='s', utc=True).tz_convert(ist)
                        candle_hour_min = candle_time.hour * 100 + candle_time.minute

                        if 915 <= candle_hour_min <= 1530:
                            filtered_candles.append(candle)

                    if not filtered_candles:
                        continue

                    # Calculate OHLC
                    day_open = filtered_candles[0][1]
                    day_high = max(c[2] for c in filtered_candles)
                    day_low = min(c[3] for c in filtered_candles)
                    day_close = filtered_candles[-1][4]

                    ohlc = OHLCData(open=day_open, high=day_high, low=day_low, close=day_close)

                    self.logger.info(f"Calculated OHLC from {resolution}-min data for {symbol}: "
                                     f"O:{ohlc.open:.2f} H:{ohlc.high:.2f} L:{ohlc.low:.2f} C:{ohlc.close:.2f}")
                    return ohlc

            except Exception as e:
                self.logger.error(f"Exception fetching {resolution}-min data for {symbol}: {e}")
                continue

        return None

    def get_ohlc_from_intraday(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """Main OHLC method."""
        return self.get_ohlc_from_daily_data(symbol, target_date)

    def get_historical_data_for_chart(self, symbol: str) -> Optional[List[CandleData]]:
        """Fetches historical data with automatic token refresh."""
        chart_config = ConfigManager.load_config().get('chart_settings', {})
        target_candles = chart_config.get('target_candles', 85)
        max_days_back = chart_config.get('max_days_back', 10)

        end_date = date.today()

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
                response = self._make_api_call_with_retry(self.fyers.history, data=data)

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

                    if len(candles_data) >= target_candles:
                        return candles_data
                    elif days_back == max_days_back:
                        return candles_data

            except Exception as e:
                self.logger.error(f"Error fetching chart data: {e}")

        return None