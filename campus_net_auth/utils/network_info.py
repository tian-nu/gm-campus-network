"""
网络信息工具
获取本机 IP 地址和 MAC 地址
"""

import enum
import socket
import subprocess
import sys
import time
import re
import logging
import os
from typing import Optional, Set

# Windows: 隐藏 subprocess 弹出的 CMD 窗口
_SUBPROCESS_FLAGS = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if sys.platform == "win32" else {}
)

# 这些名字的网卡不能当主链路，否则会拿到 26.x / 172.31.x 这类假 IP
# 注意：这里不能 import ..core.constants，core/__init__ 会反向 import 本模块，
# 形成循环导入，所以关键字直接写在这里。
VIRTUAL_ADAPTER_KEYWORDS = (
    "radmin", "tap", "tun", "wireguard", "openvpn", "zerotier",
    "tailscale", "vmware", "virtualbox", "hyper-v", "vethernet",
    "loopback", "bluetooth", "蓝牙", "wsl", "docker",
)


def _decode_output(value) -> str:
    """
    把子进程输出解成字符串。

    Windows 下 netsh / ipconfig 有时输出 UTF-8、有时 GBK（取决于系统区域设置），
    所以按 utf-8 → gbk → gb18030 依次试，全失败再用 replace 兜底。
    已经是 str 的直接返回，方便单测里用假对象替换 subprocess。
    """
    if isinstance(value, str):
        return value
    if not value:
        return ""
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            return value.decode(enc)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _run_subprocess(args: list, timeout: int = 3) -> subprocess.CompletedProcess:
    """
    执行子进程，自动处理编码问题（UTF-8 → GBK 自适应）

    Windows netsh/ipconfig 输出可能是 UTF-8 或 GBK，此函数自动适配。
    """
    kwargs = {"capture_output": True, "timeout": timeout, **_SUBPROCESS_FLAGS}
    # 不传 text/encoding，拿原始 bytes
    result = subprocess.run(args, **kwargs)
    result.stdout = _decode_output(result.stdout)
    result.stderr = _decode_output(result.stderr)
    return result


class WlanStatus(enum.Enum):
    """WLAN 状态枚举"""
    CONNECTED = "connected"           # WiFi 已连接
    NOT_CONNECTED = "not_connected"   # WLAN 开启但未连接 WiFi
    DISABLED = "disabled"             # WLAN 适配器被禁用
    NOT_AVAILABLE = "not_available"   # 无 WLAN 适配器（台式机等）


