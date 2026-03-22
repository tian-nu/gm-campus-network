"""
网络变化监听器
监听网卡切换、IP变化、系统休眠/唤醒等网络相关事件
"""

import logging
import threading
import time
import socket
import subprocess
from typing import Callable, Optional, List, Dict, Set
from dataclasses import dataclass, field
from enum import Enum, auto


class NetworkEventType(Enum):
    """网络事件类型"""
    IP_CHANGED = auto()           # IP地址变化
    ADAPTER_CHANGED = auto()      # 网卡变化（有线/无线切换）
    CONNECTION_UP = auto()        # 网络连接建立
    CONNECTION_DOWN = auto()      # 网络连接断开
    SYSTEM_RESUME = auto()        # 系统从休眠/睡眠唤醒
    SYSTEM_SUSPEND = auto()       # 系统进入休眠/睡眠
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
    监听网卡切换、IP变化、系统休眠/唤醒等事件
    """

    def __init__(
        self,
        on_event: Optional[Callable[[NetworkEvent], None]] = None,
        check_interval: float = 2.0
    ):
        """
        初始化网络监听器

        Args:
            on_event: 网络事件回调函数
            check_interval: 检测间隔（秒）
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
        self._last_resume_time: float = 0

        # 系统电源状态
        self._last_power_status: str = ""
        self._power_check_interval: float = 5.0  # 电源状态检测间隔较长

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
        self._last_resume_time = time.time()
        self._last_power_status = self._get_power_status()

        self.logger.debug(f"初始化状态 - IP: {self._last_ip}, 网卡: {self._last_adapter}, "
                         f"网关: {self._last_gateway}, 连接: {self._was_connected}")

    def _worker(self) -> None:
        """监听工作线程"""
        power_check_counter = 0

        while not self._stop_event.is_set():
            try:
                # 检测IP变化
                self._check_ip_change()

                # 检测网卡变化
                self._check_adapter_change()

                # 检测网关变化
                self._check_gateway_change()

                # 检测连接状态变化
                self._check_connection_change()

                # 检测系统电源状态（间隔较长）
                power_check_counter += 1
                if power_check_counter >= int(self._power_check_interval / self.check_interval):
                    power_check_counter = 0
                    self._check_power_status()

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

            # 判断是有线/无线切换
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

    def _check_power_status(self) -> None:
        """检测系统电源状态（休眠/唤醒）"""
        current_status = self._get_power_status()

        if current_status != self._last_power_status:
            # 检测从休眠/睡眠唤醒
            if self._last_power_status in ["suspend", "hibernate"] and current_status == "active":
                time_since_last = time.time() - self._last_resume_time

                # 只有当唤醒间隔超过10秒才认为是真正的唤醒事件（避免误触发）
                if time_since_last > 10:
                    self.logger.info("系统从休眠/睡眠唤醒")

                    event = NetworkEvent(
                        event_type=NetworkEventType.SYSTEM_RESUME,
                        old_value=self._last_power_status,
                        new_value=current_status,
                        details={"resume_time": time.time()}
                    )
                    self._emit_event(event)
                    self._last_resume_time = time.time()

            # 检测进入休眠/睡眠
            elif current_status in ["suspend", "hibernate"] and self._last_power_status == "active":
                self.logger.info(f"系统进入{current_status}状态")

                event = NetworkEvent(
                    event_type=NetworkEventType.SYSTEM_SUSPEND,
                    old_value=self._last_power_status,
                    new_value=current_status
                )
                self._emit_event(event)

            self._last_power_status = current_status

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
            # 通过路由表找到默认网关对应的网卡
            result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True,
                text=True,
                timeout=5
            )

            lines = result.stdout.split('\n')
            for line in lines:
                if '0.0.0.0' in line and 'Gateway' not in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        # 最后一列通常是网卡名称或索引
                        adapter = parts[-1]
                        return adapter

        except Exception as e:
            self.logger.debug(f"获取主网卡失败: {e}")

        return ""

    def _get_all_adapters(self) -> Set[str]:
        """获取所有网卡"""
        adapters = set()

        try:
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=5
            )

            lines = result.stdout.split('\n')
            for line in lines:
                # 匹配网卡名称行
                if '适配器' in line or 'Adapter' in line:
                    # 提取网卡名称
                    if ':' in line:
                        adapter_name = line.split(':')[0].strip()
                        # 移除"以太网适配器 "、"无线局域网适配器 "等前缀
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
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=5
            )

            lines = result.stdout.split('\n')
            for i, line in enumerate(lines):
                if '默认网关' in line or 'Default Gateway' in line:
                    # 提取网关IP
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
                s.settimeout(3)
                s.connect(("114.114.114.114", 53))
                return True
        except Exception:
            pass

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
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

        # 无线网卡关键词
        wireless_keywords = ['wi-fi', 'wifi', 'wireless', 'wlan', '无线']
        for keyword in wireless_keywords:
            if keyword in adapter_lower:
                return "wireless"

        # 有线网卡关键词
        wired_keywords = ['ethernet', 'eth', '有线', '以太网']
        for keyword in wired_keywords:
            if keyword in adapter_lower:
                return "wired"

        return "unknown"

    def _get_power_status(self) -> str:
        """
        获取系统电源状态

        Returns:
            "active" - 正常运行
            "suspend" - 睡眠状态
            "hibernate" - 休眠状态
            "unknown" - 未知
        """
        try:
            # Windows平台使用powercfg检测
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                result = subprocess.run(
                    ["powercfg", "/requests"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                result = subprocess.run(
                    ["powercfg", "/requests"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )

            # 如果能正常执行命令，说明系统处于活动状态
            return "active"

        except Exception as e:
            self.logger.debug(f"检测电源状态失败: {e}")

        # 备用方案：通过时间差判断
        # 如果两次检测间隔异常大，可能刚唤醒
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
        self._reconnect_cooldown: float = 5.0  # 5秒内不重复触发

        # 事件统计
        self.event_stats: Dict[NetworkEventType, int] = {}

    def handle_event(self, event: NetworkEvent) -> None:
        """
        处理网络事件

        Args:
            event: 网络事件
        """
        # 更新统计
        self.event_stats[event.event_type] = self.event_stats.get(event.event_type, 0) + 1

        self.logger.info(f"处理网络事件: {event.event_type.name}")

        # 根据事件类型处理
        if event.event_type == NetworkEventType.IP_CHANGED:
            self._handle_ip_changed(event)

        elif event.event_type == NetworkEventType.ADAPTER_CHANGED:
            self._handle_adapter_changed(event)

        elif event.event_type == NetworkEventType.CONNECTION_UP:
            self._handle_connection_up(event)

        elif event.event_type == NetworkEventType.SYSTEM_RESUME:
            self._handle_system_resume(event)

        elif event.event_type == NetworkEventType.GATEWAY_CHANGED:
            self._handle_gateway_changed(event)

    def _handle_ip_changed(self, event: NetworkEvent) -> None:
        """处理IP变化事件"""
        self.logger.info(f"IP变化处理: {event.old_value} -> {event.new_value}")

        # IP变化通常意味着网络环境变化，需要重新认证
        if event.new_value and event.new_value != event.old_value:
            self._trigger_reconnect("IP地址变化")

    def _handle_adapter_changed(self, event: NetworkEvent) -> None:
        """处理网卡变化事件"""
        old_type = event.details.get("old_type", "unknown")
        new_type = event.details.get("new_type", "unknown")

        self.logger.info(f"网卡切换: {old_type} -> {new_type}")

        # 有线/无线切换，需要重新认证
        if old_type != new_type:
            type_names = {"wired": "有线", "wireless": "无线", "unknown": "未知"}
            old_name = type_names.get(old_type, old_type)
            new_name = type_names.get(new_type, new_type)
            self._trigger_reconnect(f"网络切换: {old_name} -> {new_name}")

    def _handle_connection_up(self, event: NetworkEvent) -> None:
        """处理网络连接建立事件"""
        self.logger.info("网络连接已建立，检查是否需要认证")
        self._trigger_reconnect("网络连接建立")

    def _handle_system_resume(self, event: NetworkEvent) -> None:
        """处理系统唤醒事件"""
        self.logger.info("系统唤醒，检查网络状态")

        # 系统唤醒后通常需要重新认证
        self._trigger_reconnect("系统从休眠唤醒")

    def _handle_gateway_changed(self, event: NetworkEvent) -> None:
        """处理网关变化事件"""
        self.logger.info(f"网关变化: {event.old_value} -> {event.new_value}")
        self._trigger_reconnect("网关变化")

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

        # 调用回调
        if self.on_reconnect_required:
            try:
                self.on_reconnect_required()
            except Exception as e:
                self.logger.error(f"重新连接回调异常: {e}")

        # 或者通过重连服务触发
        elif self.reconnect_service:
            try:
                # 重置重连服务的间隔，立即检测
                self.reconnect_service._current_interval = 1.0
            except Exception as e:
                self.logger.error(f"重置重连间隔失败: {e}")

    def get_stats(self) -> Dict:
        """获取事件统计"""
        return {
            "event_stats": {k.name: v for k, v in self.event_stats.items()},
            "total_events": sum(self.event_stats.values())
        }
