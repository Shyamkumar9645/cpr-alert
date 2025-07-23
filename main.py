import schedule
import time
import logging
import pytz
from threading import Thread, Lock
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

# Import project modules
from config.config import ConfigManager
from core.data_classes import AssetData, OHLCData, CPRLevels, LevelType, CandleData
from services.fyers_service import FyersService
from services.notification_service import NotificationService
from utils.db_manager import DatabaseManager
from utils.chart_generator import ChartGenerator

# --- Main Application ---
class AlertingSystem:
    def __init__(self, config, fyers_service, notifier, db_manager, chart_generator):
        self.config = config
        self.fyers = fyers_service
        self.notifier = notifier
        self.db = db_manager
        self.charting = chart_generator

        self.assets_data: Dict[str, AssetData] = {}
        self.lock = Lock()
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.logger = logging.getLogger(__name__)

    def _get_previous_trading_day(self, today: date) -> date:
        # Simple implementation: subtract days until a weekday is found.
        # Note: This does not account for market holidays.
        prev_day = today - timedelta(days=1)
        while prev_day.weekday() >= 5: # Monday is 0 and Sunday is 6
            prev_day -= timedelta(days=1)
        return prev_day

    def calculate_cpr(self, ohlc: OHLCData) -> CPRLevels:
        pivot = (ohlc.high + ohlc.low + ohlc.close) / 3
        bc = (ohlc.high + ohlc.low) / 2
        tc = (pivot - bc) + pivot
        # Ensure tc is always above bc
        if tc < bc:
            tc, bc = bc, tc

        # Standard Pivot Points
        r1 = (2 * pivot) - ohlc.low
        s1 = (2 * pivot) - ohlc.high
        r2 = pivot + (ohlc.high - ohlc.low)
        s2 = pivot - (ohlc.high - ohlc.low)
        r3 = ohlc.high + 2 * (pivot - ohlc.low)
        s3 = ohlc.low - 2 * (ohlc.high - pivot)
        r4 = r3 + (r2 - r1)
        s4 = s3 - (s1 - s2)
        return CPRLevels(pivot, bc, tc, r1, s1, r2, s2, r3, s3, r4, s4)

    def initialize_assets(self):
        self.logger.info("Initializing assets and calculating CPR for the day...")
        with self.lock:
            today = datetime.now(self.timezone).date()
            prev_trading_day = self._get_previous_trading_day(today)

            for symbol in self.config['alert_settings']['symbols']:
                self.logger.info(f"Fetching previous day's data for {symbol}...")
                hist_data = self.fyers.get_historical_data(symbol, "D", prev_trading_day, prev_trading_day)

                if not hist_data:
                    self.logger.warning(f"Could not fetch historical data for {symbol}. Skipping.")
                    continue

                # The API returns data for the 'from' date, which is the previous trading day
                prev_day_candle = hist_data[0]
                ohlc = OHLCData(open=prev_day_candle[1], high=prev_day_candle[2], low=prev_day_candle[3], close=prev_day_candle[4])
                cpr = self.calculate_cpr(ohlc)

                self.assets_data[symbol] = AssetData(symbol=symbol, previous_day_ohlc=ohlc, cpr_levels=cpr)
                self.logger.info(f"Initialized {symbol} with CPR (TC: {cpr.tc:.2f}, P: {cpr.pivot:.2f}, BC: {cpr.bc:.2f})")

        self.notifier.send_message("✅ Assets initialized for the day!")

    def _check_crossover(self, symbol, ltp, asset_data):
        levels_to_check = {
            LevelType.CPR_TOP: asset_data.cpr_levels.tc,
            LevelType.CPR_PIVOT: asset_data.cpr_levels.pivot,
            LevelType.CPR_BOTTOM: asset_data.cpr_levels.bc,
            LevelType.SUPPORT: asset_data.cpr_levels.s1,
            LevelType.RESISTANCE: asset_data.cpr_levels.r1,
        }
        # This is a simplified check. A proper implementation would track previous LTP.
        # For now, we'll alert if price is very close to a level.
        for level_type, level_value in levels_to_check.items():
            if abs(ltp - level_value) / level_value < 0.001: # within 0.1%
                self.trigger_alert(symbol, ltp, level_type, level_value)

    def trigger_alert(self, symbol, ltp, level_type, level_value):
        now = datetime.now(self.timezone)
        last_alert_time = self.db.get_last_alert_time(symbol)
        cooldown_minutes = self.config['alert_settings']['cooldown_minutes']

        if last_alert_time and (now - last_alert_time) < timedelta(minutes=cooldown_minutes):
            self.logger.info(f"Alert for {symbol} is on cooldown. Skipping.")
            return

        self.logger.info(f"ALERT: Triggering for {symbol} at {ltp}, crossed {level_type.value}")
        self.db.update_last_alert_time(symbol, now)

        message = (
            f"**🚨 CPR Alert: {symbol.split(':')[-1]} 🚨**\n\n"
            f"Price **{ltp:.2f}** has crossed a key level:\n"
            f"**Level Type:** {level_type.value}\n"
            f"**Level Price:** {level_value:.2f}"
        )

        # Generate and send chart
        today = datetime.now(self.timezone).date()
        timeframe = self.config['alert_settings']['timeframe']
        candle_data_raw = self.fyers.get_historical_data(symbol, timeframe, today, today)

        if candle_data_raw:
            candles = [CandleData(timestamp=c[0], open=c[1], high=c[2], low=c[3], close=c[4]).__dict__ for c in candle_data_raw]
            chart_file = self.charting.create_cpr_chart(
                symbol, candles, self.assets_data[symbol].cpr_levels.__dict__, ltp
            )
            self.notifier.send_message(message, photo_path=chart_file)
        else:
            self.notifier.send_message(message)


    def check_for_alerts(self):
        self.logger.info("Running alert check...")
        symbols = list(self.assets_data.keys())
        if not symbols:
            self.logger.warning("No assets initialized. Skipping alert check.")
            return

        quotes = self.fyers.get_quotes(symbols)
        if not quotes:
            self.logger.error("Could not fetch live quotes.")
            return

        with self.lock:
            for quote in quotes:
                symbol = quote['n']
                ltp = quote['v']['lp']

                if symbol in self.assets_data:
                    self._check_crossover(symbol, ltp, self.assets_data[symbol])

    def run(self):
        self.logger.info("Starting CPR Alerting System...")
        self.notifier.send_message("🚀 CPR Bot is starting up!")

        # Verify Fyers connection
        if not self.fyers.get_profile():
             self.logger.critical("Fyers connection failed. Exiting.")
             self.notifier.send_message("❌ Fyers connection failed! Bot is shutting down.")
             return

        # Initial run
        self.initialize_assets()

        # Schedule jobs
        schedule.every().day.at("08:45:00").do(self.initialize_assets)
        schedule.every(self.config['alert_settings']['check_interval_seconds']).seconds.do(self.check_for_alerts)

        self.logger.info("Scheduler started. Waiting for jobs...")
        while True:
            schedule.run_pending()
            time.sleep(1)

def main():
    """Main function to configure and run the CPR bot."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger(__name__)

    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()

        fyers_service = FyersService(config['fyers_credentials'])
        notifier = NotificationService(config['telegram_credentials'])
        db_manager = DatabaseManager()
        chart_generator = ChartGenerator()

        alert_system = AlertingSystem(config, fyers_service, notifier, db_manager, chart_generator)
        alert_system.run()

    except FileNotFoundError as e:
        logger.critical(f"Configuration Error: {e}. Please ensure config.json and .env are set up correctly.")
    except (ValueError, KeyError) as e:
        logger.critical(f"Credential Error: {e}. Please check your .env file.")
    except Exception as e:
        logger.exception(f"A fatal error occurred in the main application: {e}")
        # Attempt to notify if notifier is available
        try:
            notifier.send_message(f"🚨 CPR Bot has crashed! Error: {e}")
        except:
            pass
    finally:
        # Clean up
        if 'db_manager' in locals():
            db_manager.close()

if __name__ == "__main__":
    main()