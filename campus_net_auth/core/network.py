"""
网络服务模块
心跳保持和断线重连服务
"""

import logging
import threading
import time
from typing import Callable, Optional

import requests

from .constants import Constants
from ..utils.network_info import NetworkInfo


class HeartbeatService:
    """心跳保持服务"""

    def __init__(
        self,
        interval: int = None,
        url: str = None,
        timeout: int = None,
        on_success: Optional[Callable[[], None]] = None,
        on_failure: Optional[Callable[[Exception], None]] = None
    ):
        """
        初始化心跳服务

        Args:
            interval: 心跳间隔（秒）
            url: 心跳 URL
            timeout: 请求超时时间
            on_success: 成功回调
            on_failure: 失败回调
        """
        self.logger = logging.getLogger(__name__)
        self.interval = interval or Constants.DEFAULT_HEARTBEAT_INTERVAL
        self.url = url or Constants.DEFAULT_HEARTBEAT_URL
        self.timeout = timeout or Constants.DEFAULT_TIMEOUT

        self.on_success = on_success
        self.on_failure = on_failure

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

        # 统计信息
        self.success_count = 0
        self.failure_count = 0
        self.last_success_time: Optional[float] = None

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """启动心跳服务"""
        if self.is_running:
            self.logger.warning("心跳服务已在运行")
            return

        self._stop_event.clear()
        self._is_running = True

        self._thread = threading.Thread(
            target=self._worker,
            name="HeartbeatThread",
            daemon=True
        )
        self._thread.start()
        self.logger.info(f"心跳服务已启动，间隔: {self.interval}秒")

    def stop(self, timeout: float = 5.0) -> bool:
        """
        停止心跳服务

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
                self.logger.info("心跳服务已停止")
            else:
                self.logger.warning("心跳服务停止超时")
            return stopped

        return True

    def _worker(self) -> None:
        """心跳工作线程"""
        # 禁用代理，避免因代理IP不一致导致封禁
        no_proxy = {"http": None, "https": None}
        
        while not self._stop_event.is_set():
            try:
                response = requests.get(self.url, timeout=self.timeout, proxies=no_proxy)
                if response.status_code in [200, 204]:
                    self.success_count += 1
                    self.last_success_time = time.time()
                    self.logger.debug("心跳成功")
                    if self.on_success:
                        self.on_success()
                else:
                    self.failure_count += 1
                    self.logger.debug(f"心跳响应异常: {response.status_code}")

            except Exception as e:
                self.failure_count += 1
                self.logger.debug(f"心跳失败: {e}")
                if self.on_failure:
                    self.on_failure(e)

            # 等待下一次心跳
            self._stop_event.wait(self.interval)

    def update_config(self, interval: int = None, url: str = None, timeout: int = None) -> None:
        """更新配置"""
        if interval is not None:
            self.interval = interval
        if url is not None:
            self.url = url
        if timeout is not None:
            self.timeout = timeout


class ReconnectService:
    """断线重连服务"""

    def __init__(
        self,
        check_interval: int = None,
        cooldown: int = None,
        network_checker: Optional[Callable[[], bool]] = None,
        login_func: Optional[Callable[[], tuple]] = None,
        on_reconnect_success: Optional[Callable[[], None]] = None,
        on_reconnect_failure: Optional[Callable[[str], None]] = None
    ):
        """
        初始化重连服务

        Args:
            check_interval: 检测间隔（秒）
            cooldown: 重连冷却时间（秒）
            network_checker: 网络检测函数
            login_func: 登录函数
            on_reconnect_success: 重连成功回调
            on_reconnect_failure: 重连失败回调
        """
        self.logger = logging.getLogger(__name__)
        self.check_interval = check_interval or Constants.DEFAULT_RECONNECT_INTERVAL
        self.cooldown = cooldown or Constants.DEFAULT_RECONNECT_COOLDOWN

        self.network_checker = network_checker
        self.login_func = login_func
        self.on_reconnect_success = on_reconnect_success
        self.on_reconnect_failure = on_reconnect_failure

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._last_attempt_time: float = 0
        self._ban_end_time: float = 0  # 添加封禁结束时间
        self.enable_auto_retry_after_ban = True  # 是否启用封禁后自动重试
        self.default_ban_duration = 30 * 60  # 默认封禁时长（秒）
        
        # IP变化监测
        self._last_ip: str = ""  # 上次检测的IP地址
        self._ip_change_callback: Optional[Callable[[], None]] = None  # IP变化回调
        
        # 指数退避策略
        self._consecutive_failures: int = 0  # 连续失败次数
        self._current_backoff: float = 0  # 当前退避时间
        self._min_backoff: float = 1.0  # 最小退避时间（秒）
        self._max_backoff: float = 30.0  # 最大退避时间（秒）
        self._backoff_multiplier: float = 2.0  # 退避倍数
        
        # 动态检测间隔
        self._stable_count: int = 0  # 连续稳定检测次数
        self._current_interval: float = check_interval or Constants.DEFAULT_RECONNECT_INTERVAL
        self._min_interval: float = 10.0  # 最小检测间隔（秒）
        self._max_interval: float = 300.0  # 最大检测间隔（秒）
        self._interval_step: float = 30.0  # 每次增加的步长（秒）
        self._stable_threshold: int = 10  # 连续稳定多少次后增加间隔

        # 统计信息
        self.reconnect_count = 0
        self.success_count = 0
        self.failure_count = 0

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """启动重连服务"""
        if self.is_running:
            self.logger.warning("重连服务已在运行")
            return

        if not self.network_checker or not self.login_func:
            self.logger.error("重连服务缺少必要的回调函数")
            return

        self._stop_event.clear()
        self._is_running = True

        self._thread = threading.Thread(
            target=self._worker,
            name="ReconnectThread",
            daemon=True
        )
        self._thread.start()
        self.logger.info(f"重连服务已启动，检测间隔: {self.check_interval}秒，冷却时间: {self.cooldown}秒")

    def stop(self, timeout: float = 5.0) -> bool:
        """
        停止重连服务

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
                self.logger.info("重连服务已停止")
            else:
                self.logger.warning("重连服务停止超时")
            return stopped

        return True

    def _worker(self) -> None:
        """重连工作线程"""
        while not self._stop_event.is_set():
            try:
                current_time = time.time()
                
                # 检测IP变化
                current_ip = NetworkInfo.get_ip_address()
                if self._last_ip and current_ip != self._last_ip:
                    self.logger.warning(f"检测到IP变化: {self._last_ip} -> {current_ip}")
                    # IP变化，触发重新认证
                    if self._ip_change_callback:
                        self._ip_change_callback()
                    else:
                        # 直接尝试登录
                        if self.login_func:
                            self.logger.info("IP变化，尝试重新认证")
                            self.reconnect_count += 1
                            success, message = self.login_func()
                            if success:
                                self.success_count += 1
                                self.logger.info(f"IP变化后重新认证成功: {message}")
                                if self.on_reconnect_success:
                                    self.on_reconnect_success()
                            else:
                                self.failure_count += 1
                                self.logger.error(f"IP变化后重新认证失败: {message}")
                self._last_ip = current_ip
                
                # 检查是否处于封禁期间
                if current_time < self._ban_end_time:
                    remaining_time = self._ban_end_time - current_time
                    self.logger.debug(f"账号仍在封禁期，剩余时间: {int(remaining_time)}秒")
                    # 等待较短的时间或者直到封禁结束
                    wait_time = min(self.check_interval, remaining_time)
                    self._stop_event.wait(wait_time)
                    continue

                # 检测网络状态
                if not self.network_checker():
                    self.logger.warning("检测到网络断开")
                    
                    # 网络异常时缩短检测间隔
                    self._adjust_interval_on_failure()

                    # 使用指数退避计算实际冷却时间
                    effective_cooldown = max(self.cooldown, self._current_backoff)
                    
                    # 检查冷却时间
                    if current_time - self._last_attempt_time >= effective_cooldown:
                        self._last_attempt_time = current_time
                        self.reconnect_count += 1

                        self.logger.info(f"尝试重连（第 {self.reconnect_count} 次）")

                        try:
                            success, message = self.login_func()
                            if success:
                                # 重置封禁状态和退避计数器
                                self._ban_end_time = 0
                                self._reset_backoff()
                                self.success_count += 1
                                self.logger.info(f"重连成功: {message}")
                                if self.on_reconnect_success:
                                    self.on_reconnect_success()
                            else:
                                self.failure_count += 1
                                self.logger.error(f"重连失败: {message}")
                                
                                # 增加退避时间
                                self._increment_backoff()
                                
                                # 检查是否是封禁消息
                                if self.enable_auto_retry_after_ban and ("封禁" in message or "禁止登录" in message):
                                    # 提取封禁时长，默认使用配置的时长
                                    ban_duration = self.default_ban_duration
                                    if "分钟" in message:
                                        import re
                                        match = re.search(r'(\d+)分钟', message)
                                        if match:
                                            ban_duration = int(match.group(1)) * 60
                                    
                                    self._ban_end_time = current_time + ban_duration
                                    self.reconnect_count = 0  # 重置重连计数器
                                    self.logger.info(f"检测到账号封禁，将在 {ban_duration} 秒后自动重试")
                                
                                if self.on_reconnect_failure:
                                    self.on_reconnect_failure(message)
                        except Exception as e:
                            self.failure_count += 1
                            self._increment_backoff()
                            self.logger.error(f"重连异常: {e}")
                            if self.on_reconnect_failure:
                                self.on_reconnect_failure(str(e))
                    else:
                        remaining = effective_cooldown - (current_time - self._last_attempt_time)
                        self.logger.debug(f"冷却中，剩余 {remaining:.1f} 秒（退避: {self._current_backoff:.1f}s）")
                else:
                    # 网络正常，增加稳定性计数并调整间隔
                    self._adjust_interval_on_stable()

            except Exception as e:
                self.logger.error(f"重连服务异常: {e}")

            # 等待下一次检测（使用动态间隔）
            self._stop_event.wait(self._current_interval)

    def update_config(self, check_interval: int = None, cooldown: int = None) -> None:
        """更新配置"""
        if check_interval is not None:
            self.check_interval = check_interval
        if cooldown is not None:
            self.cooldown = cooldown
            
    def set_ban_config(self, enable_auto_retry: bool, default_ban_duration_minutes: int) -> None:
        """设置封禁相关配置"""
        self.enable_auto_retry_after_ban = enable_auto_retry
        self.default_ban_duration = default_ban_duration_minutes * 60  # 转换为秒

    def set_backoff_config(self, enable: bool, min_backoff: float, max_backoff: float) -> None:
        """
        设置指数退避配置
        
        Args:
            enable: 是否启用指数退避
            min_backoff: 最小退避时间（秒）
            max_backoff: 最大退避时间（秒）
        """
        if enable:
            self._min_backoff = min_backoff
            self._max_backoff = max_backoff
        else:
            # 禁用指数退避，使用固定冷却时间
            self._min_backoff = self.cooldown
            self._max_backoff = self.cooldown
            self._current_backoff = self.cooldown

    def set_ip_change_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """设置IP变化回调函数"""
        self._ip_change_callback = callback

    def _calculate_backoff(self) -> float:
        """
        计算指数退避时间
        
        Returns:
            退避时间（秒）
        """
        if self._consecutive_failures == 0:
            return self._min_backoff
        
        # 指数退避：min_backoff * (multiplier ^ failures)
        backoff = self._min_backoff * (self._backoff_multiplier ** self._consecutive_failures)
        return min(backoff, self._max_backoff)

    def _reset_backoff(self) -> None:
        """重置退避计数器"""
        self._consecutive_failures = 0
        self._current_backoff = self._min_backoff

    def _increment_backoff(self) -> None:
        """增加退避时间"""
        self._consecutive_failures += 1
        self._current_backoff = self._calculate_backoff()
        self.logger.info(f"连续失败 {self._consecutive_failures} 次，退避时间: {self._current_backoff:.1f} 秒")

    def _adjust_interval_on_stable(self) -> None:
        """网络稳定时增加检测间隔"""
        self._stable_count += 1
        if self._stable_count >= self._stable_threshold:
            old_interval = self._current_interval
            self._current_interval = min(self._current_interval + self._interval_step, self._max_interval)
            if self._current_interval > old_interval:
                self.logger.info(f"网络稳定，检测间隔调整为: {self._current_interval:.0f} 秒")
            self._stable_count = 0

    def _adjust_interval_on_failure(self) -> None:
        """网络异常时缩短检测间隔"""
        self._stable_count = 0
        old_interval = self._current_interval
        self._current_interval = max(self.check_interval, self._min_interval)
        if self._current_interval < old_interval:
            self.logger.info(f"网络异常，检测间隔缩短为: {self._current_interval:.0f} 秒")

    def get_time_until_next_attempt(self) -> float:
        """获取距离下次重连尝试的时间"""
        if self._last_attempt_time == 0:
            return 0
        elapsed = time.time() - self._last_attempt_time
        remaining = self.cooldown - elapsed
        return max(0, remaining)


