import time
import threading
import subprocess
import platform
import requests
from typing import Callable

class NetworkDaemon:
    def __init__(self, auth_callback: Callable):
        self.active = True
        self.auth_callback = auth_callback
        self.interval = 300  # 5分钟
        self.target_ssids = ["GM-living", "东1-living"]  # 目标网络列表

    def start(self):
        def _monitor():
            while self.active:
                if self._should_connect():
                    if not self._check_internet():
                        self.auth_callback()
                time.sleep(10)  # 缩短SSID检测间隔

        threading.Thread(target=_monitor, daemon=True).start()

    def _should_connect(self) -> bool:
        """检查是否连接到目标网络"""
        current_ssid = self._get_current_ssid()
        return current_ssid in self.target_ssids if current_ssid else False

    def _get_current_ssid(self) -> str:
        """获取当前连接的SSID（编码问题修复版）"""
        try:
            system = platform.system()
            if system == 'Windows':
                cmd = ['netsh', 'wlan', 'show', 'interfaces']
                output = subprocess.check_output(
                    cmd,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    stderr=subprocess.DEVNULL
                )
                for line in output.split('\n'):
                    if 'SSID' in line and 'BSSID' not in line:
                        return line.split(':')[-1].strip()
            elif system == 'Linux':
                cmd = ['iwgetid', '-r']
                return subprocess.check_output(
                    cmd,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                ).strip()
            elif system == 'Darwin':
                cmd = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I'
                output = subprocess.check_output(
                    cmd,
                    shell=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                return output.split('SSID: ')[1].split('\n')[0].strip()
        except Exception as e:
            print(f"SSID检测失败: {str(e)}")
        return ""

    def _check_internet(self) -> bool:
        """专用网络连通性检测"""
        try:
            resp = requests.get("http://2.2.2.2", timeout=5)
            return resp.status_code == 200 and "portal" not in resp.url
        except:
            return False

    def stop(self):
        self.active = False