"""
网络变化监听器
监听网卡切换、IP变化、网关变化等网络相关事件
（睡眠/唤醒检测由 power_monitor.py 的 WM_POWERBROADCAST 负责）
"""

import logging
import threading
import time
import socket
from typing import Callable, Optional, Dict, Set
from dataclasses import dataclass, field
from enum import Enum, auto

from .helpers import run_hidden_command as _run_hidden_command


class NetworkEventType(Enum):
    """网络事件类型"""
    IP_CHANGED = auto()           # IP地址变化
    ADAPTER_CHANGED = auto()      # 网卡变化（有线/无线切换）
    CONNECTION_UP = auto()        # 网络连接建立
    CONNECTION_DOWN = auto()      # 网络连接断开
    GATEWAY_CHANGED = auto()      # 网关变化


@dataclass
class NetworkEvent:
    """网络事件数据类"""
    event_type: NetworkEventType
    timestamp: float = field(default_factory=time.time)
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    details: Dict = field(default_factory=dict)


class NetworkMonitor:
    """
    网络变化监听器
    监听网卡切换、IP变化、网关变化等事件

    注意：睡眠/唤醒检测由 PowerMonitor（WM_POWERBROADCAST）负责，
    本类不再做时间差检测和电源状态轮询。
    """

    def __init__(
        self,
        on_event: Optional[Callable[[NetworkEvent], None]] = None,
        check_interval: float = 10.0
    ):
        """
        初始化网络监听器

        Args:
            on_event: 网络事件回调函数
            check_interval: 检测间隔（秒），默认 10 秒
        """
        self.logger = logging.getLogger(__name__)
        self.on_event = on_event
        self.check_interval = check_interval

        # 线程控制
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

        # 状态记录
        self._last_ip: str = ""
        self._last_adapter: str = ""
        self._last_gateway: str = ""
        self._last_adapters: Set[str] = set()
        self._was_connected: bool = False

        # 网卡/网关检测计数器（降低 ipconfig/route 调用频率）
        self._heavy_check_counter: int = 0
        self._heavy_check_interval: int = 6  # 每 6 轮（约 60 秒）检测一次网卡和网关

        # 统计信息
        self.event_count: int = 0

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """启动监听器"""
        if self.is_running:
            self.logger.warning("网络监听器已在运行")
            return

        # 初始化状态
        self._initialize_state()

        self._stop_event.clear()
        self._is_running = True

        self._thread = threading.Thread(
            target=self._worker,
            name="NetworkMonitorThread",
            daemon=True
        )
        self._thread.start()
        self.logger.info(f"网络监听器已启动，检测间隔: {self.check_interval}秒")

    def stop(self, timeout: float = 5.0) -> bool:
        """
        停止监听器

        Args:
            timeout: 等待线程结束的超时时间

        Returns:
            是否成功停止
        """
        if not self._is_running:
            return True

        self._stop_event.set()
        self._is_running = False

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            stopped = not self._thread.is_alive()
            if stopped:
                self.logger.info("网络监听器已停止")
            else:
                self.logger.warning("网络监听器停止超时")
            return stopped

        return True

    def _initialize_state(self) -> None:
        """初始化状态记录"""
        self._last_ip = self._get_current_ip()
        self._last_adapter = self._get_primary_adapter()
        self._last_gateway = self._get_default_gateway()
        self._last_adapters = self._get_all_adapters()
        self._was_connected = self._check_internet_connectivity()

        self.logger.debug(f"初始化状态 - IP: {self._last_ip}, 网卡: {self._last_adapter}, "
                         f"网关: {self._last_gateway}, 连接: {self._was_connected}")

    def _worker(self) -> None:
        """监听工作线程"""
        while not self._stop_event.is_set():
            try:
                # IP 变化检测（轻量，每次都做）
                self._check_ip_change()

                # 连接状态检测（轻量，每次都做）
                self._check_connection_change()

                # 网卡/网关检测（重量级，低频）
                self._heavy_check_counter += 1
                if self._heavy_check_counter >= self._heavy_check_interval:
                    self._heavy_check_counter = 0
                    self._check_adapter_change()
                    self._check_gateway_change()

            except Exception as e:
                self.logger.error(f"网络监听异常: {e}")

            # 等待下一次检测
            self._stop_event.wait(self.check_interval)

    def _check_ip_change(self) -> None:
        """检测IP地址变化"""
        current_ip = self._get_current_ip()

        if current_ip != self._last_ip and (current_ip or self._last_ip):
            self.logger.info(f"IP地址变化: {self._last_ip} -> {current_ip}")

            event = NetworkEvent(
                event_type=NetworkEventType.IP_CHANGED,
                old_value=self._last_ip,
                new_value=current_ip,
                details={"timestamp": time.time()}
            )
            self._emit_event(event)

            self._last_ip = current_ip

    def _check_adapter_change(self) -> None:
        """检测网卡变化"""
        current_adapters = self._get_all_adapters()
        current_primary = self._get_primary_adapter()

        # 检测主网卡变化
        if current_primary != self._last_adapter and (current_primary or self._last_adapter):
            self.logger.info(f"主网卡变化: {self._last_adapter} -> {current_primary}")

            adapter_type = self._detect_adapter_type(current_primary)
            old_adapter_type = self._detect_adapter_type(self._last_adapter)

            event = NetworkEvent(
                event_type=NetworkEventType.ADAPTER_CHANGED,
                old_value=self._last_adapter,
                new_value=current_primary,
                details={
                    "old_type": old_adapter_type,
                    "new_type": adapter_type,
                    "all_adapters": list(current_adapters)
                }
            )
            self._emit_event(event)

            self._last_adapter = current_primary

        # 检测网卡增删
        added = current_adapters - self._last_adapters
        removed = self._last_adapters - current_adapters

        if added or removed:
            self.logger.debug(f"网卡变化 - 新增: {added}, 移除: {removed}")

        self._last_adapters = current_adapters

    def _check_gateway_change(self) -> None:
        """检测网关变化"""
        current_gateway = self._get_default_gateway()

        if current_gateway != self._last_gateway and (current_gateway or self._last_gateway):
            self.logger.info(f"网关变化: {self._last_gateway} -> {current_gateway}")

            event = NetworkEvent(
                event_type=NetworkEventType.GATEWAY_CHANGED,
                old_value=self._last_gateway,
                new_value=current_gateway
            )
            self._emit_event(event)

            self._last_gateway = current_gateway

    def _check_connection_change(self) -> None:
        """检测网络连接状态变化"""
        is_connected = self._check_internet_connectivity()

        if is_connected != self._was_connected:
            if is_connected:
                self.logger.info("网络连接已建立")
                event = NetworkEvent(
                    event_type=NetworkEventType.CONNECTION_UP,
                    new_value="connected"
                )
            else:
                self.logger.info("网络连接已断开")
                event = NetworkEvent(
                    event_type=NetworkEventType.CONNECTION_DOWN,
                    new_value="disconnected"
                )

            self._emit_event(event)
            self._was_connected = is_connected

    def _emit_event(self, event: NetworkEvent) -> None:
        """发送事件"""
        self.event_count += 1

        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                self.logger.error(f"事件回调异常: {e}")

    def _get_current_ip(self) -> str:
        """获取当前IP地址"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(2)
                s.connect(("114.114.114.114", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127."):
                    return ip
        except Exception:
            pass

        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass

        return ""

    def _get_primary_adapter(self) -> str:
        """获取主网卡名称"""
        try:
            result = _run_hidden_command(["route", "print", "0.0.0.0"], timeout=3)

            lines = result.stdout.split('\n')
            for line in lines:
                if '0.0.0.0' in line and 'Gateway' not in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        adapter = parts[-1]
                        return adapter

        except Exception as e:
            self.logger.debug(f"获取主网卡失败: {e}")

        return ""

    def _get_all_adapters(self) -> Set[str]:
        """获取所有网卡"""
        adapters = set()

        try:
            result = _run_hidden_command(["ipconfig"], timeout=3)

            lines = result.stdout.split('\n')
            for line in lines:
                if '适配器' in line or 'Adapter' in line:
                    if ':' in line:
                        adapter_name = line.split(':')[0].strip()
                        for prefix in ['以太网适配器 ', '无线局域网适配器 ', 'Ethernet adapter ', 'Wireless LAN adapter ']:
                            if prefix in adapter_name:
                                adapter_name = adapter_name.replace(prefix, '').strip()
                        adapters.add(adapter_name)

        except Exception as e:
            self.logger.debug(f"获取所有网卡失败: {e}")

        return adapters

    def _get_default_gateway(self) -> str:
        """获取默认网关"""
        try:
            result = _run_hidden_command(["ipconfig"], timeout=3)

            lines = result.stdout.split('\n')
            for i, line in enumerate(lines):
                if '默认网关' in line or 'Default Gateway' in line:
                    if ':' in line:
                        gateway = line.split(':')[-1].strip()
                        if gateway and gateway != '':
                            return gateway

        except Exception as e:
            self.logger.debug(f"获取默认网关失败: {e}")

        return ""

    def _check_internet_connectivity(self) -> bool:
        """检查互联网连通性"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(("114.114.114.114", 53))
                return True
        except Exception:
            pass

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(("8.8.8.8", 53))
                return True
        except Exception:
            pass

        return False

    def _detect_adapter_type(self, adapter_name: str) -> str:
        """
        检测网卡类型

        Returns:
            "wired" - 有线网卡
            "wireless" - 无线网卡
            "unknown" - 未知
        """
        if not adapter_name:
            return "unknown"

        adapter_lower = adapter_name.lower()

        wireless_keywords = ['wi-fi', 'wifi', 'wireless', 'wlan', '无线']
        for keyword in wireless_keywords:
            if keyword in adapter_lower:
                return "wireless"

        wired_keywords = ['ethernet', 'eth', '有线', '以太网']
        for keyword in wired_keywords:
            if keyword in adapter_lower:
                return "wired"

        return "unknown"


