import sqlite3
import logging
from core.data_classes import CPRLevels, OHLCData

class DatabaseService:
    def __init__(self, db_name: str = "cpr_alerts.db"):
        self.db_name = db_name
        self.logger = logging.getLogger(__name__)
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_name)

    def _create_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_levels (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    pivot REAL, tc REAL, bc REAL, r1 REAL, s1 REAL,
                    prev_open REAL, prev_high REAL, prev_low REAL, prev_close REAL,
                    UNIQUE(symbol, date)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    timestamp INTEGER,
                    level_type TEXT,
                    level_value REAL,
                    triggered_price REAL
                )
            ''')
            conn.commit()

    def save_daily_levels(self, symbol: str, date_str: str, levels: CPRLevels, ohlc: OHLCData):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO daily_levels 
                (symbol, date, pivot, tc, bc, r1, s1, prev_open, prev_high, prev_low, prev_close)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, date_str, levels.pivot, levels.tc, levels.bc, levels.r1, levels.s1,
                  ohlc.open, ohlc.high, ohlc.low, ohlc.close))
            conn.commit()

    def save_alert(self, symbol: str, level_type: str, level_value: float, price: float, timestamp: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts (symbol, timestamp, level_type, level_value, triggered_price)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol, timestamp, level_type, level_value, price))
            conn.commit()