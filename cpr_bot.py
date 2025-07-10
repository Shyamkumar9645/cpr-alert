import json
import logging
import time
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import requests
from fyers_apiv3 import fyersModel
import schedule
from threading import Thread, Lock
import sqlite3
from pathlib import Path
import sys
import signal
import subprocess
import io
try:
    import mplfinance as mpf
    import pandas as pd
    from PIL import Image
    import matplotlib.pyplot as plt
    CHART_SUPPORT = True
except ImportError as e:
    logger.warning(f"Chart dependencies not installed: {e}. Charts will be disabled.")
    CHART_SUPPORT = False

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

# --- Data Classes and Enums ---




class MarketStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    POST_MARKET = "post_market"

class LevelType(Enum):
    S1 = "S1"
    BC = "BC"
    PIVOT = "PIVOT"
    TC = "TC"
    R1 = "R1"

@dataclass
class OHLCData:
    open: float
    high: float
    low: float
    close: float
    date: date
    volume: Optional[int] = None
    source: str = "historical"

@dataclass
class CPRLevels:
    pivot: float
    tc: float
    bc: float
    r1: float
    s1: float
    
    def get_level(self, level_type: LevelType) -> float:
        return getattr(self, level_type.value.lower())

@dataclass
class CandleData:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    datetime: datetime
    time_str: str

@dataclass
class StockCooldown:
    """Tracks cooldown for entire stock (all levels)."""
    last_alert_time: datetime
    initial_level_touched: LevelType  # First level that triggered the cooldown
    total_touches: int = 1
    levels_touched_during_cooldown: Dict[str, int] = field(default_factory=dict)  # Levels touched during cooldown

@dataclass
class AssetData:
    name: str
    symbol: str
    levels: CPRLevels
    source_data: OHLCData
    last_candle_timestamp: int = 0
    alerted_levels: set = field(default_factory=set)  # For same-candle deduplication
    stock_cooldown: Optional[StockCooldown] = None  # Single cooldown for entire stock
    alerted_levels_timestamps: Dict[str, int] = field(default_factory=dict)  # Track alert timestamps for cleanup
    recent_candles: List[CandleData] = field(default_factory=list)  # Track recent candles for better validation

