import time
from typing import Dict

class AlertCooldownManager:
    def __init__(self, cooldown_minutes: int):
        self.cooldown_seconds = cooldown_minutes * 60
        self.last_alert_times: Dict[str, float] = {}

    def can_send_alert(self, symbol: str) -> bool:
        last_time = self.last_alert_times.get(symbol)
        if last_time and (time.time() - last_time) < self.cooldown_seconds:
            return False
        return True

    def record_alert_sent(self, symbol: str):
        self.last_alert_times[symbol] = time.time()