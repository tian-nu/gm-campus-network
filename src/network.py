import time
import threading
from typing import Callable
import requests

class NetworkDaemon:
    def __init__(self, auth_callback: Callable):
        self.active = True
        self.auth_callback = auth_callback
        self.interval = 300  # 5分钟

    def start(self):
        def _monitor():
            while self.active:
                if not self._check_connection():
                    self.auth_callback()
                time.sleep(self.interval)

        threading.Thread(target=_monitor, daemon=True).start()

    def _check_connection(self) -> bool:
        """专用网络检测"""
        try:
            resp = requests.get("http://2.2.2.2/ping", timeout=5)
            return resp.status_code == 204
        except:
            return False

    def stop(self):
        self.active = False