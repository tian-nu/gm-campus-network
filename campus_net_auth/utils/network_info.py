"""
网络信息工具
获取本机 IP 地址和 MAC 地址
检测代理/VPN状态
"""

import socket
import time
import uuid
import re
import logging
import os
import json
import glob
from typing import Optional, List, Dict, Tuple


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
    def get_mac_address(config: Optional[dict[str, object]] = None) -> str:
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


class ProxyDetector:
    """
    代理检测器
    检测各种代理软件配置，确保校园网不会被代理
    """

    # 校园网相关域名和IP模式
    CAMPUS_PATTERNS = [
        r"gzittc",  # 工贸职业技术学院域名
        r"xykd",    # 校园宽带
        r"cas\.gzittc",  # CAS认证
        r"10\.10\.21",   # 校园网IP段
        r"10\.\d+\.\d+\.\d+",  # 10.x.x.x 内网段
        r"portal",  # 门户
        r"campus",  # 校园
    ]

    # 代理软件配置文件路径
    CLASH_CONFIG_PATHS = [
        os.path.expanduser("~/.config/clash/config.yaml"),
        os.path.expanduser("~/.config/clash-verge/config.yaml"),
        os.path.expandvars("%USERPROFILE%/.config/clash/config.yaml"),
        os.path.expandvars("%USERPROFILE%/.config/clash-verge/config.yaml"),
    ]

    V2RAYN_CONFIG_PATHS = [
        os.path.expandvars("%USERPROFILE%/Documents/v2rayN/guiConfigs/config.json"),
        os.path.expandvars("%USERPROFILE%/Desktop/v2rayN/guiConfigs/config.json"),
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cached_result: Optional[Dict] = None
        self._cache_time: float = 0
        self._cache_ttl: float = 5.0  # 缓存5秒

    def detect_all(self) -> Dict:
        """
        执行所有代理检测

        Returns:
            {
                "should_block": bool,  # 是否应该阻止登录
                "reason": str,         # 阻止原因
                "details": {           # 详细检测结果
                    "system_proxy": {...},
                    "clash": {...},
                    "v2ray": {...},
                    "env_proxy": {...}
                }
            }
        """
        # 检查缓存
        current_time = time.time()
        if self._cached_result and (current_time - self._cache_time) < self._cache_ttl:
            return self._cached_result

        details = {
            "system_proxy": self._check_system_proxy(),
            "clash": self._check_clash(),
            "v2ray": self._check_v2ray(),
            "env_proxy": self._check_env_proxy(),
        }

        # 判断是否应该阻止
        should_block = False
        reasons = []

        for name, result in details.items():
            if result.get("proxies_campus", False):
                should_block = True
                reasons.append(f"{name}: {result.get('message', '')}")

        result = {
            "should_block": should_block,
            "reason": "; ".join(reasons) if reasons else "",
            "details": details
        }

        # 更新缓存
        self._cached_result = result
        self._cache_time = current_time

        return result

    def should_block_campus_login(self) -> Tuple[bool, str]:
        """
        判断是否应该阻止校园网登录

        Returns:
            (should_block, reason)
        """
        result = self.detect_all()
        return result["should_block"], result["reason"]

    def _check_system_proxy(self) -> Dict:
        """检查系统代理设置"""
        result = {
            "has_proxy": False,
            "proxies_campus": False,
            "message": ""
        }

        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)

            try:
                proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
                if proxy_enable:
                    proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
                    result["has_proxy"] = True

                    # 检查PAC文件内容
                    try:
                        pac_url = winreg.QueryValueEx(key, "AutoConfigURL")[0]
                        if pac_url:
                            result["pac_url"] = pac_url
                            # 如果PAC包含校园网相关域名，标记为危险
                            if self._check_pac_for_campus(pac_url):
                                result["proxies_campus"] = True
                                result["message"] = f"系统PAC代理可能包含校园网规则: {pac_url}"
                    except:
                        pass

                    # 检查是否有绕过列表包含校园网
                    try:
                        bypass = winreg.QueryValueEx(key, "ProxyOverride")[0]
                        if bypass:
                            result["bypass"] = bypass
                    except:
                        pass

            except FileNotFoundError:
                pass

            winreg.CloseKey(key)
        except Exception as e:
            self.logger.debug(f"检查系统代理失败: {e}")

        return result

    def _check_clash(self) -> Dict:
        """检查Clash/Clash Verge配置"""
        result = {
            "has_proxy": False,
            "proxies_campus": False,
            "message": ""
        }

        for config_path in self.CLASH_CONFIG_PATHS:
            if os.path.exists(config_path):
                result["has_proxy"] = True
                result["config_path"] = config_path

                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 检查规则部分
                    if self._check_content_for_campus(content):
                        result["proxies_campus"] = True
                        result["message"] = f"Clash配置包含校园网规则: {config_path}"
                        return result

                except Exception as e:
                    self.logger.debug(f"读取Clash配置失败 {config_path}: {e}")

        return result

    def _check_v2ray(self) -> Dict:
        """检查V2RayN配置"""
        result = {
            "has_proxy": False,
            "proxies_campus": False,
            "message": ""
        }

        for config_path in self.V2RAYN_CONFIG_PATHS:
            if os.path.exists(config_path):
                result["has_proxy"] = True
                result["config_path"] = config_path

                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    # 检查路由规则
                    routing = config.get("routing", {})
                    rules = routing.get("rules", [])

                    for rule in rules:
                        domain = rule.get("domain", [])
                        ip = rule.get("ip", [])
                        outbound = rule.get("outboundTag", "")

                        # 检查是否代理了校园网
                        combined = " ".join(domain + ip)
                        if self._matches_campus_patterns(combined):
                            result["proxies_campus"] = True
                            result["message"] = f"V2RayN路由规则代理校园网: {outbound}"
                            return result

                except Exception as e:
                    self.logger.debug(f"读取V2RayN配置失败 {config_path}: {e}")

        return result

    def _check_env_proxy(self) -> Dict:
        """检查环境变量代理"""
        result = {
            "has_proxy": False,
            "proxies_campus": False,
            "message": ""
        }

        env_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]

        for var in env_vars:
            value = os.environ.get(var)
            if value:
                result["has_proxy"] = True
                result["env_var"] = var
                result["proxy_url"] = value

                # 环境变量代理通常是全局的，可能包含校园网
                # 保守起见，如果有环境变量代理，提示风险
                result["message"] = f"环境变量代理 {var}={value}"
                break

        return result

    def _check_pac_for_campus(self, pac_url: str) -> bool:
        """检查PAC文件是否包含校园网规则"""
        try:
            # 只处理本地PAC文件
            if pac_url.startswith("file://"):
                pac_path = pac_url[7:]  # 去掉 file://
                if os.path.exists(pac_path):
                    with open(pac_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return self._check_content_for_campus(content)
        except Exception as e:
            self.logger.debug(f"检查PAC文件失败: {e}")

        return False

    def _check_content_for_campus(self, content: str) -> bool:
        """检查内容是否包含校园网相关规则"""
        content_lower = content.lower()

        for pattern in self.CAMPUS_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True

        return False

    def _matches_campus_patterns(self, text: str) -> bool:
        """检查文本是否匹配校园网模式"""
        text_lower = text.lower()

        for pattern in self.CAMPUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True

        return False


# 全局代理检测器实例
_proxy_detector: Optional[ProxyDetector] = None


def get_proxy_detector() -> ProxyDetector:
    """获取全局代理检测器实例"""
    global _proxy_detector
    if _proxy_detector is None:
        _proxy_detector = ProxyDetector()
    return _proxy_detector
