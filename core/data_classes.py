from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, date

class MarketStatus(Enum):
    PRE_MARKET = "Pre-Market"
    OPEN = "Open"
    CLOSED = "Closed"
    HOLIDAY = "Holiday"
    UNKNOWN = "Unknown"

class LevelType(Enum):
    CPR_TOP = "CPR Top"
    CPR_PIVOT = "CPR Pivot"
    CPR_BOTTOM = "CPR Bottom"
    RESISTANCE = "Resistance"
    SUPPORT = "Support"
    DAY_HIGH = "Day High"
    DAY_LOW = "Day Low"

@dataclass
class OHLCData:
    high: float
    low: float
    close: float
    open: float = 0.0

@dataclass
class CPRLevels:
    pivot: float
    bc: float
    tc: float
    r1: float
    s1: float
    r2: float
    s2: float
    r3: float
    s3: float
    r4: float
    s4: float

@dataclass
class CandleData:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float

@dataclass
class StockCooldown:
    alert_triggered: bool = False
    last_alert_time: Optional[datetime] = None

@dataclass
class AssetData:
    symbol: str
    name: str
    previous_day_ohlc: Optional[OHLCData] = None
    cpr_levels: Optional[CPRLevels] = None
    day_high: float = 0.0
    day_low: float = float('inf')
    cooldown_status: StockCooldown = field(default_factory=StockCooldown)