class NetworkEventHandler:
    """
    网络事件处理器
    处理各种网络事件并执行相应操作
    """

    def __init__(
        self,
        authenticator=None,
        reconnect_service=None,
        on_reconnect_required: Optional[Callable[[], None]] = None
    ):
        """
        初始化事件处理器

        Args:
            authenticator: 认证器实例
            reconnect_service: 重连服务实例
            on_reconnect_required: 需要重新连接时的回调
        """
        self.logger = logging.getLogger(__name__)
        self.authenticator = authenticator
        self.reconnect_service = reconnect_service
        self.on_reconnect_required = on_reconnect_required

        # 防抖动：避免短时间内多次触发
        self._last_reconnect_time: float = 0
        self._reconnect_cooldown: float = 10.0  # 10秒内不重复触发

        # 待处理的合并事件类型：短时间内多个事件只触发一次重连
        self._pending_event_types: set = set()
        self._pending_timer: Optional[threading.Timer] = None
        self._event_merge_window: float = 3.0  # 事件合并窗口（秒）

        # 事件统计
        self.event_stats: Dict[NetworkEventType, int] = {}

    def handle_event(self, event: NetworkEvent) -> None:
        """
        处理网络事件（带事件合并）

        短时间内多个事件会合并为一次重连，避免风暴效应。

        Args:
            event: 网络事件
        """
        # 更新统计
        self.event_stats[event.event_type] = self.event_stats.get(event.event_type, 0) + 1

        self.logger.info(f"处理网络事件: {event.event_type.name}")

        # CONNECTION_DOWN：立即加速重连服务检测间隔
        if event.event_type == NetworkEventType.CONNECTION_DOWN:
            self._handle_connection_down(event)
            return

        # 其他事件加入合并队列
        self._pending_event_types.add(event.event_type.name)

        # 取消之前的定时器
        if self._pending_timer is not None:
            self._pending_timer.cancel()

        # 设置新的合并定时器
        def _flush_pending():
            types = ", ".join(sorted(self._pending_event_types))
            self._pending_event_types.clear()
            self._pending_timer = None
            self._trigger_reconnect(f"网络变化合并事件: {types}")

        self._pending_timer = threading.Timer(self._event_merge_window, _flush_pending)
        self._pending_timer.daemon = True
        self._pending_timer.start()

    def _handle_connection_down(self, event: NetworkEvent) -> None:
        """处理网络连接断开事件"""
        self.logger.info("网络连接已断开，重置重连服务间隔以加速检测")
        if self.reconnect_service:
            try:
                self.reconnect_service.trigger_immediate_check()
            except AttributeError:
                # 兼容旧版无 trigger_immediate_check 的情况
                self.reconnect_service._current_interval = max(
                    float(self.reconnect_service.check_interval),
                    self.reconnect_service._min_interval
                )
                self.reconnect_service._stable_count = 0

    def _trigger_reconnect(self, reason: str) -> None:
        """
        触发重新连接

        Args:
            reason: 触发原因
        """
        current_time = time.time()

        # 检查冷却时间
        if current_time - self._last_reconnect_time < self._reconnect_cooldown:
            self.logger.debug(f"重新连接冷却中，跳过: {reason}")
            return

        self._last_reconnect_time = current_time
        self.logger.info(f"触发重新连接: {reason}")

        # 优先调用回调
        if self.on_reconnect_required:
            try:
                self.on_reconnect_required()
            except Exception as e:
                self.logger.error(f"重新连接回调异常: {e}")

        # 或者通过重连服务触发
        elif self.reconnect_service:
            try:
                self.reconnect_service.trigger_immediate_check()
            except AttributeError:
                self.reconnect_service._current_interval = 1.0

    def get_stats(self) -> Dict:
        """获取事件统计"""
        return {
            "event_stats": {k.name: v for k, v in self.event_stats.items()},
            "total_events": sum(self.event_stats.values())
        }
