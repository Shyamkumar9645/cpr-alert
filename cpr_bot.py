import logging
import time
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import sys
import signal
from threading import Thread, Lock

# Import classes from their new modular locations
from config.config import ConfigManager
from core.data_classes import MarketStatus, LevelType, OHLCData, CPRLevels, CandleData, AssetData, StockCooldown
from utils.chart_generator import ChartGenerator
from services.fyers_service import FyersService
from services.notification_service import TelegramService
from utils.date_helper import DateHelper
from utils.cpr_calculator import CPRCalculator
from core.alert_cooldown_manager import AlertCooldownManager
from utils.db_manager import DatabaseService

# --- Enhanced Configuration ---
DB_FILE = Path(__file__).parent / 'cpr_alerts.db'
LOG_FILE = Path(__file__).parent / 'logs' / f'cpr_bot_{datetime.now().strftime("%Y%m%d")}.log'

# Create logs directory if it doesn't exist
LOG_FILE.parent.mkdir(exist_ok=True)

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Main Application Class ---

class CPRAlertBot:
    """Main application class orchestrating the CPR alert system with enhanced cooldown management."""
    
    def __init__(self):
        self.config = ConfigManager.load_config()
        self.token_manager = None # Placeholder for token manager, will be set up if needed
        
        # Print all loaded configurations
        print("\n" + "="*60)
        print("📋 LOADED CONFIGURATION")
        print("="*60)
        
        print("\n🔑 FYERS CONFIG:")
        fyers_config = self.config['fyers']
        print(f"  App ID: {fyers_config.get('app_id', 'NOT SET')}")
        print(f"  Access Token: {'SET' if fyers_config.get('access_token') else 'NOT SET'}")
        
        print("\n📱 TELEGRAM CONFIG:")
        telegram_config = self.config['telegram']
        print(f"  Bot Token: {'SET' if telegram_config.get('bot_token') else 'NOT SET'}")
        print(f"  Chat ID: {telegram_config.get('chat_id', 'NOT SET')}")
        
        print(f"\n📊 ASSETS ({len(self.config['assets'])} configured):")
        for i, asset in enumerate(self.config['assets'][:5], 1):  # Show first 5
            print(f"  {i}. {asset['name']} ({asset['symbol']})")
        if len(self.config['assets']) > 5:
            print(f"  ... and {len(self.config['assets']) - 5} more")
        
        print("\n⚙️ ALERT SETTINGS:")
        alert_settings = self.config['alert_settings']
        print(f"  Check Interval: {alert_settings.get('check_interval_seconds', 'DEFAULT')} seconds")
        print(f"  Tolerance: {alert_settings.get('tolerance_percent', 'DEFAULT')} %")
        print(f"  Cooldown: {alert_settings.get('cooldown_minutes', 'DEFAULT')} minutes")
        print(f"  Market Hours: {alert_settings['market_hours']['start']} - {alert_settings['market_hours']['end']}")
        
        print("\n🔧 ADVANCED SETTINGS:")
        advanced = self.config['advanced_settings']
        print(f"  Volume Analysis: {advanced.get('enable_volume_analysis', 'DEFAULT')}")
        print(f"  Min Volume: {advanced.get('min_volume_threshold', 'DEFAULT')}")
        print(f"  Strength Filtering: {advanced.get('enable_strength_filtering', 'DEFAULT')}")
        
        print("\n🛡️ SPAM PREVENTION:")
        spam = self.config['spam_prevention']
        print(f"  Max Alerts/Hour: {spam.get('max_alerts_per_hour', 'DEFAULT')}")
        print(f"  Volume Confirmation: {spam.get('require_volume_confirmation', 'DEFAULT')}")
        print(f"  Crossing Tolerance: {spam.get('crossing_tolerance_percent', 'DEFAULT')} %")
        
        print("="*60)
        print("✅ Configuration loaded successfully!")
        print("="*60 + "\n")
        
        self.db_service = DatabaseService(DB_FILE)
        self.fyers_service = FyersService(self.config['fyers'])
        self.telegram_service = TelegramService(self.config['telegram'])
        self.chart_generator = ChartGenerator()
        
        # Initialize touch detector with less sensitive tolerance
        configured_tolerance = self.config['alert_settings']['tolerance_percent']
        final_tolerance = max(configured_tolerance, 0.15)  # Minimum 0.15%
        self.touch_detector = LevelTouchDetector(tolerance_percent=final_tolerance)
        
        if final_tolerance != configured_tolerance:
            logger.info(f"📊 Touch tolerance adjusted from {configured_tolerance}% to {final_tolerance}% (spam prevention)")
        else:
            logger.info(f"📊 Touch tolerance set to {final_tolerance}%")
        
        # Initialize cooldown manager with configurable cooldown period
        cooldown_minutes = self.config['alert_settings']['cooldown_minutes']
        self.cooldown_manager = AlertCooldownManager(cooldown_minutes)
        
        # Initialize data freshness settings with spam prevention
        self.preferred_resolution = self.config['alert_settings']['preferred_resolution']
        self.check_interval = self.config['alert_settings']['check_interval_seconds']
        
        # Ensure check interval is appropriate for resolution
        if 's' in self.preferred_resolution:
            # For seconds resolution, use minimum 30s check interval
            self.check_interval = max(self.check_interval, 30)
        elif self.preferred_resolution in ['1', '3', '5']:  # 1m, 3m, 5m
            # For minute resolution, use minimum 60s check interval
            self.check_interval = max(self.check_interval, 60)
        
        self.asset_data: Dict[str, AssetData] = {}
        self.is_running = False
        self._lock = Lock()
        
        # Schedule daily level calculation
        # schedule.every().day.at("08:00").do(self._calculate_daily_levels) # Commented out as per cleanup
        
        # Initialize token management
        self._setup_token_management()
        
        # Log chart support status
        if self.chart_generator.chart_enabled:
            logger.info("📊 Chart generation enabled - will send 5min charts with alerts")
        else:
            logger.warning("📊 Chart generation disabled - install: pip install mplfinance pandas pillow matplotlib")
        
        logger.info(f"🕐 Alert cooldown period set to {self.cooldown_manager.cooldown_minutes} minutes PER STOCK")
        logger.info(f"⚡ Using {self.preferred_resolution} resolution for detection (spam-optimized)")
        logger.info(f"🔄 Check interval: {self.check_interval} seconds (spam-prevention)")
        
        # Log spam prevention settings
        if self.check_interval < 30:
            logger.warning(f"⚠️ Check interval {self.check_interval}s may cause spam alerts. Recommended: 30s+")
        if 's' in self.preferred_resolution and int(self.preferred_resolution.replace('s', '')) < 60:
            logger.warning(f"⚠️ Resolution {self.preferred_resolution} may cause spam alerts. Recommended: 1m+")
    
    def _setup_token_management(self):
        """Setup automated token management"""
        try:
            # Import here to avoid circular imports
            from generate_official_token import AutoTokenManager
            
            self.token_manager = AutoTokenManager()
            
            # Setup restart callback
            if not self.config.get('automation'):
                self.config['automation'] = {}
            
            # Set restart callback to trigger bot restart
            self.config['automation']['restart_callback'] = """
# This callback is executed when token is refreshed
if 'bot_instance' in globals():
    bot_instance.restart_manager.request_restart(new_token)
"""
            
            # Schedule token refresh at 9pm
            self.token_manager.schedule_token_refresh("21:00")
            
            logger.info("🔐 Token management setup complete - 9pm daily refresh scheduled")
            
        except Exception as e:
            logger.error(f"⚠️ Token management setup failed: {e}")
            logger.info("💡 Manual token refresh will be required")
    
    def check_token_expiry(self):
        """Check if token is expired and needs refresh"""
        if self.token_manager and self.token_manager.is_token_expired():
            logger.warning("⚠️ Token expiring soon, attempting silent refresh...")
            
            new_token = self.token_manager.silent_token_refresh()
            if new_token:
                logger.info("✅ Token refreshed successfully")
                self.restart_manager.request_restart(new_token)
            else:
                logger.error("❌ Token refresh failed - manual intervention required")
                self.telegram_service.send_alert(
                    "⚠️ **Token Refresh Required**\n"
                    "Current token is expiring soon.\n"
                    "Please run: `python generate_official_token.py`"
                )
    
    def initialize_daily_levels(self) -> bool:
        """Initialize CPR levels for all configured assets."""
        logger.info("🎯 Initializing CPR levels for all assets")
        
        target_date = DateHelper.get_previous_trading_day()
        assets = self.config.get('assets', [])
        
        success_count = 0
        
        for asset_config in assets:
            symbol = asset_config['symbol']
            name = asset_config['name']
            
            logger.info(f"Processing {name} ({symbol})")
            
            ohlc = self.fyers_service.get_historical_ohlc(symbol, target_date)
            if ohlc:
                levels = CPRCalculator.calculate_levels(ohlc)
                
                asset_data = AssetData(
                    name=name,
                    symbol=symbol,
                    levels=levels,
                    source_data=ohlc
                )
                
                self.asset_data[symbol] = asset_data
                
                # Save to database
                self.db_service.save_daily_levels(
                    symbol, target_date.strftime('%Y-%m-%d'), levels, ohlc
                )
                
                success_count += 1
                logger.info(f"✅ Success: {name} - CPR levels calculated")
                
            else:
                logger.error(f"❌ Failed: {name} - Could not get historical data")
        
        if success_count > 0:
            self._send_daily_summary(target_date)
            return True
        else:
            logger.error("Could not calculate levels for any asset")
            return False
    
    def _calculate_daily_levels(self):
        """Scheduled task to recalculate daily levels."""
        logger.info("⏰ Scheduled daily level calculation")
        self.initialize_daily_levels()
    
    def _send_daily_summary(self, calculation_date: date):
        """Send daily CPR levels summary."""
        summary_msg = f"🎯 **CPR Levels for {datetime.now().strftime('%d/%m/%Y')}**\n\n"
        summary_msg += f"📅 *Based on {calculation_date.strftime('%d/%m/%Y')} data*\n\n"
        
        for symbol, data in self.asset_data.items():
            levels = data.levels
            source = data.source_data
            summary_msg += f"📊 *{data.name}*\n"
            summary_msg += f"OHLC: `{source.open:.1f}` | `{source.high:.1f}` | `{source.low:.1f}` | `{source.close:.1f}`\n"
            summary_msg += f"S1:`{levels.s1:.1f}` BC:`{levels.bc:.1f}` P:`{levels.pivot:.1f}` TC:`{levels.tc:.1f}` R1:`{levels.r1:.1f}`\n\n"
        
        self.telegram_service.send_alert(summary_msg)
    
    def start_monitoring(self):
        """Start the main monitoring loop."""
        if not self.asset_data:
            logger.error("No asset data available. Run initialize_daily_levels() first.")
            return
        
        self.is_running = True
        # Switch Fyers service to monitoring mode
        self.fyers_service.set_monitoring_mode()
        
        logger.info(f"🔍 Starting monitoring for {len(self.asset_data)} assets")
        logger.info(f"⚡ Real-time mode: {self.preferred_resolution} candles every {self.check_interval}s")
        
        market_hours = self.config['alert_settings']['market_hours']
        
        # Start schedule checker in a separate thread
        schedule.every().day.at("08:00").do(self._run_schedule).tag('daily-levels')
        schedule_thread = Thread(target=self._run_schedule, daemon=True)
        schedule_thread.start()
        
        # Token expiry check counter
        token_check_counter = 0
        
        while self.is_running:
            try:
                current_time = datetime.now().time()
                market_status = DateHelper.is_market_time(current_time, market_hours)
                
                # Check token expiry every 30 minutes
                if token_check_counter % 90 == 0:  # Every 30 minutes (30 * 20s intervals)
                    self.check_token_expiry()
                
                if market_status == MarketStatus.OPEN:
                    self._check_level_touches()
                elif market_status == MarketStatus.CLOSED:
                    if datetime.now().time() > datetime.strptime(market_hours['end'], '%H:%M').time():
                        self._reset_daily_data()
                    time.sleep(300)  # Sleep longer when market is closed
                    continue
                
                time.sleep(self.check_interval)
                token_check_counter += 1
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait before retrying
        
        self.is_running = False
        logger.info("Monitoring stopped")
    
    def _run_schedule(self):
        """Run scheduled tasks in a separate thread."""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)
    
    def _check_level_touches(self):
        """Check all assets for level touches with stock-wide cooldown logic."""
        current_time = datetime.now()
        
        # Process assets in larger batches since we have generous API limits
        asset_items = list(self.asset_data.items())
        batch_size = 25  # Process 25 assets at a time (increased from 10)
        
        for i in range(0, len(asset_items), batch_size):
            batch = asset_items[i:i + batch_size]
            
            for symbol, asset_data in batch:
                try:
                    candle = self.fyers_service.get_latest_candle(symbol, self.preferred_resolution)
                    
                    if not candle:
                        continue
                    
                    # Thread-safe timestamp check and update
                    with self._lock:
                        if candle.timestamp <= asset_data.last_candle_timestamp:
                            continue
                        asset_data.last_candle_timestamp = candle.timestamp
                        
                        # Update recent candles for better level touch validation
                        asset_data.recent_candles.append(candle)
                        # Keep only last 5 candles
                        if len(asset_data.recent_candles) > 5:
                            asset_data.recent_candles.pop(0)
                    
                    # Check only S1, R1, and PIVOT levels (key levels)
                    key_levels = [LevelType.S1, LevelType.R1, LevelType.PIVOT]
                    
                    # Check if any level was touched in this candle (with enhanced filters)
                    levels_touched_now = []
                    
                    # Get minimum volume threshold if configured
                    min_volume = self.config['alert_settings']['min_volume_threshold']
                    
                    # Minimal delay between symbols (we have 10 calls/sec limit)
                    time.sleep(0.01)  # 10ms delay
                
                    for level_type in key_levels:
                        level_value = asset_data.levels.get_level(level_type)
                        
                        # Use enhanced touch detection with directional validation (volume filter removed)
                        if self.touch_detector.check_level_touch_with_filters(
                            candle, level_value, 
                        recent_candles=asset_data.recent_candles[:-1] if len(asset_data.recent_candles) > 1 else [],
                        min_volume=min_volume,  # Use configured min_volume_threshold
                        level_type=level_type.value
                    ):
                            levels_touched_now.append((level_type, level_value))
                    
                    # If no levels touched, continue to next stock
                    if not levels_touched_now:
                        continue
                    
                    # Generate unique alert ID for this specific candle (use all levels to prevent multiple alerts)
                    levels_touched_str = "_".join([lt.value for lt, _ in levels_touched_now])
                    alert_id = f"{symbol}_{levels_touched_str}_{candle.timestamp}"
                    
                    # Skip if we already alerted for ANY level in this exact candle
                    if alert_id in asset_data.alerted_levels:
                        continue
                    
                    # Process the most significant level touched (priority: R1 > S1 > PIVOT)
                    priority_order = {LevelType.R1: 3, LevelType.S1: 2, LevelType.PIVOT: 1}
                    first_level_type, first_level_value = max(levels_touched_now, key=lambda x: priority_order.get(x[0], 0))
                    
                    # Use real current time for cooldown logic, not candle timestamp
                    real_current_time = datetime.now()
                    
                    # Check if we can send alert (stock-wide cooldown logic)
                    if self.cooldown_manager.can_send_alert(asset_data, first_level_type, real_current_time):
                        # Get pending touches summary
                        pending_touches, pending_levels = self.cooldown_manager.get_pending_touches_summary(asset_data)
                        
                        # Record that alert is being sent
                        self.cooldown_manager.record_alert_sent(asset_data, first_level_type, real_current_time)
                        
                        # Get updated total touches
                        total_touches = self.cooldown_manager.get_total_touches(asset_data)
                        
                        # Generate chart if enabled
                        chart_buffer = None
                        if self.chart_generator.chart_enabled:
                            try:
                                # Get chart data (5-minute candles)
                                chart_candles = self.chart_generator.get_chart_data(
                                    self.fyers_service, symbol, candle_count=50, for_date=candle.datetime.date()
                                )
                                
                                if chart_candles:
                                    chart_buffer = self.chart_generator.create_cpr_chart(
                                        symbol,
                                        asset_data.name,
                                        chart_candles,
                                        asset_data.levels,
                                        first_level_type.value,
                                        candle.close
                                    )
                            except Exception as e:
                                logger.error(f"Chart generation failed for {asset_data.name}: {e}")
                        
                        # Send alert with enhanced information (including chart)
                        success = self.telegram_service.send_formatted_alert(
                            asset_data.name,
                            first_level_type,
                            first_level_value,
                            candle,
                            total_touches,
                            pending_levels,
                            chart_buffer,
                            symbol
                        )
                        
                        if success:
                            asset_data.alerted_levels.add(alert_id)
                            asset_data.alerted_levels_timestamps[alert_id] = candle.timestamp
                            
                            # Clean up old alerts to prevent memory leak
                            self._cleanup_old_alerts(asset_data, candle.timestamp)
                            
                            # Save to database
                            self.db_service.save_alert(
                                symbol, first_level_type.value, first_level_value,
                                candle.close, candle.timestamp
                            )
                            
                            # Log all levels touched with real detection time
                            levels_str = ", ".join([f"{lt.value}({lv:.2f})" for lt, lv in levels_touched_now])
                            detection_time_str = datetime.now().strftime('%H:%M:%S')
                            logger.info(f"🎯 {asset_data.name} touched {levels_str} at {detection_time_str} "
                                      f"(candle: {candle.time_str}) - Alert sent for {first_level_type.value} (Touch #{total_touches})")
                            
                            # Record other levels touched during this same candle (they go into cooldown too)
                            for level_type, _ in levels_touched_now[1:]:
                                self.cooldown_manager.record_touch_during_cooldown(asset_data, level_type)
                        else:
                            logger.error(f"Failed to send alert for {asset_data.name} {first_level_type.value}")
                    
                    else:
                        # During cooldown period - record all level touches
                        for level_type, level_value in levels_touched_now:
                            self.cooldown_manager.record_touch_during_cooldown(asset_data, level_type)
                        
                        # Log the touches but mention stock is in cooldown
                        time_until_next = self.cooldown_manager.get_time_until_next_alert(asset_data, real_current_time)
                        cooldown_status = self.cooldown_manager.get_cooldown_status(asset_data, real_current_time)
                        
                        levels_str = ", ".join([f"{lt.value}({lv:.2f})" for lt, lv in levels_touched_now])
                        detection_time_str = datetime.now().strftime('%H:%M:%S')
                        logger.info(f"🔇 {asset_data.name} touched {levels_str} at {detection_time_str} "
                                  f"(candle: {candle.time_str}) - STOCK in cooldown "
                                  f"(Total touches: {cooldown_status['total_touches']}, next alert in {time_until_next})")
                
                except Exception as e:
                    logger.error(f"Error checking levels for {symbol}: {e}")
            
            # Shorter delay between batches since we have high API limits
            if i + batch_size < len(asset_items):
                time.sleep(0.5)  # 500ms delay between batches (reduced from 2s)
    
    def _reset_daily_data(self):
        """Reset daily tracking data including stock-wide cooldowns."""
        with self._lock:
            for asset_data in self.asset_data.values():
                asset_data.alerted_levels.clear()
                asset_data.alerted_levels_timestamps.clear()
                asset_data.recent_candles.clear()
                asset_data.last_candle_timestamp = 0
                # Reset stock-wide cooldown for new trading day
                self.cooldown_manager.reset_daily_cooldowns(asset_data)
            
            logger.info("🔄 Daily data and stock-wide cooldowns reset completed")
    
    def _cleanup_old_alerts(self, asset_data: AssetData, current_timestamp: int):
        """Clean up old alert IDs to prevent memory leak."""
        cleanup_threshold = current_timestamp - 3600  # Keep alerts for 1 hour
        
        alerts_to_remove = []
        for alert_id, timestamp in asset_data.alerted_levels_timestamps.items():
            if timestamp < cleanup_threshold:
                alerts_to_remove.append(alert_id)
        
        for alert_id in alerts_to_remove:
            asset_data.alerted_levels.discard(alert_id)
            asset_data.alerted_levels_timestamps.pop(alert_id, None)
        
        if alerts_to_remove:
            logger.debug(f"Cleaned up {len(alerts_to_remove)} old alert IDs for {asset_data.symbol}")
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.is_running = False
    
    def get_status_report(self) -> str:
        """Generate a detailed status report with stock-wide cooldown information."""
        if not self.asset_data:
            return "❌ No asset data available"
        
        current_time = datetime.now()
        report = f"📊 **CPR Bot Status Report**\n"
        report += f"🕐 Time: {current_time.strftime('%H:%M:%S')}\n"
        report += f"📈 Monitoring: {len(self.asset_data)} assets\n"
        report += f"⏰ Cooldown: {self.cooldown_manager.cooldown_minutes} min per STOCK (all levels)\n\n"
        
        # Show only assets with recent activity
        active_assets = []
        for symbol, data in self.asset_data.items():
            levels = data.levels
            total_touches = self.cooldown_manager.get_total_touches(data)
            
            if total_touches > 0:
                active_assets.append((symbol, data, total_touches))
        
        if active_assets:
            report += "🎯 **Active Assets Today:**\n"
            for symbol, data, total_touches in sorted(active_assets, key=lambda x: x[2], reverse=True):
                levels = data.levels
                cooldown_status = self.cooldown_manager.get_cooldown_status(data, current_time)
                
                report += f"*{data.name}*\n"
                report += f"S1={levels.s1:.1f} | P={levels.pivot:.1f} | R1={levels.r1:.1f}\n"
                report += f"Total touches: {total_touches}\n"
                
                if cooldown_status["in_cooldown"]:
                    minutes_left = int(cooldown_status["time_remaining"].total_seconds() / 60)
                    report += f"🔇 Stock in cooldown: {minutes_left}m left\n"
                    if cooldown_status["levels_touched_during_cooldown"]:
                        report += f"Pending levels: {', '.join(cooldown_status['levels_touched_during_cooldown'])}\n"
                else:
                    report += f"✅ Ready for alerts\n"
                
                report += "\n"
        else:
            report += "📊 No level touches recorded today\n"
        
        return report