class WatchdogService:
    """看门狗服务，监控并自动重启异常退出的服务"""

    def __init__(
        self,
        services: list,
        check_interval: int = 60,
        on_service_restart: Optional[Callable[[str], None]] = None
    ):
        """
        初始化看门狗服务

        Args:
            services: 要监控的服务列表，每个元素为 (service_name, service_instance)
            check_interval: 检查间隔（秒）
            on_service_restart: 服务重启回调
        """
        self.logger = logging.getLogger(__name__)
        self.services = services  # [(name, service), ...]
        self.check_interval = check_interval
        self.on_service_restart = on_service_restart

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        
        # 统计信息
        self.restart_count = 0

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """启动看门狗服务"""
        if self.is_running:
            self.logger.warning("看门狗服务已在运行")
            return

        self._stop_event.clear()
        self._is_running = True

        self._thread = threading.Thread(
            target=self._worker,
            name="WatchdogThread",
            daemon=True
        )
        self._thread.start()
        self.logger.info(f"看门狗服务已启动，监控 {len(self.services)} 个服务")

    def stop(self, timeout: float = 5.0) -> bool:
        """停止看门狗服务"""
        if not self._is_running:
            return True

        self._stop_event.set()
        self._is_running = False

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            stopped = not self._thread.is_alive()
            if stopped:
                self.logger.info("看门狗服务已停止")
            else:
                self.logger.warning("看门狗服务停止超时")
            return stopped

        return True

    def _worker(self) -> None:
        """看门狗工作线程"""
        while not self._stop_event.is_set():
            try:
                for service_name, service in self.services:
                    # 检查服务是否存活
                    if hasattr(service, 'is_running') and not service.is_running:
                        self.logger.warning(f"服务 {service_name} 已停止，尝试重启")
                        
                        # 尝试重启服务
                        try:
                            if hasattr(service, 'start'):
                                service.start()
                                self.restart_count += 1
                                self.logger.info(f"服务 {service_name} 已重启")
                                
                                if self.on_service_restart:
                                    self.on_service_restart(service_name)
                        except Exception as e:
                            self.logger.error(f"重启服务 {service_name} 失败: {e}")

            except Exception as e:
                self.logger.error(f"看门狗服务异常: {e}")

            # 等待下一次检查
            self._stop_event.wait(self.check_interval)
