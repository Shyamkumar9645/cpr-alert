from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

@dataclass
class OHLCData:
    open: float
    high: float
    low: float
    close: float

@dataclass
class CPRLevels:
    pivot: float
    bc: float
    tc: float
    r1: float
    s1: float

@dataclass
class CandleData:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int

class LevelType(Enum):
    R1 = "Resistance 1"
    PIVOT = "Pivot"
    S1 = "Support 1"

class MarketStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"

@dataclass
class AssetData:
    name: str
    symbol: str
    levels: CPRLevels
    source_data: OHLCData
    last_candle_timestamp: Optional[int] = None