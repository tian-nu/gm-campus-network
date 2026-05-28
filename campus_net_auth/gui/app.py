"""
主应用程序
整合所有 GUI 组件
"""

import logging
import sys
import threading
from tkinter import *
from tkinter import ttk
from typing import Optional

from ..core.authenticator import CampusNetAuthenticator
from ..core.network import HeartbeatService, ReconnectService, WatchdogService
from ..core.constants import Constants
from ..config.manager import ConfigManager
from ..utils.logger import setup_logging, add_gui_handler, remove_handler
from ..utils.network_info import NetworkInfo
from ..utils.power_monitor import PowerMonitor
from ..utils.network_monitor import NetworkMonitor, NetworkEventHandler, NetworkEventType

from .tabs.login import LoginTab
from .tabs.settings import SettingsTab
from .tabs.logs import LogsTab
from .tray import SystemTray


class CampusNetApp:
    """校园网认证主应用"""

    def __init__(self, root: Tk):
        """
        初始化应用

        Args:
            root: Tkinter 根窗口
        """
        self.root = root
        self.root.title(Constants.WINDOW_TITLE)
        self.root.geometry(Constants.WINDOW_SIZE)
        self.root.minsize(*Constants.MIN_WINDOW_SIZE)

        # Windows 性能优化
        self._optimize_windows_performance()

        # 初始化组件
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()

        # 配置日志
        self.logger = setup_logging(
            debug_mode=self.config.get("debug_mode", False),
            log_file=Constants.LOG_FILE
        )

        # 初始化认证器
        self.authenticator = CampusNetAuthenticator(self.config)

        # 初始化网络服务
        self.heartbeat_service: Optional[HeartbeatService] = None
        self.reconnect_service: Optional[ReconnectService] = None
        self.watchdog_service: Optional[WatchdogService] = None

        # 电源和网络监听器
        self.power_monitor: Optional[PowerMonitor] = None
        self.network_monitor: Optional[NetworkMonitor] = None
        self.network_event_handler: Optional[NetworkEventHandler] = None

        # 初始化托盘
        self.tray = SystemTray(
            on_show=self._restore_window,
            on_quit=self._on_quit
        )
        self.in_tray = False

        # GUI 日志处理器
        self.gui_log_handler = None

        # 创建 GUI
        self._create_widgets()

        # 加载配置到 UI
        self._load_config_to_ui()

        # 添加 GUI 日志处理器
        self.gui_log_handler = add_gui_handler(self._on_log_message)

        # 自动清理日志
        if self.config.get("auto_clean_log"):
            self.config_manager.clean_old_logs(
                Constants.LOG_FILE,
                self.config.get("log_retention_days", 7)
            )

        # 启动时最小化
        if self.config.get("minimize_startup"):
            self.root.after(100, self._minimize_to_tray)

        # 自动登录
        if self.config.get("auto_login") and self.config.get("username") and self.config.get("password"):
            self.root.after(2000, self._auto_login)

        # 绑定窗口大小变化事件(防抖优化) - 必须在_schedule_status_update之前初始化
        self._resize_debounce_timer = None
        self._RESIZE_DEBOUNCE_MS = 500  # 增加防抖时间以进一步减少resize时的更新
        self.root.bind("<Configure>", self._on_window_configure)

        # 定期更新状态（延长间隔减少资源消耗）
        self._schedule_status_update()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.logger.info("校园网认证工具启动完成")

    def _optimize_windows_performance(self) -> None:
        """Windows 平台性能优化"""
        if sys.platform != "win32":
            return

        try:
            # 禁用 ttk 主题动画，使用更轻量的主题
            style = ttk.Style()
            style.theme_use("clam")
            # 禁用动画效果以提升性能
            style.configure(".", animation=False)
        except Exception:
            pass

    def _on_window_configure(self, event) -> None:
        """
        窗口大小变化事件处理(带防抖)

        Args:
            event: Configure 事件对象
        """
        # 只处理根窗口的Configure事件(忽略子控件的事件)
        if event.widget != self.root:
            return

        # 取消之前的定时器
        if self._resize_debounce_timer:
            self.root.after_cancel(self._resize_debounce_timer)

        # 设置新的定时器 - 使用更长的防抖时间(500ms)
        self._resize_debounce_timer = self.root.after(
            self._RESIZE_DEBOUNCE_MS,
            self._on_resize_finished
        )

    def _on_resize_finished(self) -> None:
        """窗口调整完成后的处理"""
        self._resize_debounce_timer = None
        # 延迟更新状态,避免resize时频繁更新
        self.root.after(100, self._check_status_async)

    def _create_widgets(self) -> None:
        """创建 GUI 控件"""
        # 创建标签页容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 登录标签页
        self.login_tab = LoginTab(
            self.notebook,
            on_login=self._on_login,
            on_minimize=self._minimize_to_tray
        )
        self.notebook.add(self.login_tab, text="登录")

        # 设置标签页
        self.settings_tab = SettingsTab(
            self.notebook,
            on_save=self._on_save_settings,
            on_reset=self._on_reset_settings
        )
        self.notebook.add(self.settings_tab, text="设置")

        # 日志标签页
        self.logs_tab = LogsTab(self.notebook, log_file=Constants.LOG_FILE)
        self.notebook.add(self.logs_tab, text="日志")

    def _load_config_to_ui(self) -> None:
        """加载配置到 UI"""
        # 登录凭证
        self.login_tab.set_credentials(
            self.config.get("username", ""),
            self.config.get("password", "")
        )

        # 网络信息 - 先显示占位值，后台获取以避免启动白屏
        self.login_tab.update_network_info("获取中...", "获取中...")

        def _fetch_network_info() -> None:
            try:
                network_info = NetworkInfo.get_network_info(self.config)
                # 同时获取网络名称
                net_names = NetworkInfo.get_connected_network_names()
                self.root.after(0, lambda: (
                    self.login_tab.update_network_info(
                        network_info["ip"], network_info["mac"]
                    ),
                    self.login_tab.update_network_name(net_names)
                ))
            except Exception:
                self.root.after(0, lambda: (
                    self.login_tab.update_network_info("未知", "未知"),
                    self.login_tab.update_network_name(set())
                ))

        threading.Thread(target=_fetch_network_info, daemon=True).start()

        # 代理检测设置
        self.login_tab.check_proxy_before_login = self.config.get("check_proxy_before_login", True)

        # 同步开机自启状态（从注册表读取实际状态）
        actual_startup = self.config_manager.is_startup_enabled()
        self.config["startup"] = actual_startup

        # 设置
        self.settings_tab.set_config(self.config)

    def _on_login(self, username: str, password: str) -> None:
        """登录回调"""
        success, message = self.authenticator.login(username, password)

        # 在主线程更新 UI
        self.root.after(0, lambda: self._on_login_finished(success, message))

    def _on_login_finished(self, success: bool, message: str) -> None:
        """登录完成"""
        self.login_tab.on_login_finished(success, message)

        # 托盘状态（无论是否处于托盘模式都更新，保证后续显示时颜色正确）
        if success:
            self.tray.update_status(SystemTray.STATUS_ONLINE)
        else:
            self.tray.update_status(SystemTray.STATUS_OFFLINE)

        # 托盘弹窗通知（仅在托盘模式下发送）
        silent_mode = self.config.get("silent_mode", True)
        if self.in_tray:
            if success:
                if not silent_mode and self.config.get("login_success_notify", True):
                    self.tray.show_notification("登录成功", message)
            else:
                if self.config.get("login_fail_notify", True):
                    self.tray.show_notification("登录失败", message)

        if success:
            # 保存凭证
            if self.config.get("remember_password"):
                username, password = self.login_tab.get_credentials()
                self.config["username"] = username
                self.config["password"] = password
                self.config_manager.save(self.config)

            # 启动服务
            self._start_services()

    def _start_services(self) -> None:
        """启动后台服务"""
        # 心跳服务
        if self.config.get("enable_heartbeat"):
            if self.heartbeat_service is None:
                self.heartbeat_service = HeartbeatService(
                    interval=self.config.get("heartbeat_interval", 120),
                    url=self.config.get("heartbeat_url", Constants.DEFAULT_HEARTBEAT_URL),
                    timeout=self.config.get("timeout", 10)
                )
            self.heartbeat_service.start()

        # 重连服务
        if self.config.get("enable_reconnect"):
            if self.reconnect_service is None:
                # 构建白名单检查函数
                def _whitelist_check() -> bool:
                    if not self.config.get("enable_network_whitelist", True):
                        return True
                    whitelist_str = self.config.get("network_name_whitelist", "")
                    whitelist = [w.strip() for w in whitelist_str.split(",") if w.strip()]
                    return NetworkInfo.is_network_whitelisted(whitelist)

                self.reconnect_service = ReconnectService(
                    check_interval=self.config.get("reconnect_interval", 30),
                    cooldown=self.config.get("reconnect_cooldown", 30),
                    network_checker=self.authenticator.detect_network_status,
                    login_func=lambda: self.authenticator.login(
                        self.authenticator.username or "",
                        self.authenticator.password or "",
                        force=True  # 重连服务已检测断网，跳过 login 内二次检测
                    ),
                    on_reconnect_success=self._on_reconnect_success,
                    on_reconnect_failure=self._on_reconnect_failure,
                    network_whitelist_checker=_whitelist_check
                )
                # 设置封禁相关配置
                self.reconnect_service.set_ban_config(
                    self.config.get("enable_auto_retry_after_ban", True),
                    self.config.get("default_ban_duration", 30)
                )
                # 设置指数退避配置
                self.reconnect_service.set_backoff_config(
                    self.config.get("enable_exponential_backoff", True),
                    self.config.get("min_backoff_seconds", 1),
                    self.config.get("max_backoff_seconds", 30)
                )
            self.reconnect_service.start()
            
            # 启动看门狗服务
            if self.watchdog_service is None:
                monitored_services = []
                if self.heartbeat_service:
                    monitored_services.append(("心跳服务", self.heartbeat_service))
                if self.reconnect_service:
                    monitored_services.append(("重连服务", self.reconnect_service))
                
                if monitored_services:
                    self.watchdog_service = WatchdogService(
                        services=monitored_services,
                        check_interval=60,
                        on_service_restart=self._on_service_restart
                    )
                    self.watchdog_service.start()

        # 启动电源事件监听（睡眠/唤醒）
        if self.power_monitor is None:
            self.power_monitor = PowerMonitor(
                self.root,
                on_resume=self._on_system_resume,
                on_suspend=self._on_system_suspend,
            )
        self.power_monitor.start()

        # 启动网络变化监听（IP/网卡/网关变化）
        if self.network_monitor is None:
            self.network_event_handler = NetworkEventHandler(
                authenticator=self.authenticator,
                reconnect_service=self.reconnect_service,
                on_reconnect_required=self._on_reconnect_required,
            )
            self.network_monitor = NetworkMonitor(
                on_event=self.network_event_handler.handle_event,
                check_interval=10.0,
            )
        else:
            # 更新 handler 的 reconnect_service 引用
            if self.network_event_handler:
                self.network_event_handler.reconnect_service = self.reconnect_service
        self.network_monitor.start()

    def _stop_services(self, timeout: float = 5.0) -> None:
        """
        停止后台服务

        Args:
            timeout: 等待线程退出的超时时间（秒）。设置为 0 则不等待，避免阻塞 UI。
        """
        if self.power_monitor:
            self.power_monitor.stop()
        if self.network_monitor:
            self.network_monitor.stop(timeout=timeout)
        if self.watchdog_service:
            self.watchdog_service.stop(timeout=timeout)
        if self.heartbeat_service:
            self.heartbeat_service.stop(timeout=timeout)
        if self.reconnect_service:
            self.reconnect_service.stop(timeout=timeout)

    def _on_service_restart(self, service_name: str) -> None:
        """服务重启回调"""
        self.logger.info(f"看门狗自动重启服务: {service_name}")
        if self.in_tray:
            self.tray.show_notification("服务重启", f"{service_name}已自动重启")

    def _on_reconnect_success(self) -> None:
        """重连成功回调"""
        self.logger.info("断线重连成功")
        # 更新托盘状态
        self.tray.update_status(SystemTray.STATUS_ONLINE)
        if self.in_tray and not self.config.get("silent_mode", False):
            self.tray.show_notification("重连成功", "网络已恢复连接")

    def _on_reconnect_failure(self, message: str) -> None:
        """重连失败回调"""
        self.logger.error(f"断线重连失败: {message}")
        # 更新托盘状态
        self.tray.update_status(SystemTray.STATUS_RECONNECTING)

    def _on_system_resume(self) -> None:
        """系统唤醒回调 — 由 PowerMonitor 的 WM_POWERBROADCAST 触发"""
        self.logger.info("系统从睡眠/休眠唤醒，延迟5秒后尝试重连")
        # 延迟 5 秒等待网络栈就绪
        self.root.after(5000, self._do_reconnect_after_resume)

    def _on_system_suspend(self) -> None:
        """系统睡眠回调"""
        self.logger.info("系统进入睡眠/休眠")

    def _do_reconnect_after_resume(self) -> None:
        """唤醒后执行重连"""
        if not self.authenticator.username or not self.authenticator.password:
            self.logger.debug("唤醒后无凭证，跳过重连")
            return

        if self.reconnect_service:
            # 让重连服务立即检测并重连
            self.reconnect_service.trigger_immediate_check()
            self.logger.info("已触发重连服务立即检测")
        else:
            # 没有重连服务则直接登录
            success, message = self.authenticator.login(
                self.authenticator.username,
                self.authenticator.password,
                force=True,
            )
            self.root.after(0, lambda: self._on_login_finished(success, message))

    def _on_reconnect_required(self) -> None:
        """网络变化事件触发重连 — 由 NetworkEventHandler 调用"""
        if self.reconnect_service:
            self.reconnect_service.trigger_immediate_check()
            self.logger.info("网络变化事件触发重连服务立即检测")

    def _on_save_settings(self, settings: dict) -> None:
        """保存设置回调"""
        # 合并设置
        username, password = self.login_tab.get_credentials()
        settings["username"] = username
        settings["password"] = password if settings.get("remember_password") else ""
        settings["mac_address"] = self.config.get("mac_address", "")

        # 处理开机自启
        old_startup = self.config.get("startup", False)
        new_startup = settings.get("startup", False)
        if old_startup != new_startup:
            self.config_manager.set_startup(new_startup)

        # 保存
        self.config_manager.save(settings)
        self.config = settings

        # 更新认证器配置
        self.authenticator.update_config(settings)
        
        # 更新登录页的代理检测设置
        self.login_tab.check_proxy_before_login = settings.get("check_proxy_before_login", True)
        
        # 更新重连服务的封禁配置
        if self.reconnect_service:
            self.reconnect_service.set_ban_config(
                settings.get("enable_auto_retry_after_ban", True),
                settings.get("default_ban_duration", 30)
            )
            # 更新指数退避配置
            self.reconnect_service.set_backoff_config(
                settings.get("enable_exponential_backoff", True),
                settings.get("min_backoff_seconds", 1),
                settings.get("max_backoff_seconds", 30)
            )

        # 重新配置日志
        setup_logging(settings.get("debug_mode", False), Constants.LOG_FILE)

        # 重启服务（不等待线程退出，避免阻塞 UI）
        self._stop_services(timeout=0.0)
        # 清空引用，确保用新配置重新创建
        self.heartbeat_service = None
        self.reconnect_service = None
        self.watchdog_service = None
        self.power_monitor = None
        self.network_monitor = None
        self.network_event_handler = None
        if self.authenticator.is_logged_in:
            self._start_services()

        self.logger.info("设置已保存")

    def _on_reset_settings(self) -> None:
        """重置设置回调"""
        self.config = self.config_manager.reset()
        self.settings_tab.set_config(self.config)
        self.logger.info("设置已重置")

    def _on_log_message(self, message: str) -> None:
        """日志消息回调（线程安全，由 LogsTab 内部防抖）"""
        # append_log 内部使用 after() 保证线程安全
        self.logs_tab.append_log(message)

    def _minimize_to_tray(self) -> None:
        """最小化到托盘"""
        if self.tray.is_available:
            self.root.withdraw()
            self.tray.start()
            self.in_tray = True
            self.logger.info("已最小化到系统托盘")
        else:
            self.root.iconify()
            self.logger.info("已最小化到任务栏")

    def _restore_window(self) -> None:
        """恢复窗口"""
        self.tray.stop()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.in_tray = False
        self.logger.info("已恢复窗口")

    def _schedule_status_update(self) -> None:
        """调度状态更新（仅当窗口可见且不在resize时更新）"""
        # 如果正在resize，跳过本次更新
        if self._resize_debounce_timer is not None:
            self.root.after(10000, self._schedule_status_update)
            return

        # 只有窗口可见时才更新
        if self.root.winfo_viewable():
            self._check_status_async()

        # 每10秒检查一次（延长间隔减少资源消耗）
        self.root.after(10000, self._schedule_status_update)

    def _check_status_async(self) -> None:
        """异步检查状态"""
        def check():
            try:
                network_ok = self.authenticator.detect_network_status()
                login_ok = self.authenticator.is_logged_in
                self.root.after(0, lambda: self._update_status_ui(network_ok, login_ok))
            except Exception:
                pass  # 静默失败，避免日志刷屏

        threading.Thread(target=check, daemon=True).start()

    def _update_status_ui(self, network_ok: bool, login_ok: bool) -> None:
        """更新状态 UI"""
        self.login_tab.update_network_status(network_ok)
        self.login_tab.update_login_status(login_ok)
        
        # 更新托盘状态（始终更新内部状态，托盘显示时自动正确）
        if network_ok and login_ok:
            self.tray.update_status(SystemTray.STATUS_ONLINE)
        elif not network_ok:
            self.tray.update_status(SystemTray.STATUS_OFFLINE)
        else:
            self.tray.update_status(SystemTray.STATUS_RECONNECTING)

    def _auto_login(self) -> None:
        """自动登录（白名单检查在后台线程，避免阻塞 UI）"""
        self.logger.info("准备自动登录")

        # 同步提取凭证和配置（tkinter 读取操作很快）
        username, password = self.login_tab.get_credentials()
        if not username or not password:
            return

        enable_whitelist = self.config.get("enable_network_whitelist", True)
        whitelist_str = self.config.get("network_name_whitelist", "")

        def _worker() -> None:
            # 后台线程：检查白名单 + 执行登录
            if enable_whitelist:
                whitelist = [w.strip() for w in whitelist_str.split(",") if w.strip()]
                if whitelist and not NetworkInfo.is_network_whitelisted(whitelist):
                    self.logger.info("自动登录跳过：当前网络不在白名单中")
                    return

            self.logger.info("执行自动登录")
            self._on_login(username, password)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_closing(self) -> None:
        """关闭窗口"""
        # 保存配置
        settings = self.settings_tab.get_config()
        username, password = self.login_tab.get_credentials()
        settings["username"] = username
        settings["password"] = password if settings.get("remember_password") else ""
        settings["mac_address"] = self.config.get("mac_address", "")
        self.config_manager.save(settings)

        # 停止服务（daemon 线程会被自动回收，仅给 1 秒缓冲）
        # 先停止电源监听器（需要在窗口销毁前恢复 WndProc）
        if self.power_monitor:
            self.power_monitor.stop()
        self._stop_services(timeout=1.0)

        # 停止托盘
        if self.in_tray:
            self.tray.stop()

        # 移除日志处理器
        if self.gui_log_handler:
            remove_handler(self.gui_log_handler)

        self.logger.info("程序退出")

        # 销毁窗口
        self.root.destroy()

    def _on_quit(self) -> None:
        """退出程序"""
        self._on_closing()

    def run(self) -> None:
        """运行应用"""
        self.root.mainloop()
