import sqlite3
import logging
from datetime import datetime

class DatabaseManager:
    """
    Manages the SQLite database for storing alert cooldown information.
    """
    def __init__(self, db_file='cpr_alerts.db'):
        """
        Initializes the database connection and creates the table if it doesn't exist.
        """
        self.db_file = db_file
        self.logger = logging.getLogger(__name__)
        self.conn = None
        try:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self._create_table()
        except sqlite3.Error as e:
            self.logger.exception(f"Database connection error: {e}")
            raise

    def _create_table(self):
        """
        Creates the 'alerts' table if it doesn't already exist.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    symbol TEXT PRIMARY KEY,
                    last_alert_time TEXT NOT NULL
                )
            ''')
            self.conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Error creating database table: {e}")

    def update_last_alert_time(self, symbol: str, alert_time: datetime):
        """
        Updates or inserts the last alert time for a given symbol.
        """
        time_str = alert_time.isoformat()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO alerts (symbol, last_alert_time)
                VALUES (?, ?)
            ''', (symbol, time_str))
            self.conn.commit()
            self.logger.info(f"Updated last alert time for {symbol} to {time_str}")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to update alert time for {symbol}: {e}")

    def get_last_alert_time(self, symbol: str) -> Optional[datetime]:
        """
        Retrieves the last alert time for a symbol from the database.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT last_alert_time FROM alerts WHERE symbol = ?', (symbol,))
            result = cursor.fetchone()
            if result:
                return datetime.fromisoformat(result[0])
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Failed to get last alert time for {symbol}: {e}")
            return None

    def close(self):
        """
        Closes the database connection.
        """
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed.")