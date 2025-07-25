import sys
import os
import logging
import time
from datetime import datetime, date
from typing import Dict, List
from threading import Lock
import schedule

# This path fix is a good safety measure to keep.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.data_classes import MarketStatus, LevelType, CandleData, AssetData
from utils.chart_generator import ChartGenerator
from services.fyers_service import FyersService
from services.notification_service import TelegramService
from utils.date_helper import DateHelper
from utils.cpr_calculator import CPRCalculator
from core.alert_cooldown_manager import AlertCooldownManager
from utils.db_manager import DatabaseService
from utils.config_manager import ConfigManager

class CPRAlertBot:
    """Main application class orchestrating the CPR alert system."""

    def __init__(self):
        self.config = ConfigManager.load_config()
        self.db_service = DatabaseService()
        self.fyers_service = FyersService(self.config['fyers_credentials'])
        self.telegram_service = TelegramService(self.config['telegram_credentials'])
        self.chart_generator = ChartGenerator()

        alert_settings = self.config.get('alert_settings', {})
        self.cooldown_manager = AlertCooldownManager(alert_settings.get('cooldown_minutes', 15))
        self.tolerance_percent = alert_settings.get('tolerance_percent', 0.1)

        self.asset_data: Dict[str, AssetData] = {}
        self.is_running = False
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)

    def initialize_daily_levels(self) -> bool:
        self.logger.info("Initializing CPR levels for all assets...")
        target_date = DateHelper.get_previous_trading_day()

        symbols_list = self.config.get('alert_settings', {}).get('symbols', [])
        if not symbols_list:
            self.logger.critical("CRITICAL ERROR: Could not find 'symbols' list in config.json.")
            return False

        success_count = 0
        for symbol in symbols_list:
            name = symbol.split(':')[-1].replace('-EQ', '')
            self.logger.info(f"Processing {name}")

            ohlc = self.fyers_service.get_ohlc_from_intraday(symbol, target_date)

            if ohlc:
                levels = CPRCalculator.calculate_levels(ohlc)
                self.asset_data[symbol] = AssetData(name=name, symbol=symbol, levels=levels, source_data=ohlc)
                self.db_service.save_daily_levels(symbol, target_date.strftime('%Y-%m-%d'), levels, ohlc)
                success_count += 1
                self.logger.info(f"Successfully calculated CPR levels for {name}")
            else:
                self.logger.error(f"Failed to calculate historical OHLC for {name} on {target_date}")

        if success_count > 0:
            self._send_daily_summary(target_date)
            return True
        else:
            self.logger.error("Could not calculate CPR levels for ANY asset. Bot will not start.")
            return False

    def _send_daily_summary(self, calculation_date: date):
        summary_msg = f"🎯 *Daily CPR Levels Initialized*\n"
        summary_msg += f"_Based on {calculation_date.strftime('%Y-%m-%d')} data for {len(self.asset_data)} assets._"
        self.telegram_service.send_alert(summary_msg)

    def start_monitoring(self):
        """
        Starts the monitoring process by connecting to the WebSocket.
        The bot is now event-driven and will react to messages.
        """
        if not self.asset_data:
            self.logger.error("No asset data available. Run initialize_daily_levels() first.")
            return

        self.is_running = True
        self.logger.info(f"✅ Starting WebSocket monitoring for {len(self.asset_data)} assets.")

        # Get the list of symbols to subscribe to
        symbols_to_monitor = list(self.asset_data.keys())

        # Start the websocket and pass our data handling function as the callback
        self.fyers_service.start_websocket(
            symbols=symbols_to_monitor,
            on_message_callback=self.on_live_data
        )

        # The bot will now run indefinitely, driven by WebSocket events.
        # We can add a simple loop here to keep the main thread alive.
        while self.is_running:
            time.sleep(1)

    def on_live_data(self, message: Dict):
        """
        This method is called by the FyersService every time a new price tick arrives.
        """
        try:
            market_status = DateHelper.get_market_status()
            if market_status != MarketStatus.OPEN:
                return # Ignore messages outside of market hours

            symbol = message["symbol"]
            ltp = message["ltp"]

            # Since we get live ticks (LTP), we treat open, high, low, and close as the same value.
            # We create a pseudo-candle for our existing logic to work.
            tick_as_candle = CandleData(
                timestamp=int(time.time()),
                open=ltp, high=ltp, low=ltp, close=ltp, volume=message.get("v", 0)
            )

            asset_data = self.asset_data.get(symbol)
            if not asset_data:
                return

            key_levels = {
                LevelType.R1: asset_data.levels.r1,
                LevelType.PIVOT: asset_data.levels.pivot,
                LevelType.S1: asset_data.levels.s1,
            }

            for level_type, level_value in key_levels.items():
                if self._is_level_touched(tick_as_candle, level_value) and self.cooldown_manager.can_send_alert(symbol):
                    self._trigger_alert(asset_data, level_type, level_value, tick_as_candle)
                    self.cooldown_manager.record_alert_sent(symbol)
                    break
        except Exception as e:
            self.logger.error(f"Error processing live data for {message.get('symbol')}: {e}", exc_info=True)


    def _is_level_touched(self, candle: CandleData, level_value: float) -> bool:
        # For a live tick, high and low are the same (the LTP).
        # We check if the level is within the tolerance of the current price.
        tolerance = level_value * (self.tolerance_percent / 100)
        return (level_value - tolerance) <= candle.close <= (level_value + tolerance)

    def _trigger_alert(self, asset_data: AssetData, level_type: LevelType, level_value: float, candle: CandleData):
        self.logger.info(f"ALERT: {asset_data.name} touched {level_type.value} at {level_value:.2f}")

        chart_buffer = None
        chart_config = self.config.get('chart_settings', {})
        if chart_config.get('show_pivots', True):
            chart_candles = self.fyers_service.get_historical_data_for_chart(asset_data.symbol)
            if chart_candles:
                chart_buffer = self.chart_generator.create_cpr_chart(
                    asset_data.name, chart_candles, asset_data.levels, level_type, candle.close
                )

        self.telegram_service.send_formatted_alert(
            asset_data.name, level_type, level_value, candle, chart_buffer, asset_data.symbol
        )
        self.db_service.save_alert(asset_data.symbol, level_type.value, level_value, candle.close, candle.timestamp)

    def stop_monitoring(self):
        self.is_running = False
        if self.fyers_service.websocket:
            self.fyers_service.websocket.stop_running()
        self.logger.info("Monitoring stopped.")