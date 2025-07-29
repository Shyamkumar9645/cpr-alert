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

    def _is_index_symbol(self, symbol: str) -> bool:
        """
        Determines if a symbol is an index based on the symbol format.
        Returns True for indexes, False for stocks.
        """
        index_patterns = [
            '-INDEX',  # NIFTY50-INDEX, NIFTYBANK-INDEX, etc.
            'SENSEX-INDEX',
            'FINNIFTY-INDEX'
        ]
        return any(pattern in symbol for pattern in index_patterns)

    def _get_alert_levels_for_symbol(self, symbol: str, levels: CPRCalculator) -> Dict[LevelType, float]:
        """
        Returns the appropriate alert levels based on whether the symbol is an index or stock.
        - Indexes: CPR (Pivot), S1, R1
        - Stocks: Only S1, R1 (no CPR/Pivot alerts)
        """
        if self._is_index_symbol(symbol):
            # For indexes: alert on all three levels
            return {
                LevelType.R1: levels.r1,
                LevelType.PIVOT: levels.pivot,  # CPR level
                LevelType.S1: levels.s1,
            }
        else:
            # For stocks: alert only on S1 and R1, skip CPR/Pivot
            return {
                LevelType.R1: levels.r1,
                LevelType.S1: levels.s1,
            }

    def initialize_daily_levels(self) -> bool:
        self.logger.info("Initializing CPR levels for all assets...")
        target_date = DateHelper.get_previous_trading_day()

        symbols_list = self.config.get('alert_settings', {}).get('symbols', [])
        if not symbols_list:
            self.logger.critical("CRITICAL ERROR: Could not find 'symbols' list in config.json.")
            return False

        success_count = 0
        index_count = 0
        stock_count = 0

        for symbol in symbols_list:
            name = symbol.split(':')[-1].replace('-EQ', '')
            is_index = self._is_index_symbol(symbol)

            if is_index:
                index_count += 1
                self.logger.info(f"Processing INDEX: {name}")
            else:
                stock_count += 1
                self.logger.info(f"Processing STOCK: {name}")

            ohlc = self.fyers_service.get_ohlc_from_intraday(symbol, target_date)

            if ohlc:
                levels = CPRCalculator.calculate_levels(ohlc)
                self.asset_data[symbol] = AssetData(name=name, symbol=symbol, levels=levels, source_data=ohlc)
                self.db_service.save_daily_levels(symbol, target_date.strftime('%Y-%m-%d'), levels, ohlc)
                success_count += 1

                # Log which levels will trigger alerts
                alert_levels = self._get_alert_levels_for_symbol(symbol, levels)
                level_names = [lt.value for lt in alert_levels.keys()]
                self.logger.info(f"✅ {name} - Alert levels: {', '.join(level_names)}")
            else:
                self.logger.error(f"Failed to calculate historical OHLC for {name} on {target_date}")

        if success_count > 0:
            self._send_daily_summary(target_date, index_count, stock_count)
            return True
        else:
            self.logger.error("Could not calculate CPR levels for ANY asset. Bot will not start.")
            return False

    def _send_daily_summary(self, calculation_date: date, index_count: int, stock_count: int):
        summary_msg = f"🎯 *Daily CPR Levels Initialized*\n"
        summary_msg += f"_Based on {calculation_date.strftime('%Y-%m-%d')} data_\n\n"
        summary_msg += f"📊 Indexes: {index_count} (CPR + S1/R1 alerts)\n"
        summary_msg += f"📈 Stocks: {stock_count} (S1/R1 alerts only)\n"
        summary_msg += f"🎯 Total assets: {len(self.asset_data)}"
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

        symbols_to_monitor = list(self.asset_data.keys())

        self.fyers_service.start_websocket(
            symbols=symbols_to_monitor,
            on_message_callback=self.on_live_data
        )

        while self.is_running:
            time.sleep(1)

    def on_live_data(self, message: Dict):
        """
        This method is called by the FyersService every time a new price tick arrives.
        Modified to handle different alert levels for indexes vs stocks.
        """
        try:
            market_status = DateHelper.get_market_status()
            if market_status != MarketStatus.OPEN:
                return

            symbol = message.get("symbol")
            ltp = message.get("ltp")

            if not symbol or not ltp:
                return

            tick_as_candle = CandleData(
                timestamp=int(time.time()),
                open=ltp, high=ltp, low=ltp, close=ltp, volume=message.get("vol_traded_today", 0)
            )

            asset_data = self.asset_data.get(symbol)
            if not asset_data:
                return

            # Get the appropriate alert levels for this symbol (index vs stock)
            key_levels = self._get_alert_levels_for_symbol(symbol, asset_data.levels)

            for level_type, level_value in key_levels.items():
                if self._is_level_touched(tick_as_candle, level_value) and self.cooldown_manager.can_send_alert(symbol):
                    asset_type = "INDEX" if self._is_index_symbol(symbol) else "STOCK"
                    self.logger.info(f"🚨 {asset_type} ALERT: {asset_data.name} touched {level_type.value} at {level_value:.2f}")

                    self._trigger_alert(asset_data, level_type, level_value, tick_as_candle)
                    self.cooldown_manager.record_alert_sent(symbol)
                    break # Move to the next symbol after an alert
        except Exception as e:
            self.logger.error(f"Error processing live data for {message.get('symbol')}: {e}", exc_info=True)

    def _is_level_touched(self, candle: CandleData, level_value: float) -> bool:
        tolerance = level_value * (self.tolerance_percent / 100)
        return (level_value - tolerance) <= candle.close <= (level_value + tolerance)

    def _trigger_alert(self, asset_data: AssetData, level_type: LevelType, level_value: float, candle: CandleData):
        # Add asset type to the log message
        asset_type = "INDEX" if self._is_index_symbol(asset_data.symbol) else "STOCK"
        self.logger.info(f"ALERT: {asset_type} {asset_data.name} touched {level_type.value} at {level_value:.2f}")

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