class ChartGenerator:
    """Generates candlestick charts with CPR levels for alerts."""
    
    def __init__(self):
        self.chart_enabled = CHART_SUPPORT
        if not self.chart_enabled:
            logger.warning("Chart generation disabled - missing dependencies")
    
    def create_cpr_chart(self, symbol: str, asset_name: str, candle_data: List[CandleData], 
                        cpr_levels: CPRLevels, current_level: LevelType, 
                        current_price: float) -> Optional[io.BytesIO]:
        """Create 5-minute candlestick chart with CPR levels."""
        
        if not self.chart_enabled or not candle_data:
            return None
        
        try:
            # Prepare data for mplfinance
            chart_data = []
            for candle in candle_data:
                chart_data.append({
                    'datetime': candle.datetime,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                })
            
            df = pd.DataFrame(chart_data)
            df.set_index('datetime', inplace=True)
            df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            
            # Create horizontal lines for CPR levels (exactly matching reference image)
            hlines = dict(
                hlines=[cpr_levels.s1, cpr_levels.pivot, cpr_levels.r1],  # Key levels
                colors=['green', 'blue', 'red'],  # Green for S1, blue for pivot, red for R1
                linestyle='--',  # Dashed lines (more visible than dotted)
                linewidths=2,  # Thicker lines for visibility
                alpha=0.8  # Semi-transparent
            )
            
            # Create style matching reference image exactly
            mc = mpf.make_marketcolors(
                up='#26a69a', down='#ef5350',  # Standard trading colors
                edge='inherit',
                wick='inherit',
                volume={'up': '#26a69a', 'down': '#ef5350'}  # Volume colors
            )
            
            style = mpf.make_mpf_style(
                marketcolors=mc,
                gridstyle='-',        # Solid grid lines like reference
                gridcolor='#e0e0e0',  # Light gray grid
                facecolor='white',    # White background like reference
                figcolor='white',     # White figure background
                edgecolor='black',
                y_on_right=True       # Price labels on right side
            )
            
            # Create compact chart with no title to save space
            fig, axes = mpf.plot(
                df,
                type='candle',
                style=style,
                title='',  # No title for compact design
                volume=True,
                hlines=hlines,
                figsize=(10, 6),  # More compact size
                tight_layout=False,  # Manual layout control
                returnfig=True,
                datetime_format='%H:%M',
                xrotation=0
            )
            
            # Clean styling like reference image - no heavy backgrounds
            ax = axes[0]
            
            # Manually draw CPR level lines to ensure they're visible
            ax.axhline(y=cpr_levels.s1, color='green', linestyle=':', linewidth=2, alpha=0.8)
            ax.axhline(y=cpr_levels.pivot, color='blue', linestyle=':', linewidth=2, alpha=0.8)
            ax.axhline(y=cpr_levels.r1, color='red', linestyle=':', linewidth=2, alpha=0.8)
            
            # Add compact title in top left corner
            ax.text(0.02, 0.98, f'{asset_name} - CPR Levels', transform=ax.transAxes, 
                   verticalalignment='top', horizontalalignment='left', 
                   color='black', fontweight='bold', fontsize=10)
            
            # Add level info in top right corner
            level_text = f'S1:{cpr_levels.s1:.0f} | P:{cpr_levels.pivot:.0f} | R1:{cpr_levels.r1:.0f}'
            ax.text(0.98, 0.98, level_text, transform=ax.transAxes, 
                   verticalalignment='top', horizontalalignment='right', 
                   color='black', fontweight='bold', fontsize=9)
            
            # Current price alert in top right
            ax.text(0.98, 0.93, f'{current_level.value} Alert: {current_price:.2f}', transform=ax.transAxes, 
                   verticalalignment='top', horizontalalignment='right', 
                   color='red', fontweight='bold', fontsize=9)
            
            # Compact layout - remove extra white space
            fig.subplots_adjust(top=0.97, bottom=0.15, left=0.08, right=0.95, hspace=0.1)
            
            # Remove extra margins and make chart fill the space
            if len(axes) > 1:  # Volume subplot
                axes[1].margins(x=0)
            
            # Save to bytes buffer with minimal padding
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0.1, facecolor='white')
            buf.seek(0)
            
            # Clean up
            plt.close(fig)
            
            logger.info(f"Chart generated successfully for {symbol}")
            return buf
            
        except Exception as e:
            logger.error(f"Error generating chart for {symbol}: {e}")
            return None
    
    def get_chart_data(self, fyers_service, symbol: str, candle_count: int = 78) -> List[CandleData]:
        """Get 5-minute candle data spanning today and yesterday for comprehensive chart."""
        try:
            end_time = datetime.now()
            # Get data from yesterday to cover both days
            start_time = end_time - timedelta(days=2)  # 2 days to ensure we get yesterday + today
            
            data = {
                "symbol": symbol,
                "resolution": "5",  # 5 minute candles
                "date_format": "1",
                "range_from": start_time.strftime('%Y-%m-%d'),
                "range_to": end_time.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            response = fyers_service.client.history(data=data)
            
            if response.get('s') == 'ok' and response.get('candles'):
                candles = response['candles']
                chart_candles = []
                
                # Take last 'candle_count' candles
                for candle in candles[-candle_count:]:
                    timestamp, o, h, l, c, volume = candle
                    candle_datetime = datetime.fromtimestamp(timestamp)
                    
                    chart_candles.append(CandleData(
                        timestamp=timestamp,
                        open=o,
                        high=h,
                        low=l,
                        close=c,
                        volume=volume,
                        datetime=candle_datetime,
                        time_str=candle_datetime.strftime('%H:%M')
                    ))
                
                return chart_candles
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching chart data for {symbol}: {e}")
            return []

# --- Helper Functions and Classes ---

class ConfigManager:
    """Manages configuration loading and validation."""
    
    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Loads configuration from environment variables."""
        config = {
            'fyers': {
                'app_id': os.getenv('FYERS_APP_ID'),
                'access_token': os.getenv('FYERS_ACCESS_TOKEN')
            },
            'telegram': {
                'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
                'chat_id': os.getenv('TELEGRAM_CHAT_ID')
            },
            'assets': [
                {'symbol': 'NSE:NIFTY50-INDEX', 'name': 'NIFTY 50', 'type': 'index', 'category': 'INDEX'},
                {'symbol': 'NSE:NIFTYBANK-INDEX', 'name': 'BANK NIFTY', 'type': 'index', 'category': 'INDEX'},
                {'symbol': 'NSE:FINNIFTY-INDEX', 'name': 'NIFTY FINANCIAL', 'type': 'index', 'category': 'INDEX'},
                {'symbol': 'NSE:RELIANCE-EQ', 'name': 'RELIANCE', 'type': 'stock', 'category': 'ENERGY'},
                {'symbol': 'NSE:HDFCBANK-EQ', 'name': 'HDFC BANK', 'type': 'stock', 'category': 'BANKING'},
                {'symbol': 'NSE:ICICIBANK-EQ', 'name': 'ICICI BANK', 'type': 'stock', 'category': 'BANKING'},
                {'symbol': 'NSE:AXISBANK-EQ', 'name': 'AXIS BANK', 'type': 'stock', 'category': 'BANKING'},
                {'symbol': 'NSE:SBIN-EQ', 'name': 'STATE BANK', 'type': 'stock', 'category': 'BANKING'},
                {'symbol': 'NSE:TATAMOTORS-EQ', 'name': 'TATA MOTORS', 'type': 'stock', 'category': 'AUTO'},
                {'symbol': 'NSE:BAJFINANCE-EQ', 'name': 'BAJAJ FINANCE', 'type': 'stock', 'category': 'FINANCE'}
            ],
            'alert_settings': {
                'check_interval_seconds': int(os.getenv('CHECK_INTERVAL_SECONDS', '20')),
                'tolerance_percent': float(os.getenv('TOLERANCE_PERCENT', '0.05')),
                'cooldown_minutes': int(os.getenv('COOLDOWN_MINUTES', '30')),
                'preferred_resolution': os.getenv('PREFERRED_RESOLUTION', '1'),
                'focus_on_key_levels': os.getenv('FOCUS_ON_KEY_LEVELS', 'true').lower() == 'true',
                'min_volume_threshold': int(os.getenv('MIN_VOLUME_THRESHOLD', '5000')),
                'enable_spam_prevention': os.getenv('ENABLE_SPAM_PREVENTION', 'true').lower() == 'true',
                'strict_level_crossing': os.getenv('STRICT_LEVEL_CROSSING', 'true').lower() == 'true',
                'market_hours': {
                    'start': os.getenv('MARKET_START_TIME', '09:15'),
                    'end': os.getenv('MARKET_END_TIME', '15:30'),
                    'pre_market_start': os.getenv('PRE_MARKET_START', '09:00'),
                    'post_market_end': os.getenv('POST_MARKET_END', '15:45')
                }
            },
            'advanced_settings': {
                'enable_volume_analysis': os.getenv('ENABLE_VOLUME_ANALYSIS', 'true').lower() == 'true',
                'min_volume_threshold': int(os.getenv('MIN_VOLUME_THRESHOLD', '5000')),
                'enable_strength_filtering': os.getenv('ENABLE_STRENGTH_FILTERING', 'true').lower() == 'true',
                'min_touch_strength': float(os.getenv('MIN_TOUCH_STRENGTH', '0.4')),
                'enable_trend_analysis': os.getenv('ENABLE_TREND_ANALYSIS', 'false').lower() == 'true',
                'enable_volatility_filter': os.getenv('ENABLE_VOLATILITY_FILTER', 'true').lower() == 'true'
            },
            'spam_prevention': {
                'min_candle_range_ratio': float(os.getenv('MIN_CANDLE_RANGE_RATIO', '0.3')),
                'max_alerts_per_hour': int(os.getenv('MAX_ALERTS_PER_HOUR', '12')),
                'require_volume_confirmation': os.getenv('REQUIRE_VOLUME_CONFIRMATION', 'true').lower() == 'true',
                'strict_crossing_validation': os.getenv('STRICT_CROSSING_VALIDATION', 'true').lower() == 'true',
                'crossing_tolerance_percent': float(os.getenv('CROSSING_TOLERANCE_PERCENT', '0.02'))
            }
        }
        
        ConfigManager._validate_config(config)
        return config

    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> None:
        """Validates the configuration structure."""
        # Validate required environment variables
        required_vars = ['FYERS_APP_ID', 'FYERS_ACCESS_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Validate Fyers config
        fyers_config = config['fyers']
        if not all(key in fyers_config and fyers_config[key] for key in ['app_id', 'access_token']):
            raise ValueError("Missing required Fyers configuration")
        
        # Validate Telegram config
        telegram_config = config['telegram']
        if not all(key in telegram_config and telegram_config[key] for key in ['bot_token', 'chat_id']):
            raise ValueError("Missing required Telegram configuration")
        
        # Validate assets
        if not config['assets']:
            raise ValueError("No assets configured")

class DateHelper:
    """Helper class for date-related operations."""
    
    @staticmethod
    def get_previous_trading_day(reference_date: Optional[date] = None) -> date:
        """Gets the previous trading day, accounting for weekends."""
        if reference_date is None:
            reference_date = date.today()
        
        previous_day = reference_date - timedelta(days=1)
        
        # Handle weekends
        if reference_date.weekday() == 0:  # Monday
            previous_day = reference_date - timedelta(days=3)  # Friday
        elif reference_date.weekday() == 6:  # Sunday
            previous_day = reference_date - timedelta(days=2)  # Friday
        
        logger.info(f"Reference: {reference_date}, Previous trading day: {previous_day}")
        return previous_day

    @staticmethod
    def is_market_time(current_time: time, market_hours: Dict[str, str]) -> MarketStatus:
        """Determines current market status."""
        start_time = datetime.strptime(market_hours['start'], '%H:%M').time()
        end_time = datetime.strptime(market_hours['end'], '%H:%M').time()
        
        pre_market_start = datetime.strptime(market_hours.get('pre_market_start', '09:00'), '%H:%M').time()
        post_market_end = datetime.strptime(market_hours.get('post_market_end', '15:45'), '%H:%M').time()
        
        if start_time <= current_time <= end_time:
            return MarketStatus.OPEN
        elif pre_market_start <= current_time < start_time:
            return MarketStatus.PRE_MARKET
        elif end_time < current_time <= post_market_end:
            return MarketStatus.POST_MARKET
        else:
            return MarketStatus.CLOSED

class CPRCalculator:
    """Handles CPR level calculations."""
    
    @staticmethod
    def calculate_levels(ohlc: OHLCData) -> CPRLevels:
        """Calculates CPR levels from OHLC data."""
        pivot = (ohlc.high + ohlc.low + ohlc.close) / 3
        bc = (ohlc.high + ohlc.low) / 2
        tc = (pivot - bc) + pivot
        r1 = (2 * pivot) - ohlc.low
        s1 = (2 * pivot) - ohlc.high
        
        return CPRLevels(
            pivot=pivot,
            tc=tc,
            bc=bc,
            r1=r1,
            s1=s1
        )

# --- Touch Detection and Cooldown Classes ---

class LevelTouchDetector:
    """Detects level touches with configurable tolerance and validation."""
    
    def __init__(self, tolerance_percent: float = 0.25):  # Increased default from 0.1% to 0.25%
        self.tolerance_percent = tolerance_percent
        logger.info(f"LevelTouchDetector initialized with {tolerance_percent}% tolerance")
        
        # Warn if tolerance is too sensitive
        if tolerance_percent < 0.15:
            logger.warning(f"⚠️ Tolerance {tolerance_percent}% is very sensitive and may cause spam alerts")
    
    def check_level_touch(self, candle: CandleData, level_value: float) -> bool:
        """Check if a candle actually touched/crossed a specific level with minimal tolerance."""
        if not candle:
            return False
        
        # Use much smaller tolerance for actual level touch (0.05% max)
        actual_tolerance_percent = min(self.tolerance_percent, 0.05)
        tolerance = level_value * (actual_tolerance_percent / 100)
        
        # Check if the candle actually touched the level (not just came close)
        # The level must be within the candle's high-low range with minimal tolerance
        level_touched = (candle.low - tolerance) <= level_value <= (candle.high + tolerance)
        
        # Additional check: ensure the touch is meaningful (not just a wick)
        if level_touched:
            # For support levels (S1), check if price went down to the level
            # For resistance levels (R1), check if price went up to the level
            # For pivot, check either direction
            candle_range = candle.high - candle.low
            touch_significance = min(abs(candle.low - level_value), abs(candle.high - level_value))
            
            # Touch should be within tolerance and significant relative to candle size
            return touch_significance <= tolerance and candle_range > tolerance * 2
        
        return False
    
    def get_touch_strength(self, candle: CandleData, level_value: float) -> float:
        """Calculate how strongly the candle touched the level (0-1)."""
        if not self.check_level_touch(candle, level_value):
            return 0.0
        
        # Calculate overlap between candle range and level
        tolerance = level_value * (self.tolerance_percent / 100)
        level_range = (level_value - tolerance, level_value + tolerance)
        candle_range = (candle.low, candle.high)
        
        overlap_start = max(candle_range[0], level_range[0])
        overlap_end = min(candle_range[1], level_range[1])
        overlap_size = overlap_end - overlap_start
        
        level_size = level_range[1] - level_range[0]
        return min(1.0, overlap_size / level_size)
    
    def check_volatility_filter(self, candle: CandleData, recent_candles: List[CandleData] = None) -> bool:
        """Check if the touch is significant enough based on volatility."""
        if not recent_candles or len(recent_candles) < 3:
            return True  # Allow if not enough data
        
        # Calculate average candle range from recent candles
        avg_range = sum((c.high - c.low) for c in recent_candles[-5:]) / min(5, len(recent_candles))
        current_range = candle.high - candle.low
        
        # If current candle range is too small compared to average, it might be noise
        if current_range < avg_range * 0.3:  # Less than 30% of average range
            return False
        
        return True
    
    def check_level_touch_with_filters(self, candle: CandleData, level_value: float, 
                                     recent_candles: List[CandleData] = None, 
                                     min_volume: int = 0, 
                                     level_type: str = None) -> bool:
        """Enhanced level touch detection with spam filters and directional validation."""
        # Basic level touch check with strict tolerance
        if not self.check_level_touch(candle, level_value):
            return False
        
        # Volume filter - REMOVED (no longer required)
        # Volatility filter - REMOVED (no longer required)
        
        # Strict level crossing validation
        if level_type and recent_candles and len(recent_candles) > 0:
            prev_candle = recent_candles[-1]
            
            # Use actual level crossing logic instead of just proximity
            if not self.check_actual_level_cross(candle, prev_candle, level_value, level_type):
                return False
        
        return True
    
    def check_actual_level_cross(self, current_candle: CandleData, previous_candle: CandleData, 
                                level_value: float, level_type: str) -> bool:
        """Check if price actually crossed the level, not just came close."""
        if not previous_candle:
            return False
        
        tolerance = level_value * 0.02 / 100  # Very tight 0.02% tolerance for crossing
        
        if level_type == 'S1':  # Support level
            # Price should cross from above to below (or bounce off)
            prev_above = previous_candle.low > (level_value + tolerance)
            curr_touches = (current_candle.low - tolerance) <= level_value <= (current_candle.high + tolerance)
            return prev_above and curr_touches
            
        elif level_type == 'R1':  # Resistance level
            # Price should cross from below to above (or reject from)
            prev_below = previous_candle.high < (level_value - tolerance)
            curr_touches = (current_candle.low - tolerance) <= level_value <= (current_candle.high + tolerance)
            return prev_below and curr_touches
            
        elif level_type == 'PIVOT':  # Pivot level
            # Price should cross from either side
            prev_above = previous_candle.close > (level_value + tolerance)
            prev_below = previous_candle.close < (level_value - tolerance)
            curr_touches = (current_candle.low - tolerance) <= level_value <= (current_candle.high + tolerance)
            return (prev_above or prev_below) and curr_touches
        
        return False

class AlertCooldownManager:
    """Manages stock-wide cooldown periods for level touch alerts."""
    
    def __init__(self, cooldown_minutes: int = 30):  # Increased from 15 to 30 minutes
        # Ensure minimum cooldown to prevent spam
        self.cooldown_minutes = max(cooldown_minutes, 20)  # Minimum 20 minutes
        self.cooldown_duration = timedelta(minutes=self.cooldown_minutes)
        
        if self.cooldown_minutes != cooldown_minutes:
            logger.info(f"AlertCooldownManager cooldown adjusted from {cooldown_minutes} to {self.cooldown_minutes} minutes (spam prevention)")
        else:
            logger.info(f"AlertCooldownManager initialized with {self.cooldown_minutes} minute STOCK-WIDE cooldown")
        
        # Warn if cooldown is too short
        if self.cooldown_minutes < 25:
            logger.warning(f"⚠️ Cooldown {self.cooldown_minutes}min may still allow spam alerts. Recommended: 30min+")
    
    def can_send_alert(self, asset_data: AssetData, level_type: LevelType, current_time: datetime) -> bool:
        """Check if we can send an alert for this stock (any level)."""
        # If no previous alert for this stock, always allow
        if asset_data.stock_cooldown is None:
            return True
        
        time_since_last_alert = current_time - asset_data.stock_cooldown.last_alert_time
        
        # Check if cooldown period has passed
        return time_since_last_alert >= self.cooldown_duration
    
    def record_alert_sent(self, asset_data: AssetData, level_type: LevelType, current_time: datetime):
        """Record that an alert was sent for this stock."""
        if asset_data.stock_cooldown is None:
            # First alert for this stock
            asset_data.stock_cooldown = StockCooldown(
                last_alert_time=current_time,
                initial_level_touched=level_type,
                total_touches=1,
                levels_touched_during_cooldown={}
            )
        else:
            # Update existing cooldown - this means cooldown period has expired
            pending_touches = sum(asset_data.stock_cooldown.levels_touched_during_cooldown.values())
            asset_data.stock_cooldown.last_alert_time = current_time
            asset_data.stock_cooldown.initial_level_touched = level_type
            asset_data.stock_cooldown.total_touches += 1 + pending_touches
            asset_data.stock_cooldown.levels_touched_during_cooldown.clear()
    
    def record_touch_during_cooldown(self, asset_data: AssetData, level_type: LevelType):
        """Record a touch that occurred during cooldown period."""
        if asset_data.stock_cooldown is not None:
            level_key = level_type.value
            current_count = asset_data.stock_cooldown.levels_touched_during_cooldown.get(level_key, 0)
            asset_data.stock_cooldown.levels_touched_during_cooldown[level_key] = current_count + 1
    
    def get_pending_touches_summary(self, asset_data: AssetData) -> Tuple[int, List[str]]:
        """Get summary of pending touches during cooldown."""
        if asset_data.stock_cooldown is None:
            return 0, []
        
        total_pending = sum(asset_data.stock_cooldown.levels_touched_during_cooldown.values())
        levels_touched = list(asset_data.stock_cooldown.levels_touched_during_cooldown.keys())
        
        return total_pending, levels_touched
    
    def get_total_touches(self, asset_data: AssetData) -> int:
        """Get total touches for this stock today."""
        if asset_data.stock_cooldown is None:
            return 0
        
        pending_touches = sum(asset_data.stock_cooldown.levels_touched_during_cooldown.values())
        return asset_data.stock_cooldown.total_touches + pending_touches
    
    def get_time_until_next_alert(self, asset_data: AssetData, current_time: datetime) -> Optional[timedelta]:
        """Get time remaining until next alert can be sent for this stock."""
        if asset_data.stock_cooldown is None:
            return None
        
        time_since_last = current_time - asset_data.stock_cooldown.last_alert_time
        
        if time_since_last >= self.cooldown_duration:
            return None
        
        return self.cooldown_duration - time_since_last
    
    def get_cooldown_status(self, asset_data: AssetData, current_time: datetime) -> Dict[str, Any]:
        """Get detailed cooldown status for this stock."""
        if asset_data.stock_cooldown is None:
            return {"in_cooldown": False, "can_alert": True}
        
        time_until_next = self.get_time_until_next_alert(asset_data, current_time)
        pending_touches, levels_touched = self.get_pending_touches_summary(asset_data)
        
        return {
            "in_cooldown": time_until_next is not None,
            "can_alert": time_until_next is None,
            "time_remaining": time_until_next,
            "initial_level": asset_data.stock_cooldown.initial_level_touched.value,
            "total_touches": self.get_total_touches(asset_data),
            "pending_touches": pending_touches,
            "levels_touched_during_cooldown": levels_touched
        }
    
    def reset_daily_cooldowns(self, asset_data: AssetData):
        """Reset cooldown for a new trading day."""
        asset_data.stock_cooldown = None

# --- Enhanced Service Classes ---

class DatabaseService:
    """Handles database operations for storing alerts and historical data."""
    
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    level_type TEXT NOT NULL,
                    level_value REAL NOT NULL,
                    touch_price REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    date_sent TEXT NOT NULL,
                    UNIQUE(symbol, level_type, timestamp)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    pivot REAL NOT NULL,
                    tc REAL NOT NULL,
                    bc REAL NOT NULL,
                    r1 REAL NOT NULL,
                    s1 REAL NOT NULL,
                    source_ohlc TEXT NOT NULL,
                    UNIQUE(symbol, date)
                )
            ''')
    
    def save_alert(self, symbol: str, level_type: str, level_value: float, 
                   touch_price: float, timestamp: int):
        """Save an alert to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR IGNORE INTO alerts 
                    (symbol, level_type, level_value, touch_price, timestamp, date_sent)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, level_type, level_value, touch_price, timestamp, 
                      datetime.now().isoformat()))
        except Exception as e:
            logger.error(f"Error saving alert: {e}")
    
    def save_daily_levels(self, symbol: str, date_str: str, levels: CPRLevels, 
                         source_ohlc: OHLCData):
        """Save daily CPR levels to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO daily_levels 
                    (symbol, date, pivot, tc, bc, r1, s1, source_ohlc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, date_str, levels.pivot, levels.tc, levels.bc, 
                      levels.r1, levels.s1, json.dumps({
                          'open': source_ohlc.open,
                          'high': source_ohlc.high,
                          'low': source_ohlc.low,
                          'close': source_ohlc.close,
                          'volume': source_ohlc.volume,
                          'source': source_ohlc.source
                      })))
        except Exception as e:
            logger.error(f"Error saving daily levels: {e}")

class TelegramService:
    """Enhanced Telegram service with retry logic and rate limiting."""
    
    def __init__(self, config: Dict[str, Any]):
        self.bot_token = config.get('bot_token')
        self.chat_id = config.get('chat_id')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.last_message_time = 0
        self.min_interval = 5  # Minimum seconds between messages (increased from 1)
        self.burst_count = 0
        self.burst_window_start = 0
        self.max_burst_messages = 3  # Max 3 messages per burst window
        self.burst_window_seconds = 60  # 1 minute burst window
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("Telegram bot_token or chat_id is missing in config.")
        
        # URLs for different message types
        self.photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

    def send_alert(self, message: str, max_retries: int = 3) -> bool:
        """Sends a message with retry logic and enhanced rate limiting."""
        current_time = time.time()
        
        # Check burst protection
        if current_time - self.burst_window_start > self.burst_window_seconds:
            # Reset burst window
            self.burst_window_start = current_time
            self.burst_count = 0
        
        if self.burst_count >= self.max_burst_messages:
            logger.warning(f"Telegram rate limit: {self.burst_count} messages sent in {self.burst_window_seconds}s window")
            return False
        
        # Basic rate limiting
        time_since_last = current_time - self.last_message_time
        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)
        
        payload = {
            'chat_id': self.chat_id,
            'text': message[:4096],  # Telegram message limit
            'parse_mode': 'Markdown'
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(self.base_url, data=payload, timeout=10)
                response.raise_for_status()
                self.last_message_time = time.time()
                self.burst_count += 1
                logger.info(f"Alert sent successfully (attempt {attempt + 1})")
                return True
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to send alert (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Failed to send alert after {max_retries} attempts")
        return False
    
    def send_photo_with_caption(self, photo_buffer: io.BytesIO, caption: str, max_retries: int = 3) -> bool:
        """Send a photo with caption to Telegram."""
        current_time = time.time()
        
        # Check rate limiting
        if current_time - self.burst_window_start > self.burst_window_seconds:
            self.burst_window_start = current_time
            self.burst_count = 0
        
        if self.burst_count >= self.max_burst_messages:
            logger.warning(f"Telegram rate limit reached, skipping photo")
            return False
        
        time_since_last = current_time - self.last_message_time
        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)
        
        for attempt in range(max_retries):
            try:
                # Reset buffer position
                photo_buffer.seek(0)
                
                files = {
                    'photo': ('chart.png', photo_buffer, 'image/png')
                }
                
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption[:1024],  # Telegram caption limit
                    'parse_mode': 'Markdown'
                }
                
                response = requests.post(self.photo_url, files=files, data=data, timeout=30)
                response.raise_for_status()
                
                self.last_message_time = time.time()
                self.burst_count += 1
                logger.info(f"Chart sent successfully (attempt {attempt + 1})")
                return True
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to send chart (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        logger.error(f"Failed to send chart after {max_retries} attempts")
        return False

    def send_formatted_alert(self, asset_name: str, level_type: LevelType, 
                           level_value: float, candle: CandleData, 
                           total_touches: int = 1, pending_levels: List[str] = None,
                           chart_buffer: Optional[io.BytesIO] = None, 
                           symbol: str = None) -> bool:
        """Sends a formatted level touch alert with real-time detection info and optional chart."""
        emoji_map = {
            LevelType.S1: '📉',
            LevelType.R1: '🚨',
            LevelType.PIVOT: '⚖️',
            LevelType.BC: '🔵',
            LevelType.TC: '🔴'
        }
        
        emoji = emoji_map.get(level_type, '🎯')
        
        # Get current real time for instant detection
        detection_time = datetime.now()
        
        # Create main alert message
        message = f"{emoji} *{level_type.value} Touch Alert*"
        
        # Add touch count information
        if total_touches > 1:
            message += f" *(Touch #{total_touches})*"
        
        # Add information about other levels touched during cooldown
        if pending_levels and len(pending_levels) > 0:
            levels_str = ", ".join(pending_levels)
            message += f" *[Also: {levels_str}]*"
        
        message += f"\n*{asset_name}* touched {level_type.value} level!\n\n"
        message += f"📊 *Level:* `{level_value:.2f}`\n"
        message += f"🚨 *Alert Time:* `{detection_time.strftime('%H:%M:%S')}` *(REAL-TIME)*\n"
        message += f"📅 *Data Time:* `{candle.time_str}`\n"
        
        
        # Skip significance indicators, cooldown info, and chart info
        
        # Send chart with caption if available, otherwise send text message
        if chart_buffer:
            success = self.send_photo_with_caption(chart_buffer, message)
            if not success:
                # Fallback to text message if chart fails
                logger.warning(f"Chart failed for {asset_name}, sending text alert")
                return self.send_alert(message)
            return success
        else:
            return self.send_alert(message)

class FyersService:
    """Enhanced Fyers service with better error handling and data validation."""
    
    def __init__(self, config: Dict[str, Any]):
        self.app_id = config.get('app_id')
        self.access_token = config.get('access_token')
        self._lock = Lock()
        self.last_api_call = 0
        self.api_call_interval = 0.1  # 100ms between API calls (10 calls per second max)
        self.api_call_count = 0
        self.api_window_start = 0
        self.max_api_calls_per_minute = 180  # Use 180 out of 200 to leave buffer
        self.initialization_mode = True  # Flag to distinguish initialization from monitoring
        
        if not self.app_id or not self.access_token:
            raise ValueError("Fyers app_id or access_token is missing in config.")
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Fyers client with error handling."""
        try:
            self.client = fyersModel.FyersModel(
                client_id=self.app_id,
                token=self.access_token,
                log_path=".",
                is_async=False
            )
            logger.info("Successfully initialized Fyers client")
        except Exception as e:
            logger.error(f"Failed to initialize Fyers client: {e}")
            raise ValueError(f"Could not initialize Fyers client. Error: {e}")
    
    def get_historical_ohlc(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """Enhanced method to get historical OHLC data with multiple fallback strategies."""
        with self._lock:
            strategies = [
                self._try_exact_date,
                self._try_date_range,
                self._try_different_resolution,
                self._try_quotes_fallback
            ]
            
            for i, strategy in enumerate(strategies, 1):
                if not self._check_api_rate_limit():
                    logger.warning(f"API rate limit reached, skipping strategy {i} for {symbol}")
                    continue
                    
                logger.info(f"Strategy {i} for {symbol}")
                result = strategy(symbol, target_date)
                if result:
                    logger.info(f"Strategy {i} successful for {symbol}")
                    return result
                time.sleep(0.5)
            
            logger.error(f"All strategies failed for {symbol}")
            return None
    
    def _try_exact_date(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """Try to get data for exact date."""
        try:
            data = {
                "symbol": symbol,
                "resolution": "D",
                "date_format": "1",
                "range_from": target_date.strftime('%Y-%m-%d'),
                "range_to": target_date.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            response = self.client.history(data=data)
            return self._parse_historical_response(response, target_date)
            
        except Exception as e:
            logger.debug(f"Exact date strategy failed: {e}")
            return None
    
    def _try_date_range(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """Try to get data from a date range."""
        try:
            start_date = target_date - timedelta(days=5)
            
            data = {
                "symbol": symbol,
                "resolution": "D",
                "date_format": "1",
                "range_from": start_date.strftime('%Y-%m-%d'),
                "range_to": target_date.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            response = self.client.history(data=data)
            return self._parse_historical_response(response, target_date, allow_closest=True)
            
        except Exception as e:
            logger.debug(f"Date range strategy failed: {e}")
            return None
    
    def _try_different_resolution(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """Try different resolution formats."""
        try:
            data = {
                "symbol": symbol,
                "resolution": "1D",
                "date_format": "1",
                "range_from": target_date.strftime('%Y-%m-%d'),
                "range_to": target_date.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            response = self.client.history(data=data)
            return self._parse_historical_response(response, target_date)
            
        except Exception as e:
            logger.debug(f"Different resolution strategy failed: {e}")
            return None
    
    def _check_api_rate_limit(self) -> bool:
        """Check if API rate limit allows another call with different limits for init vs monitoring."""
        current_time = time.time()
        
        # Reset API call counter every minute
        if current_time - self.api_window_start > 60:
            self.api_window_start = current_time
            self.api_call_count = 0
        
        # Use different limits for initialization vs monitoring
        if self.initialization_mode:
            # Aggressive during initialization to get all data quickly
            max_calls = self.max_api_calls_per_minute  # Use full 180 calls/min
            min_interval = 0.1  # 100ms during init (10 calls/sec)
        else:
            # Still generous during monitoring but with some buffer
            max_calls = 150  # 150 calls per minute during monitoring (75% of limit)
            min_interval = self.api_call_interval  # 100ms during monitoring
        
        # Check if we've exceeded the rate limit
        if self.api_call_count >= max_calls:
            logger.debug(f"API rate limit reached: {self.api_call_count}/{max_calls} calls in current minute")
            return False
        
        # Check minimum interval between calls
        time_since_last = current_time - self.last_api_call
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_api_call = time.time()
        self.api_call_count += 1
        return True
    
    def set_monitoring_mode(self):
        """Switch to monitoring mode with stricter rate limits."""
        self.initialization_mode = False
        # Reset counters when switching modes
        self.api_call_count = 0
        self.api_window_start = time.time()
        logger.info("🔄 Switched to monitoring mode with optimized API rate limits (150 calls/min)")
    
    def _try_quotes_fallback(self, symbol: str, target_date: date) -> Optional[OHLCData]:
        """Fallback to quotes data with estimation."""
        try:
            response = self.client.quotes({"symbols": symbol})
            
            if response.get('s') == 'ok' and response.get('d'):
                quote_data = response['d'][0]['v']
                prev_close = quote_data.get('prev_close_price')
                
                if prev_close:
                    estimated_ohlc = OHLCData(
                        open=prev_close,
                        high=prev_close * 1.01,
                        low=prev_close * 0.99,
                        close=prev_close,
                        date=target_date,
                        source="quotes_estimate"
                    )
                    logger.warning(f"Using estimated OHLC from quotes for {symbol}")
                    return estimated_ohlc
                    
        except Exception as e:
            logger.debug(f"Quotes fallback strategy failed: {e}")
            return None
    
    def _parse_historical_response(self, response: Dict[str, Any], target_date: date, 
                                 allow_closest: bool = False) -> Optional[OHLCData]:
        """Parse historical API response."""
        if response.get('s') != 'ok' or not response.get('candles'):
            return None
        
        candles = response['candles']
        if not candles:
            return None
        
        # Find the candle for target date or closest if allowed
        best_candle = None
        best_date = None
        
        for candle in candles:
            timestamp, o, h, l, c, volume = candle
            candle_date = datetime.fromtimestamp(timestamp).date()
            
            if candle_date == target_date:
                best_candle = candle
                best_date = candle_date
                break
            elif allow_closest and (not best_date or abs((target_date - candle_date).days) < abs((target_date - best_date).days)):
                best_candle = candle
                best_date = candle_date
        
        if best_candle:
            timestamp, o, h, l, c, volume = best_candle
            return OHLCData(
                open=o,
                high=h,
                low=l,
                close=c,
                date=best_date,
                volume=volume,
                source="historical"
            )
        
        return None
    
    def get_latest_candle(self, symbol: str, resolution: str = "30s") -> Optional[CandleData]:
        """Get the latest candle with seconds resolution for real-time detection."""
        try:
            if not self._check_api_rate_limit():
                logger.warning(f"API rate limit reached for {symbol}, skipping candle fetch")
                return None
                
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=30)  # Shorter window for seconds data
            
            data = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",
                "range_from": start_time.strftime('%Y-%m-%d'),
                "range_to": end_time.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            response = self.client.history(data=data)
            
            if response.get('s') == 'ok' and response.get('candles'):
                candles = response['candles']
                if candles:
                    latest_candle = candles[-1]
                    timestamp, o, h, l, c, volume = latest_candle
                    candle_datetime = datetime.fromtimestamp(timestamp)
                    
                    return CandleData(
                        timestamp=timestamp,
                        open=o,
                        high=h,
                        low=l,  
                        close=c,
                        volume=volume,
                        datetime=candle_datetime,
                        time_str=candle_datetime.strftime('%H:%M:%S')  # Include seconds
                    )
            else:
                # Fallback hierarchy: 30s -> 1m -> 5m
                return self._try_fallback_resolutions(symbol, start_time, end_time)
                    
        except Exception as e:
            logger.debug(f"Error fetching {resolution} candle for {symbol}: {e}")
            return self._try_fallback_resolutions(symbol, start_time, end_time)
    
    def _try_fallback_resolutions(self, symbol: str, start_time: datetime, end_time: datetime) -> Optional[CandleData]:
        """Try different resolutions in order of preference for real-time data."""
        fallback_resolutions = ["15s", "1", "3", "5"]  # 15s, 1m, 3m, 5m
        
        for resolution in fallback_resolutions:
            try:
                logger.debug(f"Trying fallback resolution {resolution} for {symbol}")
                
                # Adjust time window based on resolution
                if 's' in resolution:  # Seconds
                    time_window = timedelta(minutes=15)
                else:  # Minutes
                    time_window = timedelta(hours=2)
                
                start = end_time - time_window
                
                data = {
                    "symbol": symbol,
                    "resolution": resolution,
                    "date_format": "1",
                    "range_from": start.strftime('%Y-%m-%d'),
                    "range_to": end_time.strftime('%Y-%m-%d'),
                    "cont_flag": "1"
                }
                
                response = self.client.history(data=data)
                
                if response.get('s') == 'ok' and response.get('candles'):
                    candles = response['candles']
                    if candles:
                        latest_candle = candles[-1]
                        timestamp, o, h, l, c, volume = latest_candle
                        candle_datetime = datetime.fromtimestamp(timestamp)
                        
                        # Format time string based on resolution
                        if 's' in resolution:
                            time_format = '%H:%M:%S'
                        else:
                            time_format = '%H:%M'
                        
                        logger.info(f"✅ Using {resolution} resolution for {symbol}")
                        
                        return CandleData(
                            timestamp=timestamp,
                            open=o,
                            high=h,
                            low=l,  
                            close=c,
                            volume=volume,
                            datetime=candle_datetime,
                            time_str=candle_datetime.strftime(time_format)
                        )
                        
            except Exception as e:
                logger.debug(f"Fallback resolution {resolution} failed for {symbol}: {e}")
                continue
        
        logger.warning(f"All fallback resolutions failed for {symbol}")
        return None

# --- Token Management Integration ---

class BotRestartManager:
    """Manages seamless bot restart with new tokens"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.restart_requested = False
        self.new_token = None
        
    def request_restart(self, new_token: str):
        """Request bot restart with new token"""
        logger.info(f"🔄 Bot restart requested with new token")
        self.new_token = new_token
        self.restart_requested = True
        
        # Stop current monitoring gracefully
        self.bot.stop_monitoring()
        
        # Wait for monitoring to stop
        time.sleep(3)
        
        # Update config with new token
        self.bot.config['fyers']['access_token'] = new_token
        
        # Reinitialize services
        self.bot.fyers_service = FyersService(self.bot.config['fyers'])
        
        # Send restart notification
        self.bot.telegram_service.send_alert(
            f"🔄 **Bot Restarted at {datetime.now().strftime('%H:%M:%S')}**\n"
            f"✅ New token applied successfully\n"
            f"🚀 Resuming monitoring with fresh authentication"
        )
        
        # Restart monitoring
        self.bot.start_monitoring()
        
        logger.info("✅ Bot restart completed successfully")
        self.restart_requested = False

# --- Main Application Class ---

class CPRAlertBot:
    """Main application class orchestrating the CPR alert system with enhanced cooldown management."""
    
    def __init__(self):
        self.config = ConfigManager.load_config()
        self.restart_manager = BotRestartManager(self)
        self.token_manager = None
        
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
        print(f"  Tolerance: {alert_settings.get('tolerance_percent', 'DEFAULT')}%")
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
        print(f"  Crossing Tolerance: {spam.get('crossing_tolerance_percent', 'DEFAULT')}%")
        
        print("="*60)
        print("✅ Configuration loaded successfully!")
        print("="*60 + "\n")
        
        self.db_service = DatabaseService()
        self.fyers_service = FyersService(self.config['fyers'])
        self.telegram_service = TelegramService(self.config['telegram'])
        self.chart_generator = ChartGenerator()
        # Initialize touch detector with less sensitive tolerance
        default_tolerance = 0.25  # Increased from 0.1% to 0.25% to reduce false positives
        configured_tolerance = self.config.get('alert_settings', {}).get('tolerance_percent', default_tolerance)
        
        # Ensure minimum tolerance to prevent spam
        final_tolerance = max(configured_tolerance, 0.15)  # Minimum 0.15%
        
        self.touch_detector = LevelTouchDetector(tolerance_percent=final_tolerance)
        
        if final_tolerance != configured_tolerance:
            logger.info(f"📊 Touch tolerance adjusted from {configured_tolerance}% to {final_tolerance}% (spam prevention)")
        else:
            logger.info(f"📊 Touch tolerance set to {final_tolerance}%")
        
        # Initialize cooldown manager with configurable cooldown period
        default_cooldown = 30  # Increased default from 15 to 30 minutes
        cooldown_minutes = self.config.get('alert_settings', {}).get('cooldown_minutes', default_cooldown)
        self.cooldown_manager = AlertCooldownManager(cooldown_minutes)
        
        # Initialize data freshness settings with spam prevention
        self.preferred_resolution = self.config.get('alert_settings', {}).get('preferred_resolution', '1')  # Changed from 30s to 1m
        self.check_interval = self.config.get('alert_settings', {}).get('check_interval_seconds', 30)  # Increased from 15s to 30s
        
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
        schedule.every().day.at("08:00").do(self._calculate_daily_levels)
        
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
                    min_volume = self.config.get('alert_settings', {}).get('min_volume_threshold', 0)
                    
                    # Minimal delay between symbols (we have 10 calls/sec limit)
                    time.sleep(0.01)  # 10ms delay
                
                    for level_type in key_levels:
                        level_value = asset_data.levels.get_level(level_type)
                        
                        # Use enhanced touch detection with directional validation (volume filter removed)
                        if self.touch_detector.check_level_touch_with_filters(
                            candle, level_value, 
                        recent_candles=asset_data.recent_candles[:-1] if len(asset_data.recent_candles) > 1 else [],
                        min_volume=0,  # Volume filtering disabled
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
                                    self.fyers_service, symbol, candle_count=50
                                )
                                
                                if chart_candles:
                                    chart_buffer = self.chart_generator.create_cpr_chart(
                                        symbol,
                                        asset_data.name,
                                        chart_candles,
                                        asset_data.levels,
                                        first_level_type,
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

# --- Enhanced Configuration Template ---

def create_sample_config():
    """Create a sample configuration file."""
    sample_config = {
        "fyers": {
            "app_id": "YOUR_APP_ID",
            "access_token": "YOUR_ACCESS_TOKEN"
        },
        "telegram": {
            "bot_token": "YOUR_BOT_TOKEN",
            "chat_id": "YOUR_CHAT_ID"
        },
        "assets": [
            {
                "symbol": "NSE:NIFTY50-INDEX",
                "name": "NIFTY 50"
            },
            {
                "symbol": "NSE:BANKNIFTY-INDEX", 
                "name": "BANK NIFTY"
            },
            {
                "symbol": "NSE:RELIANCE-EQ",
                "name": "RELIANCE"
            }
        ],
        "alert_settings": {
            "market_hours": {
                "start": "09:15",
                "end": "15:30",
                "pre_market_start": "09:00",
                "post_market_end": "15:45"
            },
            "check_interval_seconds": 20,
            "tolerance_percent": 0.05,
            "cooldown_minutes": 30,
            "preferred_resolution": "1",
            "focus_on_key_levels": true,
            "min_volume_threshold": 5000,
            "enable_spam_prevention": true,
            "strict_level_crossing": true
        },
        "advanced_settings": {
            "enable_volume_analysis": true,
            "min_volume_threshold": 5000,
            "enable_strength_filtering": true,
            "min_touch_strength": 0.4,
            "enable_trend_analysis": false,
            "enable_volatility_filter": true
        },
        "spam_prevention": {
            "min_candle_range_ratio": 0.3,
            "max_alerts_per_hour": 6,
            "require_volume_confirmation": true,
            "strict_crossing_validation": true,
            "crossing_tolerance_percent": 0.02
        }
    }
    
    config_path = Path('config_sample.json')
    with open(config_path, 'w') as f:
        json.dump(sample_config, f, indent=4)
    
    print(f"Sample configuration created at: {config_path}")
    return sample_config

# --- CLI Interface ---

class CLIInterface:
    """Command line interface for the CPR bot."""
    
    def __init__(self, bot: CPRAlertBot):
        self.bot = bot
    
    def run_interactive(self):
        """Run interactive CLI."""
        print("🎯 CPR Alert Bot - Interactive Mode")
        print("Commands: status, start, stop, config, cooldown, reset, quit")
        
        while True:
            try:
                command = input("\nEnter command: ").strip().lower()
                
                if command == "quit" or command == "exit":
                    print("Goodbye!")
                    break
                elif command == "status":
                    print(self.bot.get_status_report())
                elif command == "start":
                    if not self.bot.asset_data:
                        print("Initializing levels...")
                        if self.bot.initialize_daily_levels():
                            print("Starting monitoring...")
                            Thread(target=self.bot.start_monitoring, daemon=True).start()
                        else:
                            print("Failed to initialize levels")
                    else:
                        print("Bot is already running")
                elif command == "stop":
                    self.bot.stop_monitoring()
                    print("Monitoring stopped")
                elif command == "config":
                    create_sample_config()
                elif command == "cooldown":
                    symbol = input("Enter symbol (e.g., 'NSE:NIFTY50-INDEX'): ").strip()
                    if symbol in self.bot.asset_data:
                        asset_data = self.bot.asset_data[symbol]
                        cooldown_status = self.bot.cooldown_manager.get_cooldown_status(asset_data, datetime.now())
                        
                        if cooldown_status["in_cooldown"]:
                            minutes = int(cooldown_status["time_remaining"].total_seconds() / 60)
                            print(f"🔇 {symbol} in cooldown: {minutes} minutes remaining")
                            print(f"Initial level: {cooldown_status['initial_level']}")
                            if cooldown_status["levels_touched_during_cooldown"]:
                                print(f"Also touched: {', '.join(cooldown_status['levels_touched_during_cooldown'])}")
                        else:
                            print(f"✅ {symbol} ready for alerts")
                    else:
                        print("Symbol not found")
                elif command == "reset":
                    confirm = input("Reset all stock cooldowns? (yes/no): ").strip().lower()
                    if confirm == "yes":
                        for asset_data in self.bot.asset_data.values():
                            self.bot.cooldown_manager.reset_daily_cooldowns(asset_data)
                        print("🔄 All stock cooldowns reset")
                elif command == "help":
                    print("Available commands:")
                    print("  status   - Show current bot status")
                    print("  start    - Start monitoring")
                    print("  stop     - Stop monitoring")
                    print("  config   - Create sample config")
                    print("  cooldown - Check cooldown for specific stock")
                    print("  reset    - Reset all stock cooldowns")
                    print("  quit     - Exit program")
                else:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

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
        logger.error(f"Error in interactive mode: {e}")

def test_connection():
    """Test Fyers and Telegram connections."""
    try:
        config = ConfigManager.load_config()
        
        print("Testing Fyers connection...")
        fyers_service = FyersService(config['fyers'])
        test_symbol = "NSE:NIFTY50-INDEX"
        candle = fyers_service.get_latest_candle(test_symbol)
        if candle:
            print(f"✅ Fyers connection successful. Latest {test_symbol}: {candle.close}")
        else:
            print("❌ Fyers connection failed")
        
        print("\nTesting Telegram connection...")
        telegram_service = TelegramService(config['telegram'])
        success = telegram_service.send_alert("🧪 CPR Bot connection test")
        if success:
            print("✅ Telegram connection successful")
        else:
            print("❌ Telegram connection failed")
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "interactive":
            interactive_main()
        elif sys.argv[1] == "test":
            test_connection()
        elif sys.argv[1] == "config":
            create_sample_config()
        else:
            print("Usage: python cpr_bot.py [interactive|test|config]")
    else:
        main()