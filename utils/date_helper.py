from datetime import date, timedelta, datetime, time
from core.data_classes import MarketStatus

class DateHelper:
    @staticmethod
    def get_previous_trading_day() -> date:
        """
        Calculates the previous trading day.
        NOTE: This is a simple implementation and does not account for market holidays.
        """
        today = date.today()
        # Monday (weekday 0) -> Previous trading day is Friday
        if today.weekday() == 0:
            return today - timedelta(days=3)
        # Sunday (weekday 6) -> Previous trading day is Friday
        elif today.weekday() == 6:
            return today - timedelta(days=2)
        # All other days
        else:
            return today - timedelta(days=1)

    @staticmethod
    def get_market_status() -> MarketStatus:
        """
        Checks if the Indian stock market is currently open.
        """
        now = datetime.now().time()
        market_open = time(9, 15)
        market_close = time(15, 30)

        # Also check that it's a weekday
        if date.today().weekday() < 5: # Monday to Friday
            if market_open <= now <= market_close:
                return MarketStatus.OPEN

        return MarketStatus.CLOSED