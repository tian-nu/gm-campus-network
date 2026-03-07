"""
网络信息工具
获取本机 IP 地址和 MAC 地址
"""

import socket
import time
import uuid
import re
import logging
import os
from typing import Optional


class NetworkInfo:
    """网络信息获取工具类"""

    _logger = logging.getLogger(__name__)

    @staticmethod
    def get_ip_address() -> str:
        """
        获取本机 IP 地址

        优先通过连接外部服务器获取，失败则通过主机名获取

        Returns:
            IP 地址字符串
        """
        # 方法1: 通过连接外部服务器获取
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(2)
                s.connect(("114.114.114.114", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127."):
                    return ip
        except Exception:
            pass

        # 方法2: 通过主机名获取
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass

        # 方法3: 遍历所有网络接口
        try:
            import subprocess
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # 查找 IPv4 地址
            matches = re.findall(r"IPv4.*?:\s*(\d+\.\d+\.\d+\.\d+)", result.stdout)
            for ip in matches:
                if not ip.startswith("127."):
                    return ip
        except Exception:
            pass

        # 兜底值
        NetworkInfo._logger.warning("无法获取 IP 地址，使用默认值")
        return "10.0.0.1"

    @staticmethod
    def get_mac_address(config: Optional[dict] = None) -> str:
        """
        获取 MAC 地址

        优先从配置获取，否则自动检测

        Args:
            config: 配置字典，可包含 mac_address 键

        Returns:
            MAC 地址字符串（格式: xx:xx:xx:xx:xx:xx）
        """
        # 优先使用配置中的 MAC 地址
        if config and config.get("mac_address"):
            return config["mac_address"]

        # 自动获取 MAC 地址
        try:
            mac = uuid.getnode()
            mac_str = ':'.join(('%012x' % mac)[i:i+2] for i in range(0, 12, 2))
            return mac_str
        except Exception:
            pass

        # Windows 特定方法
        try:
            import subprocess
            result = subprocess.run(
                ["getmac", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # 解析输出
            lines = result.stdout.strip().split('\n')
            if lines:
                # 格式: "AA-BB-CC-DD-EE-FF","..."
                mac = lines[0].split(',')[0].strip('"').replace('-', ':').lower()
                if re.match(r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$', mac):
                    return mac
        except Exception:
            pass

        NetworkInfo._logger.warning("无法获取 MAC 地址，使用默认值")
        return "00:00:00:00:00:00"

    @classmethod
    def get_network_info(cls, config: Optional[dict] = None) -> dict:
        """
        获取完整的网络信息

        Args:
            config: 配置字典

        Returns:
            包含 ip, mac, timestamp 的字典
        """
        return {
            "ip": cls.get_ip_address(),
            "mac": cls.get_mac_address(config),
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """
        验证 IP 地址格式

        Args:
            ip: IP 地址字符串

        Returns:
            是否有效
        """
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def is_valid_mac(mac: str) -> bool:
        """
        验证 MAC 地址格式

        Args:
            mac: MAC 地址字符串

        Returns:
            是否有效
        """
        pattern = r'^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$'
        return bool(re.match(pattern, mac))

    @staticmethod
    def detect_proxy() -> dict:
        """
        检测系统是否启用了代理

        Returns:
            dict: 包含代理信息的字典
            {
                "has_proxy": bool,  # 是否检测到代理
                "proxy_type": str,  # 代理类型 (system/http/https/socks)
                "proxy_address": str,  # 代理地址
                "warning": str  # 警告信息
            }
        """
        result = {
            "has_proxy": False,
            "proxy_type": "",
            "proxy_address": "",
            "warning": ""
        }

        # 1. 检测系统代理（Windows注册表）
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)

            try:
                proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
                if proxy_enable:
                    proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
                    result["has_proxy"] = True
                    result["proxy_type"] = "system"
                    result["proxy_address"] = proxy_server
                    result["warning"] = f"检测到系统代理已开启: {proxy_server}"
                    NetworkInfo._logger.warning(f"系统代理已开启: {proxy_server}")
            except FileNotFoundError:
                pass

            winreg.CloseKey(key)
        except Exception as e:
            NetworkInfo._logger.debug(f"检测系统代理失败: {e}")

        # 2. 检测环境变量中的代理
        env_proxies = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
        for env_var in env_proxies:
            proxy_value = os.environ.get(env_var)
            if proxy_value:
                result["has_proxy"] = True
                result["proxy_type"] = "env"
                result["proxy_address"] = proxy_value
                result["warning"] = f"检测到环境变量代理({env_var}): {proxy_value}"
                NetworkInfo._logger.warning(f"环境变量代理 {env_var}: {proxy_value}")
                break

        # 3. 检测常见代理端口
        common_proxy_ports = [7890, 1080, 8080, 10809, 10808, 1087, 1086]  # Clash, V2Ray, SSR等常用端口
        for port in common_proxy_ports:
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)
                result_connect = test_socket.connect_ex(('127.0.0.1', port))
                test_socket.close()

                if result_connect == 0:
                    # 端口被占用，可能是代理软件
                    if not result["has_proxy"]:  # 如果还没检测到其他代理
                        result["has_proxy"] = True
                        result["proxy_type"] = "port"
                        result["proxy_address"] = f"127.0.0.1:{port}"
                        result["warning"] = f"检测到本地端口 {port} 可能在运行代理软件"
                        NetworkInfo._logger.warning(f"检测到本地代理端口: {port}")
            except Exception:
                pass

        return result

    @staticmethod
    def check_proxy_before_login() -> tuple:
        """
        登录前检查代理状态

        Returns:
            tuple: (has_proxy: bool, warning_message: str)
        """
        proxy_info = NetworkInfo.detect_proxy()

        if proxy_info["has_proxy"]:
            warning = f"⚠️ 检测到代理已开启\n\n{proxy_info['warning']}\n\n开着代理登录可能导致账号被封禁30分钟！\n建议先关闭代理后再登录。"
            return True, warning

        return False, ""
