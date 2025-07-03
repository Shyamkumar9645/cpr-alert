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
    recent_candles: List[CandleData] = field(default_factory=list)
    alerted_levels_timestamps: Dict[str, int] = field(default_factory=dict)

class ConfigManager:
    """Manages configuration from environment variables and defaults."""
    
    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {
            "fyers": {
                "app_id": os.getenv("FYERS_APP_ID"),
                "secret_key": os.getenv("FYERS_SECRET_KEY"),
                "redirect_uri": os.getenv("FYERS_REDIRECT_URI", "https://trade.fyers.in/api-login/redirect-uri/index.html"),
                "access_token": os.getenv("FYERS_ACCESS_TOKEN")
            },
            "telegram": {
                "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
                "chat_id": os.getenv("TELEGRAM_CHAT_ID")
            },
            "assets": [
                {
                    "symbol": "NSE:NIFTY50-INDEX",
                    "name": "NIFTY 50",
                    "type": "index",
                    "category": "INDEX",
                    "intraday_rating": "★★★★★",
                    "volatility": "MEDIUM",
                    "liquidity": "ULTRA_HIGH"
                },
                {
                    "symbol": "NSE:NIFTYBANK-INDEX",
                    "name": "BANK NIFTY",
                    "type": "index",
                    "category": "INDEX",
                    "intraday_rating": "★★★★★",
                    "volatility": "HIGH",
                    "liquidity": "ULTRA_HIGH"
                },
                {
                    "symbol": "NSE:FINNIFTY-INDEX",
                    "name": "NIFTY FINANCIAL",
                    "type": "index",
                    "category": "INDEX",
                    "intraday_rating": "★★★★★",
                    "volatility": "HIGH",
                    "liquidity": "HIGH"
                },
                {
                    "symbol": "NSE:RELIANCE-EQ",
                    "name": "RELIANCE",
                    "type": "stock",
                    "category": "ENERGY",
                    "intraday_rating": "★★★★★",
                    "volatility": "MEDIUM",
                    "liquidity": "ULTRA_HIGH",
                    "avg_daily_move": "2-4%"
                },
                {
                    "symbol": "NSE:HDFCBANK-EQ",
                    "name": "HDFC BANK",
                    "type": "stock",
                    "category": "BANKING",
                    "intraday_rating": "★★★★★",
                    "volatility": "MEDIUM",
                    "liquidity": "ULTRA_HIGH",
                    "avg_daily_move": "1-3%"
                },
                {
                    "symbol": "NSE:ICICIBANK-EQ",
                    "name": "ICICI BANK",
                    "type": "stock",
                    "category": "BANKING",
                    "intraday_rating": "★★★★★",
                    "volatility": "MEDIUM",
                    "liquidity": "ULTRA_HIGH",
                    "avg_daily_move": "2-4%"
                },
                {
                    "symbol": "NSE:AXISBANK-EQ",
                    "name": "AXIS BANK",
                    "type": "stock",
                    "category": "BANKING",
                    "intraday_rating": "★★★★★",
                    "volatility": "HIGH",
                    "liquidity": "HIGH",
                    "avg_daily_move": "3-6%"
                },
                {
                    "symbol": "NSE:SBIN-EQ",
                    "name": "STATE BANK",
                    "type": "stock",
                    "category": "BANKING",
                    "intraday_rating": "★★★★★",
                    "volatility": "HIGH",
                    "liquidity": "HIGH",
                    "avg_daily_move": "3-7%"
                },
                {
                    "symbol": "NSE:TATAMOTORS-EQ",
                    "name": "TATA MOTORS",
                    "type": "stock",
                    "category": "AUTO",
                    "intraday_rating": "★★★★★",
                    "volatility": "VERY_HIGH",
                    "liquidity": "HIGH",
                    "avg_daily_move": "4-9%"
                },
                {
                    "symbol": "NSE:BAJFINANCE-EQ",
                    "name": "BAJAJ FINANCE",
                    "type": "stock",
                    "category": "FINANCE",
                    "intraday_rating": "★★★★★",
                    "volatility": "VERY_HIGH",
                    "liquidity": "HIGH",
                    "avg_daily_move": "4-8%"
                },
                {
                    "symbol": "NSE:JSWSTEEL-EQ",
                    "name": "JSW STEEL",
                    "type": "stock",
                    "category": "METALS",
                    "intraday_rating": "★★★★★",
                    "volatility": "VERY_HIGH",
                    "liquidity": "HIGH",
                    "avg_daily_move": "4-9%"
                },
                {
                    "symbol": "NSE:TATASTEEL-EQ",
                    "name": "TATA STEEL",
                    "type": "stock",
                    "category": "METALS",
                    "intraday_rating": "★★★★★",
                    "volatility": "VERY_HIGH",
                    "liquidity": "HIGH",
                    "avg_daily_move": "4-8%"
                },
                {
                    "symbol": "NSE:ADANIENT-EQ",
                    "name": "ADANI ENT",
                    "type": "stock",
                    "category": "CONGLOMERATE",
                    "intraday_rating": "★★★★★",
                    "volatility": "EXTREME",
                    "liquidity": "HIGH",
                    "avg_daily_move": "5-12%"
                },
                {
                    "symbol": "NSE:INDUSINDBK-EQ",
                    "name": "INDUSIND BANK",
                    "type": "stock",
                    "category": "BANKING",
                    "intraday_rating": "★★★★★",
                    "volatility": "VERY_HIGH",
                    "liquidity": "HIGH",
                    "avg_daily_move": "4-8%"
                }
            ],
            "alert_settings": {
                "check_interval_seconds": 20,
                "tolerance_percent": 0.05,
                "cooldown_minutes": 30,
                "preferred_resolution": "1",
                "focus_on_key_levels": True,
                "min_volume_threshold": 0,
                "enable_spam_prevention": True,
                "strict_level_crossing": True,
                "market_hours": {
                    "start": "09:15",
                    "end": "15:30",
                    "pre_market_start": "09:00",
                    "post_market_end": "15:45"
                }
            },
            "api_optimization": {
                "max_calls_per_minute_init": 180,
                "max_calls_per_minute_monitoring": 150,
                "call_interval_milliseconds": 100,
                "batch_size": 25,
                "batch_delay_milliseconds": 500
            }
        }
        
        # Validate required environment variables
        required_vars = [
            "FYERS_APP_ID", "FYERS_SECRET_KEY", "FYERS_ACCESS_TOKEN",
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        logger.info("Configuration loaded from environment variables")
        return config

class CPRCalculator:
    """Calculates CPR levels from OHLC data."""
    
    @staticmethod
    def calculate_cpr_levels(ohlc_data: OHLCData) -> CPRLevels:
        """Calculate CPR levels from previous day's OHLC data."""
        high = ohlc_data.high
        low = ohlc_data.low
        close = ohlc_data.close
        
        # Calculate CPR levels
        pivot = (high + low + close) / 3
        bc = (high + low) / 2  # Bottom Central
        tc = (pivot - bc) + pivot  # Top Central
        r1 = (2 * pivot) - low  # Resistance 1
        s1 = (2 * pivot) - high  # Support 1
        
        return CPRLevels(
            pivot=round(pivot, 2),
            tc=round(tc, 2),
            bc=round(bc, 2),
            r1=round(r1, 2),
            s1=round(s1, 2)
        )

class LevelTouchDetector:
    """Detects level touches with configurable tolerance and validation."""
    
    def __init__(self, tolerance_percent: float = 0.25):
        self.tolerance_percent = tolerance_percent
        logger.info(f"LevelTouchDetector initialized with {tolerance_percent}% tolerance")
        
        if tolerance_percent < 0.15:
            logger.warning(f"⚠️ Tolerance {tolerance_percent}% is very sensitive and may cause spam alerts")
    
    def check_level_touch(self, candle: CandleData, level_value: float) -> bool:
        """Check if a candle actually touched/crossed a specific level with minimal tolerance."""
        if not candle:
            return False
        
        actual_tolerance_percent = min(self.tolerance_percent, 0.05)
        tolerance = level_value * (actual_tolerance_percent / 100)
        
        level_touched = (candle.low - tolerance) <= level_value <= (candle.high + tolerance)
        
        if level_touched:
            candle_range = candle.high - candle.low
            touch_significance = min(abs(candle.low - level_value), abs(candle.high - level_value))
            
            return touch_significance <= tolerance and candle_range > tolerance * 2
        
        return False
    
    def check_level_touch_with_filters(self, candle: CandleData, level_value: float, 
                                     recent_candles: List[CandleData] = None, 
                                     min_volume: int = 0, 
                                     level_type: str = None) -> bool:
        """Enhanced level touch detection with spam filters and directional validation."""
        if not self.check_level_touch(candle, level_value):
            return False
        
        # Volume filter - REMOVED (no longer required)
        # Volatility filter - REMOVED (no longer required)
        
        # Strict level crossing validation
        if level_type and recent_candles and len(recent_candles) > 0:
            prev_candle = recent_candles[-1]
            
            if not self.check_actual_level_cross(candle, prev_candle, level_value, level_type):
                return False
        
        return True
    
    def check_actual_level_cross(self, current_candle: CandleData, previous_candle: CandleData, 
                                level_value: float, level_type: str) -> bool:
        """Check if price actually crossed the level, not just came close."""
        if not previous_candle:
            return False
        
        tolerance = level_value * 0.02 / 100
        
        if level_type == 'S1':
            prev_above = previous_candle.low > (level_value + tolerance)
            curr_touches = (current_candle.low - tolerance) <= level_value <= (current_candle.high + tolerance)
            return prev_above and curr_touches
            
        elif level_type == 'R1':
            prev_below = previous_candle.high < (level_value - tolerance)
            curr_touches = (current_candle.low - tolerance) <= level_value <= (current_candle.high + tolerance)
            return prev_below and curr_touches
            
        elif level_type == 'PIVOT':
            prev_above = previous_candle.close > (level_value + tolerance)
            prev_below = previous_candle.close < (level_value - tolerance)
            curr_touches = (current_candle.low - tolerance) <= level_value <= (current_candle.high + tolerance)
            return (prev_above or prev_below) and curr_touches
        
        return False

class AlertCooldownManager:
    """Manages stock-wide cooldown periods for level touch alerts."""
    
    def __init__(self, cooldown_minutes: int = 30):
        self.cooldown_minutes = max(cooldown_minutes, 20)
        self.cooldown_duration = timedelta(minutes=self.cooldown_minutes)
        
        if self.cooldown_minutes != cooldown_minutes:
            logger.info(f"AlertCooldownManager cooldown adjusted from {cooldown_minutes} to {self.cooldown_minutes} minutes (spam prevention)")
        else:
            logger.info(f"AlertCooldownManager initialized with {self.cooldown_minutes} minute STOCK-WIDE cooldown")
        
        if self.cooldown_minutes < 25:
            logger.warning(f"⚠️ Cooldown {self.cooldown_minutes}min may still allow spam alerts. Recommended: 30min+")
    
    def can_send_alert(self, asset_data: AssetData, level_type: LevelType, current_time: datetime) -> bool:
        """Check if we can send an alert for this stock (any level)."""
        if asset_data.stock_cooldown is None:
            return True
        
        time_since_last_alert = current_time - asset_data.stock_cooldown.last_alert_time
        return time_since_last_alert >= self.cooldown_duration
    
    def record_alert_sent(self, asset_data: AssetData, level_type: LevelType, current_time: datetime):
        """Record that an alert was sent for this stock."""
        if asset_data.stock_cooldown is None:
            asset_data.stock_cooldown = StockCooldown(
                last_alert_time=current_time,
                initial_level_touched=level_type
            )
        else:
            asset_data.stock_cooldown.last_alert_time = current_time
            asset_data.stock_cooldown.total_touches += 1
    
    def record_touch_during_cooldown(self, asset_data: AssetData, level_type: LevelType):
        """Record a level touch that occurred during cooldown period."""
        if asset_data.stock_cooldown:
            level_name = level_type.value
            if level_name not in asset_data.stock_cooldown.levels_touched_during_cooldown:
                asset_data.stock_cooldown.levels_touched_during_cooldown[level_name] = 0
            asset_data.stock_cooldown.levels_touched_during_cooldown[level_name] += 1
    
    def get_cooldown_status(self, asset_data: AssetData, current_time: datetime) -> Dict[str, Any]:
        """Get cooldown status for a stock."""
        if asset_data.stock_cooldown is None:
            return {"in_cooldown": False, "time_remaining": timedelta(0)}
        
        time_since_last = current_time - asset_data.stock_cooldown.last_alert_time
        
        if time_since_last >= self.cooldown_duration:
            return {"in_cooldown": False, "time_remaining": timedelta(0)}
        
        return {
            "in_cooldown": True,
            "time_remaining": self.cooldown_duration - time_since_last,
            "initial_level": asset_data.stock_cooldown.initial_level_touched.value,
            "total_touches": asset_data.stock_cooldown.total_touches,
            "levels_touched_during_cooldown": list(asset_data.stock_cooldown.levels_touched_during_cooldown.keys())
        }
    
    def get_total_touches(self, asset_data: AssetData) -> int:
        """Get total number of level touches for this stock."""
        return asset_data.stock_cooldown.total_touches if asset_data.stock_cooldown else 0
    
    def get_pending_touches_summary(self, asset_data: AssetData) -> Tuple[int, List[str]]:
        """Get summary of pending touches during cooldown."""
        if not asset_data.stock_cooldown:
            return 0, []
        
        pending_touches = sum(asset_data.stock_cooldown.levels_touched_during_cooldown.values())
        pending_levels = list(asset_data.stock_cooldown.levels_touched_during_cooldown.keys())
        
        return pending_touches, pending_levels
    
    def get_time_until_next_alert(self, asset_data: AssetData, current_time: datetime) -> timedelta:
        """Get time remaining until next alert can be sent."""
        if asset_data.stock_cooldown is None:
            return timedelta(0)
        
        time_since_last = current_time - asset_data.stock_cooldown.last_alert_time
        
        if time_since_last >= self.cooldown_duration:
            return timedelta(0)
        
        return self.cooldown_duration - time_since_last
    
    def reset_daily_cooldowns(self, asset_data: AssetData):
        """Reset cooldown for a stock (useful for daily resets)."""
        asset_data.stock_cooldown = None
        asset_data.alerted_levels.clear()
        asset_data.alerted_levels_timestamps.clear()

class DatabaseService:
    """Handles database operations for storing alerts and daily levels."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    level_type TEXT NOT NULL,
                    level_value REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_levels (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    pivot REAL NOT NULL,
                    tc REAL NOT NULL,
                    bc REAL NOT NULL,
                    r1 REAL NOT NULL,
                    s1 REAL NOT NULL,
                    source_ohlc TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, date)
                )
            ''')
    
    def save_alert(self, symbol: str, level_type: str, level_value: float, price: float, timestamp: int):
        """Save an alert to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO alerts (symbol, level_type, level_value, price, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (symbol, level_type, level_value, price, timestamp))
        except Exception as e:
            logger.error(f"Error saving alert: {e}")
    
    def save_daily_levels(self, symbol: str, levels: CPRLevels, source_ohlc: OHLCData):
        """Save daily CPR levels to database."""
        try:
            date_str = source_ohlc.date.strftime('%Y-%m-%d')
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
        self.min_interval = 5
        self.burst_count = 0
        self.burst_window_start = 0
        self.max_burst_messages = 3
        self.burst_window_seconds = 60
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("Telegram bot_token or chat_id is missing in config.")

    def send_alert(self, message: str, max_retries: int = 3) -> bool:
        """Sends a message with retry logic and enhanced rate limiting."""
        current_time = time.time()
        
        if current_time - self.burst_window_start > self.burst_window_seconds:
            self.burst_window_start = current_time
            self.burst_count = 0
        
        if self.burst_count >= self.max_burst_messages:
            logger.warning(f"Telegram rate limit: {self.burst_count} messages sent in {self.burst_window_seconds}s window")
            return False
        
        time_since_last = current_time - self.last_message_time
        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)
        
        payload = {
            'chat_id': self.chat_id,
            'text': message[:4096],
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
                    time.sleep(2 ** attempt)
        
        logger.error(f"Failed to send alert after {max_retries} attempts")
        return False

    def send_formatted_alert(self, asset_name: str, level_type: LevelType, 
                           level_value: float, candle: CandleData, 
                           total_touches: int = 1, pending_levels: List[str] = None) -> bool:
        """Sends a formatted level touch alert with real-time detection info."""
        emoji_map = {
            LevelType.S1: '📉',
            LevelType.R1: '🚨',
            LevelType.PIVOT: '⚖️',
            LevelType.BC: '🔵',
            LevelType.TC: '🔴'
        }
        
        emoji = emoji_map.get(level_type, '🎯')
        
        detection_time = datetime.now()
        
        message = f"{emoji} *{level_type.value} Touch Alert*"
        
        if total_touches > 1:
            message += f" *(Touch #{total_touches})*"
        
        if pending_levels:
            message += f" + {', '.join(pending_levels)}"
        
        message += f"\n\n📊 *{asset_name}*"
        message += f"\n💰 Level: `{level_value:.2f}`"
        message += f"\n📈 Price: `{candle.close:.2f}`"
        message += f"\n🕒 Detection: `{detection_time.strftime('%H:%M:%S')}`"
        message += f"\n📅 Candle: `{candle.time_str}`"
        
        return self.send_alert(message)

class FyersService:
    """Enhanced Fyers API service with improved rate limiting and error handling."""
    
    def __init__(self, config: Dict[str, Any], telegram_service=None):
        self.client = fyersModel.FyersModel(
            token=config.get('access_token'),
            log_path=".",
            is_async=False
        )
        
        self.last_call_time = 0
        self.call_count = 0
        self.call_window_start = time.time()
        self.telegram_service = telegram_service
        self.max_calls_per_minute = 150
        self.call_interval = 0.1
        
        if not config.get('access_token'):
            raise ValueError("Fyers access_token is missing in config.")
        
        logger.info(f"FyersService initialized with {self.max_calls_per_minute} calls/minute limit")
    
    def _check_api_rate_limit(self) -> bool:
        """Check if we can make an API call without hitting rate limits."""
        current_time = time.time()
        
        if current_time - self.call_window_start >= 60:
            self.call_window_start = current_time
            self.call_count = 0
        
        if self.call_count >= self.max_calls_per_minute:
            logger.warning(f"API rate limit reached: {self.call_count} calls in current minute")
            return False
        
        time_since_last = current_time - self.last_call_time
        if time_since_last < self.call_interval:
            time.sleep(self.call_interval - time_since_last)
        
        self.last_call_time = time.time()
        self.call_count += 1
        return True
    
    def get_historical_data(self, symbol: str, target_date: date, 
                          allow_closest: bool = False) -> Optional[OHLCData]:
        """Get historical OHLC data for a specific date."""
        try:
            if not self._check_api_rate_limit():
                logger.warning(f"API rate limit reached for {symbol}, skipping historical data fetch")
                return None
                
            end_date = target_date + timedelta(days=1)
            
            data = {
                "symbol": symbol,
                "resolution": "D",
                "date_format": "1",
                "range_from": target_date.strftime('%Y-%m-%d'),
                "range_to": end_date.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            response = self.client.history(data=data)
            return self._parse_historical_response(response, target_date, allow_closest)
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    def _parse_historical_response(self, response: Dict[str, Any], target_date: date, 
                                 allow_closest: bool = False) -> Optional[OHLCData]:
        """Parse historical API response."""
        if response.get('s') != 'ok' or not response.get('candles'):
            return None
        
        candles = response['candles']
        if not candles:
            return None
        
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
            start_time = end_time - timedelta(minutes=30)
            
            data = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",
                "range_from": start_time.strftime('%Y-%m-%d'),
                "range_to": end_time.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            logger.info(f"Making API call for {symbol} latest candle")
            # Send telegram notification for API call
            if self.telegram_service:
                self.telegram_service.send_alert(f"📡 API Call: {symbol} - {datetime.now().strftime('%H:%M:%S')}")
            response = self.client.history(data=data)
            logger.info(f"API response for {symbol}: {response.get('s', 'unknown')}")
            
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
                        time_str=candle_datetime.strftime('%H:%M:%S')
                    )
            else:
                return self._try_fallback_resolutions(symbol, start_time, end_time)
                    
        except Exception as e:
            logger.debug(f"Error fetching {resolution} candle for {symbol}: {e}")
            return self._try_fallback_resolutions(symbol, start_time, end_time)
    
    def _try_fallback_resolutions(self, symbol: str, start_time: datetime, end_time: datetime) -> Optional[CandleData]:
        """Try different resolutions in order of preference for real-time data."""
        fallback_resolutions = ["15s", "1", "3", "5"]
        
        for resolution in fallback_resolutions:
            try:
                logger.debug(f"Trying fallback resolution {resolution} for {symbol}")
                
                if 's' in resolution:
                    time_window = timedelta(minutes=15)
                else:
                    time_window = timedelta(hours=2)
                
                adjusted_start = end_time - time_window
                
                data = {
                    "symbol": symbol,
                    "resolution": resolution,
                    "date_format": "1",
                    "range_from": adjusted_start.strftime('%Y-%m-%d'),
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
                        
                        logger.debug(f"Successfully got {resolution} candle for {symbol}")
                        return CandleData(
                            timestamp=timestamp,
                            open=o,
                            high=h,
                            low=l,
                            close=c,
                            volume=volume,
                            datetime=candle_datetime,
                            time_str=candle_datetime.strftime('%H:%M:%S')
                        )
                        
            except Exception as e:
                logger.debug(f"Fallback resolution {resolution} failed for {symbol}: {e}")
                continue
        
        return None

class MarketHoursChecker:
    """Checks if market is open based on Indian market hours."""
    
    def __init__(self, market_hours: Dict[str, str]):
        self.market_start = datetime.strptime(market_hours.get('start', '09:15'), '%H:%M').time()
        self.market_end = datetime.strptime(market_hours.get('end', '15:30'), '%H:%M').time()
        self.pre_market_start = datetime.strptime(market_hours.get('pre_market_start', '09:00'), '%H:%M').time()
        self.post_market_end = datetime.strptime(market_hours.get('post_market_end', '15:45'), '%H:%M').time()
    
    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        now = datetime.now()
        
        # Check if it's a weekend
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        current_time = now.time()
        
        # Check if within market hours
        return self.market_start <= current_time <= self.market_end
    
    def get_market_status(self) -> MarketStatus:
        """Get current market status."""
        now = datetime.now()
        
        if now.weekday() >= 5:
            return MarketStatus.CLOSED
        
        current_time = now.time()
        
        if self.market_start <= current_time <= self.market_end:
            return MarketStatus.OPEN
        elif self.pre_market_start <= current_time < self.market_start:
            return MarketStatus.PRE_MARKET
        elif self.market_end < current_time <= self.post_market_end:
            return MarketStatus.POST_MARKET
        else:
            return MarketStatus.CLOSED

class CPRAlertBot:
    """Main CPR Alert Bot with enhanced monitoring and alerting."""
    
    def __init__(self):
        self.config = ConfigManager.load_config()
        self.telegram_service = TelegramService(self.config['telegram'])
        self.fyers_service = FyersService(self.config['fyers'], self.telegram_service)
        self.db_service = DatabaseService(DB_FILE)
        
        alert_settings = self.config.get('alert_settings', {})
        self.check_interval = alert_settings.get('check_interval_seconds', 20)
        self.tolerance_percent = alert_settings.get('tolerance_percent', 0.05)
        self.cooldown_minutes = alert_settings.get('cooldown_minutes', 30)
        self.preferred_resolution = alert_settings.get('preferred_resolution', '1')
        
        self.touch_detector = LevelTouchDetector(self.tolerance_percent)
        self.cooldown_manager = AlertCooldownManager(self.cooldown_minutes)
        self.market_checker = MarketHoursChecker(alert_settings.get('market_hours', {}))
        
        self.asset_data: Dict[str, AssetData] = {}
        self.is_running = False
        self._lock = Lock()
        
        logger.info(f"CPR Alert Bot initialized with {len(self.config['assets'])} assets")
    
    def initialize_daily_levels(self) -> bool:
        """Initialize CPR levels for all configured assets."""
        logger.info("Initializing daily CPR levels...")
        
        # Get yesterday's date for CPR calculation
        yesterday = date.today() - timedelta(days=1)
        
        # If today is Monday, get Friday's data
        if yesterday.weekday() == 6:  # Sunday
            yesterday = yesterday - timedelta(days=2)  # Friday
        elif yesterday.weekday() == 5:  # Saturday
            yesterday = yesterday - timedelta(days=1)  # Friday
        
        successful_initializations = 0
        total_assets = len(self.config['assets'])
        
        for asset_config in self.config['assets']:
            symbol = asset_config['symbol']
            name = asset_config['name']
            
            try:
                # Get historical data for yesterday
                ohlc_data = self.fyers_service.get_historical_data(symbol, yesterday, allow_closest=True)
                
                if ohlc_data:
                    # Calculate CPR levels
                    cpr_levels = CPRCalculator.calculate_cpr_levels(ohlc_data)
                    
                    # Store asset data
                    self.asset_data[symbol] = AssetData(
                        name=name,
                        symbol=symbol,
                        levels=cpr_levels,
                        source_data=ohlc_data
                    )
                    
                    # Save to database
                    self.db_service.save_daily_levels(symbol, cpr_levels, ohlc_data)
                    
                    successful_initializations += 1
                    logger.info(f"✅ {name}: S1={cpr_levels.s1}, PIVOT={cpr_levels.pivot}, R1={cpr_levels.r1}")
                else:
                    logger.warning(f"❌ Failed to get historical data for {name} ({symbol})")
                    
            except Exception as e:
                logger.error(f"❌ Error initializing {name}: {e}")
        
        success_rate = (successful_initializations / total_assets) * 100
        logger.info(f"Initialization complete: {successful_initializations}/{total_assets} assets ({success_rate:.1f}%)")
        
        return successful_initializations > 0
    
    def start_monitoring(self):
        """Start the monitoring loop."""
        if self.is_running:
            logger.warning("Monitoring is already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting CPR level monitoring...")
        
        # Start scheduler in background thread
        schedule_thread = Thread(target=self._run_schedule, daemon=True)
        schedule_thread.start()
        
        # Schedule daily level reset
        schedule.every().day.at("06:00").do(self._reset_daily_data)
        
        # Main monitoring loop
        while self.is_running:
            try:
                market_status = self.market_checker.get_market_status()
                logger.info(f"Market status: {market_status}")
                
                if market_status == MarketStatus.OPEN:
                    self._check_level_touches()
                elif market_status == MarketStatus.CLOSED:
                    logger.info("Market is closed but continuing monitoring for testing...")
                    self._check_level_touches()  # Continue monitoring even when closed
                    if datetime.now().hour == 6 and datetime.now().minute < 5:
                        self._reset_daily_data()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)
        
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
        
        asset_items = list(self.asset_data.items())
        batch_size = 25
        
        for i in range(0, len(asset_items), batch_size):
            batch = asset_items[i:i + batch_size]
            
            for symbol, asset_data in batch:
                try:
                    candle = self.fyers_service.get_latest_candle(symbol, self.preferred_resolution)
                    
                    if not candle:
                        continue
                    
                    with self._lock:
                        if candle.timestamp <= asset_data.last_candle_timestamp:
                            continue
                        asset_data.last_candle_timestamp = candle.timestamp
                        
                        asset_data.recent_candles.append(candle)
                        if len(asset_data.recent_candles) > 5:
                            asset_data.recent_candles.pop(0)
                    
                    key_levels = [LevelType.S1, LevelType.R1, LevelType.PIVOT]
                    
                    levels_touched_now = []
                    
                    time.sleep(0.01)
                
                    for level_type in key_levels:
                        level_value = asset_data.levels.get_level(level_type)
                        
                        if self.touch_detector.check_level_touch_with_filters(
                            candle, level_value, 
                        recent_candles=asset_data.recent_candles[:-1] if len(asset_data.recent_candles) > 1 else [],
                        min_volume=0,
                        level_type=level_type.value
                    ):
                            levels_touched_now.append((level_type, level_value))
                    
                    if not levels_touched_now:
                        continue
                    
                    levels_touched_str = "_".join([lt.value for lt, _ in levels_touched_now])
                    alert_id = f"{symbol}_{levels_touched_str}_{candle.timestamp}"
                    
                    if alert_id in asset_data.alerted_levels:
                        continue
                    
                    priority_order = {LevelType.R1: 3, LevelType.S1: 2, LevelType.PIVOT: 1}
                    first_level_type, first_level_value = max(levels_touched_now, key=lambda x: priority_order.get(x[0], 0))
                    
                    real_current_time = datetime.now()
                    
                    if self.cooldown_manager.can_send_alert(asset_data, first_level_type, real_current_time):
                        pending_touches, pending_levels = self.cooldown_manager.get_pending_touches_summary(asset_data)
                        
                        self.cooldown_manager.record_alert_sent(asset_data, first_level_type, real_current_time)
                        
                        total_touches = self.cooldown_manager.get_total_touches(asset_data)
                        
                        success = self.telegram_service.send_formatted_alert(
                            asset_data.name,
                            first_level_type,
                            first_level_value,
                            candle,
                            total_touches,
                            pending_levels
                        )
                        
                        if success:
                            asset_data.alerted_levels.add(alert_id)
                            asset_data.alerted_levels_timestamps[alert_id] = candle.timestamp
                            
                            self._cleanup_old_alerts(asset_data, candle.timestamp)
                            
                            self.db_service.save_alert(
                                symbol, first_level_type.value, first_level_value,
                                candle.close, candle.timestamp
                            )
                            
                            levels_str = ", ".join([f"{lt.value}({lv:.2f})" for lt, lv in levels_touched_now])
                            detection_time_str = datetime.now().strftime('%H:%M:%S')
                            logger.info(f"🎯 {asset_data.name} touched {levels_str} at {detection_time_str} "
                                      f"(candle: {candle.time_str}) - Alert sent for {first_level_type.value} (Touch #{total_touches})")
                            
                            for level_type, _ in levels_touched_now[1:]:
                                self.cooldown_manager.record_touch_during_cooldown(asset_data, level_type)
                        else:
                            logger.error(f"Failed to send alert for {asset_data.name} {first_level_type.value}")
                    
                    else:
                        for level_type, level_value in levels_touched_now:
                            self.cooldown_manager.record_touch_during_cooldown(asset_data, level_type)
                        
                        time_until_next = self.cooldown_manager.get_time_until_next_alert(asset_data, real_current_time)
                        cooldown_status = self.cooldown_manager.get_cooldown_status(asset_data, real_current_time)
                        
                        levels_str = ", ".join([f"{lt.value}({lv:.2f})" for lt, lv in levels_touched_now])
                        minutes_remaining = int(time_until_next.total_seconds() / 60)
                        logger.info(f"🔇 {asset_data.name} touched {levels_str} - In cooldown ({minutes_remaining}m remaining)")
                        
                except Exception as e:
                    logger.error(f"Error checking {symbol}: {e}")
    
    def _cleanup_old_alerts(self, asset_data: AssetData, current_timestamp: int):
        """Clean up old alerts to prevent memory leaks."""
        cutoff_time = current_timestamp - 3600
        
        old_alerts = [alert_id for alert_id, timestamp in asset_data.alerted_levels_timestamps.items() 
                     if timestamp < cutoff_time]
        
        for alert_id in old_alerts:
            asset_data.alerted_levels.discard(alert_id)
            asset_data.alerted_levels_timestamps.pop(alert_id, None)
    
    def _reset_daily_data(self):
        """Reset daily data and reinitialize levels."""
        logger.info("🔄 Resetting daily data and reinitializing levels...")
        
        # Reset cooldowns
        for asset_data in self.asset_data.values():
            self.cooldown_manager.reset_daily_cooldowns(asset_data)
        
        # Reinitialize levels
        self.initialize_daily_levels()
        
        logger.info("✅ Daily reset complete")
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.is_running = False
        logger.info("🛑 Stopping monitoring...")
    
    def get_status_report(self) -> str:
        """Generate a status report."""
        if not self.asset_data:
            return "❌ No assets initialized"
        
        market_status = self.market_checker.get_market_status()
        
        report = f"📊 *CPR Alert Bot Status*\n"
        report += f"🕐 Market Status: {market_status.value.upper()}\n"
        report += f"📈 Assets Monitored: {len(self.asset_data)}\n"
        
        if market_status == MarketStatus.OPEN:
            report += f"⏱️ Check Interval: {self.check_interval}s\n"
            report += f"🎯 Tolerance: {self.tolerance_percent}%\n"
            report += f"⏰ Cooldown: {self.cooldown_minutes}min\n"
        
        return report

def main():
    """Main entry point for the CPR alert bot."""
    try:
        bot = CPRAlertBot()
        
        if not bot.initialize_daily_levels():
            logger.error("Failed to initialize daily levels. Exiting.")
            return
        
        try:
            bot.start_monitoring()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            bot.stop_monitoring()
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