class NetworkInfo:
    """网络信息获取工具类"""

    _logger = logging.getLogger(__name__)

    # 缓存：避免短时间内反复执行 subprocess
    _cached_network_names: Optional[Set[str]] = None
    _cache_time: float = 0.0
    _CACHE_TTL: float = 30.0  # 缓存有效期（秒）

    # ------------------------------------------------------------------ 网卡选择

    @staticmethod
    def _default_routes() -> list:
        """
        读默认路由，返回按 metric 升序的 [(metric, interface_ip), ...]

        路由表「接口」那一列正好等于该网卡自己的 IP，
        可以直接拿去和 ipconfig 里的网卡块匹配。
        """
        try:
            result = _run_subprocess(["route", "print", "-4"], timeout=3)
        except Exception:
            return []

        routes = []
        for line in (result.stdout or "").splitlines():
            fields = line.split()
            if len(fields) < 5:
                continue
            if fields[0] != "0.0.0.0" or fields[1] != "0.0.0.0":
                continue
            if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", fields[2]):
                continue
            try:
                metric = int(fields[-1])
            except ValueError:
                metric = 99999
            routes.append((metric, fields[3]))
        routes.sort(key=lambda x: x[0])
        return routes

    @staticmethod
    def _is_virtual_adapter(name: str) -> bool:
        """名字命中虚拟网卡关键字就判定为虚拟"""
        lowered = (name or "").lower()
        return any(k in lowered for k in VIRTUAL_ADAPTER_KEYWORDS)

    @classmethod
    def parse_adapters(cls) -> list:
        """
        解析 ipconfig /all，返回所有网卡。

        每项：{"name", "ip", "mac", "gw", "lease", "kind", "virtual"}
        kind 取值：wired / wifi / virtual / other
        """
        try:
            result = _run_subprocess(["ipconfig", "/all"], timeout=5)
        except Exception:
            return []

        adapters = []
        current = None

        for line in (result.stdout or "").splitlines():
            if not line.strip():
                continue
            if not line[0].isspace() and line.rstrip().endswith(":"):
                current = {
                    "name": line.strip().rstrip(":").strip(),
                    "ip": "", "mac": "", "gw": "", "lease": "",
                }
                adapters.append(current)
                continue
            if current is None:
                continue

            m = re.search(r"IPv4\s*(?:地址|Address)[^:]*:\s*([\d.]+)", line)
            if m and not current["ip"]:
                current["ip"] = m.group(1)
                continue
            m = re.search(r"(?:物理地址|Physical Address)[^:]*:\s*([0-9A-Fa-f-]{17})", line)
            if m and not current["mac"]:
                current["mac"] = m.group(1).lower()
                continue
            m = re.search(r"(?:默认网关|Default Gateway)[^:]*:\s*([\d.]+)", line)
            if m and not current["gw"]:
                current["gw"] = m.group(1)
                continue
            m = re.search(r"(?:获得租约|Lease Obtained)[^:]*:\s*(.+)", line)
            if m and not current["lease"]:
                current["lease"] = m.group(1).strip()

        for item in adapters:
            # 标题带「以太网适配器 / 无线局域网适配器」前缀，去掉只留网卡名
            item["name"] = re.sub(
                r"^(以太网适配器|无线局域网适配器|未知适配器|"
                r"Ethernet adapter|Wireless LAN adapter|Unknown adapter)\s*",
                "", item["name"], flags=re.I,
            ).strip()

            name = item["name"]
            if cls._is_virtual_adapter(name):
                item["kind"] = "virtual"
                item["virtual"] = True
            elif re.search(r"(WLAN|无线|Wi-?Fi)", name, re.I):
                item["kind"] = "wifi"
                item["virtual"] = False
            elif re.search(r"(以太网|Ethernet|本地连接|Local Area Connection)", name, re.I):
                item["kind"] = "wired"
                item["virtual"] = False
            else:
                item["kind"] = "other"
                item["virtual"] = False

        return adapters

    @classmethod
    def get_active_adapter(cls) -> Optional[dict]:
        """
        取真正承载默认路由的物理网卡。

        机器上常同时有 Radmin/VPN/Docker 虚拟网卡，它们也有 IP 甚至网关，
        靠「有没有网关」判断会选错（拿到 26.x / 172.31.x 去认证必然失败）。
        metric 差距通常很大（有线 25 vs Radmin 9257），这个判据最可靠。
        """
        adapters = cls.parse_adapters()
        by_ip = {a["ip"]: a for a in adapters if a["ip"]}

        for metric, interface_ip in cls._default_routes():
            adapter = by_ip.get(interface_ip)
            if adapter and not adapter["virtual"]:
                adapter["metric"] = metric
                return adapter

        # 兜底：有网关、非虚拟、不是 169.254 自分配地址
        candidates = [a for a in adapters
                      if a["ip"] and a["gw"] and not a["virtual"]
                      and not a["ip"].startswith("169.254.")]
        if candidates:
            candidates.sort(key=lambda a: 0 if a["kind"] == "wired" else 1)
            return candidates[0]

        return None

    @classmethod
    def list_disabled_adapters(cls) -> list:
        """
        列出被系统禁用的网卡。

        ipconfig 不会显示已禁用的网卡，所以单独用 netsh 查——
        「网线插上没反应」十有八九就是网卡被禁用了。
        """
        try:
            result = _run_subprocess(["netsh", "interface", "show", "interface"], timeout=3)
        except Exception:
            return []

        disabled = []
        for line in (result.stdout or "").splitlines():
            if "已禁用" in line or "Disabled" in line:
                fields = line.split()
                if len(fields) >= 4:
                    disabled.append(fields[-1])
        return disabled

    # ------------------------------------------------------------------ IP / MAC

    @classmethod
    def get_ip_address(cls) -> str:
        """
        获取本机 IP 地址

        优先用主用网卡的 IP（按路由 metric 选），
        拿不到再退回「连一下外网看源地址」。

        Returns:
            IP 地址字符串
        """
        adapter = cls.get_active_adapter()
        if adapter and adapter["ip"]:
            return adapter["ip"]

        # 兜底：UDP 连一下外网看源地址（不依赖网卡名解析）
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(1)
                s.connect(("223.5.5.5", 53))
                ip = s.getsockname()[0]
                if ip and not ip.startswith(("127.", "0.0.0.0")):
                    return ip
        except Exception:
            pass

        cls._logger.warning("无法获取 IP 地址，使用默认值")
        return "10.0.0.1"

    @classmethod
    def get_mac_address(cls, config: Optional[dict[str, object]] = None) -> str:
        """
        获取 MAC 地址

        优先从配置获取，否则取主用网卡的物理地址。

        注意：不能用 uuid.getnode()——它返回的是系统某个网卡（通常是第一块）
        的 MAC，本机装了 Radmin VPN / VMware 时经常抓到虚拟网卡的地址，
        拿去门户认证必然对不上 RADIUS 里的记录。

        Args:
            config: 配置字典，可包含 mac_address 键

        Returns:
            MAC 地址字符串（格式: xx:xx:xx:xx:xx:xx）
        """
        # 优先使用配置中的 MAC 地址
        if config and config.get("mac_address"):
            return config["mac_address"]

        # 主用网卡的物理地址
        adapter = cls.get_active_adapter()
        if adapter and adapter["mac"]:
            return adapter["mac"]

        # 兜底：getmac 第一行
        try:
            result = _run_subprocess(["getmac", "/fo", "csv", "/nh"], timeout=2)
            lines = (result.stdout or "").strip().split('\n')
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
            包含 ip, mac, adapter, gateway, kind, timestamp 的字典
        """
        adapter = cls.get_active_adapter() or {}
        return {
            "ip": cls.get_ip_address(),
            "mac": cls.get_mac_address(config),
            "adapter": adapter.get("name", ""),
            "gateway": adapter.get("gw", ""),
            "kind": adapter.get("kind", ""),
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

    @classmethod
    def get_connected_network_names(cls) -> Set[str]:
        """
        获取当前连接的所有网络名称（WiFi SSID / 以太网适配器名称 / 网络配置名）

        结果缓存 30 秒（空结果不缓存），避免短时间内反复执行 subprocess。
        """
        now = time.time()
        # 只缓存非空结果
        if (cls._cached_network_names is not None
                and cls._cached_network_names  # 非空才用缓存
                and now - cls._cache_time < cls._CACHE_TTL):
            NetworkInfo._logger.debug(f"使用缓存的网络名称: {cls._cached_network_names}")
            return cls._cached_network_names

        names: Set[str] = set()

        # 方法1: netsh interface show interface（最快最可靠）
        try:
            result = _run_subprocess(
                ["netsh", "interface", "show", "interface"], timeout=2)
            NetworkInfo._logger.debug(f"netsh interface 原始输出: {result.stdout[:200]}")
            for line in result.stdout.split('\n'):
                tokens = line.split()
                if len(tokens) >= 4 and tokens[1].lower() == 'connected':
                    name = " ".join(tokens[3:])
                    if name:
                        names.add(name)
                        NetworkInfo._logger.debug(f"检测到连接接口: {name}")
        except Exception as e:
            NetworkInfo._logger.debug(f"获取接口名称失败: {e}")

        # 方法2: netsh wlan show interfaces（获取 WiFi SSID）
        try:
            result = _run_subprocess(
                ["netsh", "wlan", "show", "interfaces"], timeout=2)
            NetworkInfo._logger.debug(f"netsh wlan 原始输出: {result.stdout[:200]}")
            for line in result.stdout.split('\n'):
                line_stripped = line.strip()
                if 'SSID' in line_stripped and 'BSSID' not in line_stripped:
                    parts = line_stripped.split(':', 1)
                    if len(parts) >= 2:
                        ssid = parts[1].strip()
                        if ssid:
                            names.add(ssid)
                            NetworkInfo._logger.debug(f"检测到 WiFi SSID: {ssid}")
        except Exception as e:
            NetworkInfo._logger.debug(f"获取 WiFi SSID 失败: {e}")

        # 方法3: ipconfig 兜底（提取适配器描述/名称）
        if not names:
            try:
                result = _run_subprocess(["ipconfig"], timeout=2)
                # 匹配 "以太网适配器 xxx:" 或 "无线局域网适配器 xxx:"
                for m in re.finditer(
                    r'(?:以太网|无线局域网|Ethernet|Wireless LAN)\s*适配器\s*([^:\n]+)',
                    result.stdout
                ):
                    name = m.group(1).strip()
                    if name:
                        names.add(name)
                        NetworkInfo._logger.debug(f"ipconfig 检测到适配器: {name}")
            except Exception as e:
                NetworkInfo._logger.debug(f"ipconfig 解析失败: {e}")

        # 方法4: Windows 网络配置文件（注册表）
        if not names:
            try:
                import winreg
                key_path = (r"SOFTWARE\Microsoft\Windows NT"
                            r"\CurrentVersion\NetworkList\Signatures\Unmanaged")
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY
                )
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ)
                        try:
                            profile_name = winreg.QueryValueEx(subkey, "ProfileName")[0]
                            managed = winreg.QueryValueEx(subkey, "Managed")[0]
                            if managed == 0 and profile_name:
                                names.add(profile_name)
                                NetworkInfo._logger.debug(
                                    f"检测到网络配置文件: {profile_name}"
                                )
                        except FileNotFoundError:
                            pass
                        winreg.CloseKey(subkey)
                        index += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except Exception as e:
                NetworkInfo._logger.debug(f"获取网络配置文件失败: {e}")

        # 只缓存非空结果
        if names:
            cls._cached_network_names = names
            cls._cache_time = now
        NetworkInfo._logger.info(f"当前连接的网络名称: {names}")
        return names

    @classmethod
    def get_wlan_status(cls) -> WlanStatus:
        """
        检测 WLAN 状态

        通过 Windows netsh 命令判断 WLAN 适配器是否可用、是否已连接 WiFi。

        Returns:
            WlanStatus 枚举值
        """
        # 1. 检查是否有无线接口（WLAN 适配器）
        has_wireless_adapter = False
        wireless_connected = False
        wireless_enabled = False

        try:
            result = _run_subprocess(
                ["netsh", "interface", "show", "interface"], timeout=3)
            for line in result.stdout.split('\n'):
                tokens = line.split()
                if len(tokens) >= 4:
                    admin_state = tokens[0].lower()
                    conn_state = tokens[1].lower()
                    iface_type = tokens[2].lower() if len(tokens) > 2 else ""
                    name = " ".join(tokens[3:]).lower()

                    # 判断是否是无线接口
                    is_wireless = any(kw in name for kw in (
                        "wlan", "wi-fi", "wifi", "wireless",
                        "无线", " WLAN"
                    )) or "wireless" in iface_type

                    if is_wireless:
                        has_wireless_adapter = True
                        if admin_state == "enabled":
                            wireless_enabled = True
                        if conn_state == "connected":
                            wireless_connected = True
        except Exception as e:
            cls._logger.debug(f"检测无线接口失败: {e}")

        # 2. 用 netsh wlan show interfaces 进一步确认
        #    （某些系统接口名不含 wlan，但 wlan 命令仍可用）
        try:
            result = _run_subprocess(
                ["netsh", "wlan", "show", "interfaces"], timeout=3)
            output = result.stdout

            # 如果命令本身报错（如"无线自动配置服务未运行"），说明 WLAN 服务未启动
            if "not running" in output.lower() or "没有运行" in output:
                if has_wireless_adapter:
                    return WlanStatus.DISABLED
                return WlanStatus.NOT_AVAILABLE

            # 检查是否有接口
            if "there is no" in output.lower() or "系统上没有" in output:
                # netsh wlan 说没有接口
                if has_wireless_adapter:
                    # 有适配器但 wlan 服务不可用 = 被禁用
                    return WlanStatus.DISABLED
                return WlanStatus.NOT_AVAILABLE

            # 解析状态
            for line in output.split('\n'):
                line_stripped = line.strip()
                if 'state' in line_stripped.lower() or '状态' in line_stripped:
                    if 'connected' in line_stripped.lower() or '已连接' in line_stripped:
                        return WlanStatus.CONNECTED
                    elif 'disconnected' in line_stripped.lower() or '已断开' in line_stripped:
                        return WlanStatus.NOT_CONNECTED
        except Exception as e:
            cls._logger.debug(f"netsh wlan 检测失败: {e}")

        # 3. 根据之前的接口检测结果判断
        if not has_wireless_adapter:
            return WlanStatus.NOT_AVAILABLE
        if not wireless_enabled:
            return WlanStatus.DISABLED
        if wireless_connected:
            return WlanStatus.CONNECTED
        return WlanStatus.NOT_CONNECTED

    @staticmethod
    def is_network_whitelisted(whitelist: Optional[list] = None) -> bool:
        """
        检查当前网络是否在白名单中

        Args:
            whitelist: 网络名称白名单列表，若为 None 或空则允许所有网络

        Returns:
            True 表示允许在此网络下操作
        """
        if not whitelist:
            return True  # 白名单为空，允许所有网络

        connected_names = NetworkInfo.get_connected_network_names()

        if not connected_names:
            # 无法获取任何网络名称，保守处理：允许操作
            NetworkInfo._logger.warning("无法获取网络名称，默认允许操作")
            return True

        # 检查是否匹配
        whitelist_lower = {w.strip().lower() for w in whitelist if w.strip()}
        for name in connected_names:
            if name.lower() in whitelist_lower:
                NetworkInfo._logger.info(f"当前网络 '{name}' 在白名单中，允许操作")
                return True

        NetworkInfo._logger.warning(
            f"当前网络 {connected_names} 不在白名单 {whitelist} 中，跳过操作"
        )
        return False
