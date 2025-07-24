import sys
import os
import logging
import time
from datetime import datetime, date
from typing import Dict
from threading import Lock
import schedule

# This path fix is a good safety measure to keep.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# These imports will now succeed.
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

        # Safely get settings from your config
        alert_settings = self.config.get('alert_settings', {})
        self.cooldown_manager = AlertCooldownManager(alert_settings.get('cooldown_minutes', 15))
        self.check_interval = alert_settings.get('check_interval_seconds', 60)
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
        summary_msg += f"_Based on {calculation_date.strftime('%d/%m/%Y')} data for {len(self.asset_data)} assets._"
        self.telegram_service.send_alert(summary_msg)

    def start_monitoring(self):
        if not self.asset_data:
            self.logger.error("No asset data available. Run initialize_daily_levels() first.")
            return

        self.is_running = True
        self.logger.info(f"✅ Monitoring started for {len(self.asset_data)} assets.")
        schedule.every().day.at("08:00").do(self.initialize_daily_levels)

        while self.is_running:
            market_status = DateHelper.get_market_status()
            if market_status == MarketStatus.OPEN:
                self._check_level_touches()
            else:
                self.logger.info("Market is closed. Sleeping for 10 minutes.")
                time.sleep(600)

            schedule.run_pending()
            time.sleep(self.check_interval)

    def _check_level_touches(self):
        for symbol, asset_data in self.asset_data.items():
            try:
                candle = self.fyers_service.get_latest_candle(symbol)
                if not candle or (asset_data.last_candle_timestamp and candle.timestamp <= asset_data.last_candle_timestamp):
                    continue

                with self._lock:
                    asset_data.last_candle_timestamp = candle.timestamp

                key_levels = {
                    LevelType.R1: asset_data.levels.r1,
                    LevelType.PIVOT: asset_data.levels.pivot,
                    LevelType.S1: asset_data.levels.s1,
                }

                for level_type, level_value in key_levels.items():
                    if self._is_level_touched(candle, level_value) and self.cooldown_manager.can_send_alert(symbol):
                        self._trigger_alert(asset_data, level_type, level_value, candle)
                        self.cooldown_manager.record_alert_sent(symbol)
                        break
            except Exception as e:
                self.logger.error(f"Error checking levels for {symbol}: {e}", exc_info=True)

    def _is_level_touched(self, candle: CandleData, level_value: float) -> bool:
        tolerance = level_value * (self.tolerance_percent / 100)
        return (candle.low - tolerance) <= level_value <= (candle.high + tolerance)

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
        self.logger.info("Monitoring stopped.")