# --- Main Entry Points ---

def main():
    """Main entry point for the CPR alert bot with token management."""
    try:
        # Check required environment variables
        required_vars = ['FYERS_APP_ID', 'FYERS_ACCESS_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set the environment variables and run again.")
            return
        
        # Initialize bot
        bot = CPRAlertBot()
        
        # Make bot instance available globally for token refresh callbacks
        globals()['bot_instance'] = bot
        
        # Initialize daily levels
        if not bot.initialize_daily_levels():
            logger.error("Failed to initialize daily levels. Exiting.")
            return
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            bot.stop_monitoring()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitoring
        try:
            logger.info("🚀 Starting CPR Alert Bot with automated token management")
            bot.start_monitoring()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            bot.stop_monitoring()
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

def interactive_main():
    """Interactive main entry point."""
    try:
        # Check required environment variables
        required_vars = ['FYERS_APP_ID', 'FYERS_ACCESS_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set the environment variables and run again.")
            return
        
        bot = CPRAlertBot()
        cli = CLIInterface(bot)
        cli.run_interactive()
            
    except Exception as e:
        logger.error(f"Fatal error in interactive mode: {e}")
        raise

if __name__ == "__main__":
    # Determine if running in interactive mode or as a scheduled bot
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_main()
    else:
        main()