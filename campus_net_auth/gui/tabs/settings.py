"""
设置标签页
提供应用配置界面
"""

import logging
from tkinter import *
from typing import Callable

from ..widgets import (
    SettingCheckbox, SettingSpinbox,
    ActionButton, SettingGroup
)


class SettingsTab(Frame):
    """设置标签页"""
    
    # 类型注解
    logger: logging.Logger
    on_save: Callable[[dict], None] | None
    on_reset: Callable[[], None] | None
    scrollable_frame: Frame | None
    startup_check: SettingCheckbox | None
    auto_login_check: SettingCheckbox | None
    minimize_startup_check: SettingCheckbox | None
    remember_password_check: SettingCheckbox | None
    login_success_notify_check: SettingCheckbox | None
    login_fail_notify_check: SettingCheckbox | None
    silent_mode_check: SettingCheckbox | None
    check_proxy_before_login_check: SettingCheckbox | None
    strict_proxy_check_check: SettingCheckbox | None
    timeout_spinbox: SettingSpinbox | None
    max_retries_spinbox: SettingSpinbox | None
    enable_heartbeat_check: SettingCheckbox | None
    heartbeat_interval_spinbox: SettingSpinbox | None
    heartbeat_url_var: StringVar | None
    enable_reconnect_check: SettingCheckbox | None
    reconnect_interval_spinbox: SettingSpinbox | None
    reconnect_cooldown_spinbox: SettingSpinbox | None
    debug_mode_check: SettingCheckbox | None
    verbose_log_check: SettingCheckbox | None
    auto_clean_log_check: SettingCheckbox | None
    log_retention_spinbox: SettingSpinbox | None
    enable_auto_retry_after_ban_check: SettingCheckbox | None
    default_ban_duration_spinbox: SettingSpinbox | None
    status_label: Label | None

    def __init__(
        self,
        parent: Widget,
        on_save: Callable[[dict], None] | None = None,
        on_reset: Callable[[], None] | None = None,
        **kwargs
    ):
        """
        初始化设置标签页

        Args:
            parent: 父容器
            on_save: 保存回调函数
            on_reset: 重置回调函数
        """
        super().__init__(parent, **kwargs)

        self.logger = logging.getLogger(__name__)
        self.on_save = on_save
        self.on_reset = on_reset

        # 初始化所有属性
        self.scrollable_frame: Frame | None = None
        self.startup_check: SettingCheckbox | None = None
        self.auto_login_check: SettingCheckbox | None = None
        self.minimize_startup_check: SettingCheckbox | None = None
        self.remember_password_check: SettingCheckbox | None = None
        self.login_success_notify_check: SettingCheckbox | None = None
        self.login_fail_notify_check: SettingCheckbox | None = None
        self.silent_mode_check: SettingCheckbox | None
        self.check_proxy_before_login_check: SettingCheckbox | None
        self.strict_proxy_check_check: SettingCheckbox | None
        self.timeout_spinbox: SettingSpinbox | None = None
        self.max_retries_spinbox: SettingSpinbox | None = None
        self.enable_heartbeat_check: SettingCheckbox | None = None
        self.heartbeat_interval_spinbox: SettingSpinbox | None = None
        self.heartbeat_url_var: StringVar | None = None
        self.enable_reconnect_check: SettingCheckbox | None = None
        self.reconnect_interval_spinbox: SettingSpinbox | None = None
        self.reconnect_cooldown_spinbox: SettingSpinbox | None = None
        self.debug_mode_check: SettingCheckbox | None = None
        self.verbose_log_check: SettingCheckbox | None = None
        self.auto_clean_log_check: SettingCheckbox | None = None
        self.log_retention_spinbox: SettingSpinbox | None = None
        self.enable_auto_retry_after_ban_check: SettingCheckbox | None = None
        self.default_ban_duration_spinbox: SettingSpinbox | None = None
        self.status_label: Label | None = None

        self._create_widgets()

    def _create_widgets(self) -> None:
        """创建控件"""
        # 创建Canvas和Scrollbar实现滚动
        canvas = Canvas(self, bg="#f5f5f5", highlightthickness=0)
        scrollbar = Scrollbar(self, orient=VERTICAL, command=canvas.yview)

        # 可滚动的Frame
        self.scrollable_frame = Frame(canvas, padx=20, pady=15)

        # 配置滚动
        _ = self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        _ = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=canvas.winfo_width())
        canvas.configure(yscrollcommand=scrollbar.set)

        # 打包Canvas和Scrollbar
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 标题
        Label(
            self.scrollable_frame,
            text="设置",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg="#333333"
        ).pack(anchor=W, pady=(0, 15))

        # 启动设置
        self._create_startup_settings(self.scrollable_frame)

        # 登录设置
        self._create_login_settings(self.scrollable_frame)

        # 网络设置
        self._create_network_settings(self.scrollable_frame)

        # 心跳设置
        self._create_heartbeat_settings(self.scrollable_frame)

        # 重连设置
        self._create_reconnect_settings(self.scrollable_frame)

        # 高级设置
        self._create_advanced_settings(self.scrollable_frame)

        # 按钮区域
        self._create_buttons(self.scrollable_frame)

        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        _ = canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 窗口大小改变时调整canvas宽度
        def _on_canvas_configure(_event):
            canvas.itemconfig("all", width=_event.width)

        _ = canvas.bind("<Configure>", _on_canvas_configure)

    def _create_startup_settings(self, parent: Widget) -> None:
        """创建启动设置"""
        group = SettingGroup(parent, title="启动设置")
        group.pack(fill=X, pady=(0, 10))

        self.startup_check = SettingCheckbox(group, text="开机自启动")
        self.startup_check.pack(anchor=W, pady=3)

        self.auto_login_check = SettingCheckbox(group, text="启动时自动登录")
        self.auto_login_check.pack(anchor=W, pady=3)

        self.minimize_startup_check = SettingCheckbox(group, text="启动时最小化")
        self.minimize_startup_check.pack(anchor=W, pady=3)

    def _create_login_settings(self, parent: Widget) -> None:
        """创建登录设置"""
        group = SettingGroup(parent, title="登录设置")
        group.pack(fill=X, pady=(0, 10))

        self.remember_password_check = SettingCheckbox(group, text="记住密码")
        self.remember_password_check.pack(anchor=W, pady=3)

        # 合并通知设置
        self.login_success_notify_check = SettingCheckbox(group, text="登录成功提示")
        self.login_success_notify_check.pack(anchor=W, pady=3)

        self.login_fail_notify_check = SettingCheckbox(group, text="登录失败提示")
        self.login_fail_notify_check.pack(anchor=W, pady=3)

        self.silent_mode_check = SettingCheckbox(group, text="静默模式（仅异常通知）")
        self.silent_mode_check.pack(anchor=W, pady=3)

        # 代理检测设置
        self.check_proxy_before_login_check = SettingCheckbox(group, text="登录前检测代理")
        self.check_proxy_before_login_check.pack(anchor=W, pady=3)

        # 严格代理检测模式
        self.strict_proxy_check_check = SettingCheckbox(group, text="严格代理检测（检测到代理时阻止登录）")
        self.strict_proxy_check_check.pack(anchor=W, pady=3)

    def _create_network_settings(self, parent: Widget) -> None:
        """创建网络设置"""
        group = SettingGroup(parent, title="网络设置")
        group.pack(fill=X, pady=(0, 10))

        self.timeout_spinbox = SettingSpinbox(
            group,
            label_text="超时时间 (秒):",
            min_val=5,
            max_val=60,
            default_val=10
        )
        self.timeout_spinbox.pack(anchor=W, pady=3)

        self.max_retries_spinbox = SettingSpinbox(
            group,
            label_text="最大重试次数:",
            min_val=1,
            max_val=10,
            default_val=3
        )
        self.max_retries_spinbox.pack(anchor=W, pady=3)

    def _create_heartbeat_settings(self, parent: Widget) -> None:
        """创建心跳设置"""
        group = SettingGroup(parent, title="心跳保持")
        group.pack(fill=X, pady=(0, 10))

        self.enable_heartbeat_check = SettingCheckbox(group, text="启用心跳保持")
        self.enable_heartbeat_check.pack(anchor=W, pady=3)

        self.heartbeat_interval_spinbox = SettingSpinbox(
            group,
            label_text="心跳间隔 (秒):",
            min_val=30,
            max_val=600,
            default_val=120
        )
        self.heartbeat_interval_spinbox.pack(anchor=W, pady=3)

        # 心跳 URL
        url_frame = Frame(group)
        url_frame.pack(fill=X, pady=3)

        Label(url_frame, text="心跳 URL:", font=("Microsoft YaHei UI", 10)).pack(side=LEFT)
        self.heartbeat_url_var = StringVar()
        Entry(
            url_frame,
            textvariable=self.heartbeat_url_var,
            font=("Microsoft YaHei UI", 10),
            width=30
        ).pack(side=LEFT, padx=(10, 0))

    def _create_reconnect_settings(self, parent: Widget) -> None:
        """创建重连设置"""
        group = SettingGroup(parent, title="断线重连")
        group.pack(fill=X, pady=(0, 10))

        self.enable_reconnect_check = SettingCheckbox(group, text="启用断线重连")
        self.enable_reconnect_check.pack(anchor=W, pady=3)

        self.reconnect_interval_spinbox = SettingSpinbox(
            group,
            label_text="检测间隔 (秒):",
            min_val=10,
            max_val=300,
            default_val=30
        )
        self.reconnect_interval_spinbox.pack(anchor=W, pady=3)

        self.reconnect_cooldown_spinbox = SettingSpinbox(
            group,
            label_text="冷却时间 (秒):",
            min_val=10,
            max_val=300,
            default_val=30
        )
        self.reconnect_cooldown_spinbox.pack(anchor=W, pady=3)

    def _create_advanced_settings(self, parent: Widget) -> None:
        """创建高级设置"""
        group = SettingGroup(parent, title="高级设置")
        group.pack(fill=X, pady=(0, 10))

        self.debug_mode_check = SettingCheckbox(group, text="调试模式")
        self.debug_mode_check.pack(anchor=W, pady=3)

        self.verbose_log_check = SettingCheckbox(group, text="详细日志")
        self.verbose_log_check.pack(anchor=W, pady=3)

        self.auto_clean_log_check = SettingCheckbox(group, text="自动清理日志")
        self.auto_clean_log_check.pack(anchor=W, pady=3)

        self.log_retention_spinbox = SettingSpinbox(
            group,
            label_text="日志保留天数:",
            min_val=1,
            max_val=30,
            default_val=7
        )
        self.log_retention_spinbox.pack(anchor=W, pady=3)

        # 封禁处理设置
        self.enable_auto_retry_after_ban_check = SettingCheckbox(group, text="封禁后自动重试")
        self.enable_auto_retry_after_ban_check.pack(anchor=W, pady=3)

        self.default_ban_duration_spinbox = SettingSpinbox(
            group,
            label_text="默认封禁时长(分钟):",
            min_val=1,
            max_val=120,
            default_val=30
        )
        self.default_ban_duration_spinbox.pack(anchor=W, pady=3)

    def _create_buttons(self, parent: Widget) -> None:
        """创建按钮区域"""
        # 按钮框架
        button_frame = Frame(parent)
        button_frame.pack(fill=X, pady=(20, 10))

        ActionButton(
            button_frame,
            text="保存设置",
            command=self._on_save_click,
            style="success",
            width=12,
            height=1,
            font=("Microsoft YaHei UI", 10)
        ).pack(side=LEFT, padx=(0, 10))

        ActionButton(
            button_frame,
            text="恢复默认",
            command=self._on_reset_click,
            style="default",
            width=12,
            height=1,
            font=("Microsoft YaHei UI", 10)
        ).pack(side=LEFT)

        # 状态提示标签
        self.status_label = Label(
            parent,
            text="",
            font=("Microsoft YaHei UI", 10),
            fg="#666666"
        )
        self.status_label.pack(anchor=W, pady=(5, 0))

    def _show_status(self, message: str, msg_type: str = "info") -> None:
        """显示状态提示"""
        colors = {
            "success": "#4CAF50",
            "error": "#F44336",
            "warning": "#FF9800",
            "info": "#2196F3"
        }
        color = colors.get(msg_type, "#666666")
        self.status_label.config(text=message, fg=color)

        # 3秒后清除
        self.after(3000, lambda: self.status_label.config(text=""))

    def get_config(self) -> dict[str, object]:
        """获取当前配置"""
        return {
            # 启动设置
            "startup": self.startup_check.get(),
            "auto_login": self.auto_login_check.get(),
            "remember_password": self.remember_password_check.get(),
            "minimize_startup": self.minimize_startup_check.get(),

            # 通知设置
            "login_success_notify": self.login_success_notify_check.get(),
            "login_fail_notify": self.login_fail_notify_check.get(),
            "silent_mode": self.silent_mode_check.get(),
            "check_proxy_before_login": self.check_proxy_before_login_check.get(),
            "strict_proxy_check": self.strict_proxy_check_check.get(),

            # 网络设置
            "timeout": self.timeout_spinbox.get(),
            "max_retries": self.max_retries_spinbox.get(),

            # 心跳设置
            "enable_heartbeat": self.enable_heartbeat_check.get(),
            "heartbeat_interval": self.heartbeat_interval_spinbox.get(),
            "heartbeat_url": self.heartbeat_url_var.get(),

            # 重连设置
            "enable_reconnect": self.enable_reconnect_check.get(),
            "reconnect_interval": self.reconnect_interval_spinbox.get(),
            "reconnect_cooldown": self.reconnect_cooldown_spinbox.get(),

            # 高级设置
            "debug_mode": self.debug_mode_check.get(),
            "verbose_log": self.verbose_log_check.get(),
            "auto_clean_log": self.auto_clean_log_check.get(),
            "log_retention_days": self.log_retention_spinbox.get(),
            
            # 封禁处理设置
            "enable_auto_retry_after_ban": self.enable_auto_retry_after_ban_check.get(),
            "default_ban_duration": self.default_ban_duration_spinbox.get(),
        }

    def set_config(self, config: dict) -> None:
        """设置配置"""
        # 启动设置
        self.startup_check.set(config.get("startup", False))
        self.auto_login_check.set(config.get("auto_login", False))
        self.remember_password_check.set(config.get("remember_password", True))
        self.minimize_startup_check.set(config.get("minimize_startup", False))

        # 通知设置
        self.login_success_notify_check.set(config.get("login_success_notify", True))
        self.login_fail_notify_check.set(config.get("login_fail_notify", True))
        self.silent_mode_check.set(config.get("silent_mode", True))
        self.check_proxy_before_login_check.set(config.get("check_proxy_before_login", True))
        self.strict_proxy_check_check.set(config.get("strict_proxy_check", True))

        # 网络设置
        self.timeout_spinbox.set(config.get("timeout", 10))
        self.max_retries_spinbox.set(config.get("max_retries", 3))

        # 心跳设置
        self.enable_heartbeat_check.set(config.get("enable_heartbeat", True))
        self.heartbeat_interval_spinbox.set(config.get("heartbeat_interval", 120))
        self.heartbeat_url_var.set(config.get("heartbeat_url", ""))

        # 重连设置
        self.enable_reconnect_check.set(config.get("enable_reconnect", True))
        self.reconnect_interval_spinbox.set(config.get("reconnect_interval", 30))
        self.reconnect_cooldown_spinbox.set(config.get("reconnect_cooldown", 30))

        # 高级设置
        self.debug_mode_check.set(config.get("debug_mode", False))
        self.verbose_log_check.set(config.get("verbose_log", True))
        self.auto_clean_log_check.set(config.get("auto_clean_log", True))
        self.log_retention_spinbox.set(config.get("log_retention_days", 7))
        
        # 封禁处理设置
        self.enable_auto_retry_after_ban_check.set(config.get("enable_auto_retry_after_ban", True))
        self.default_ban_duration_spinbox.set(config.get("default_ban_duration", 30))

    def _on_save_click(self) -> None:
        """保存按钮点击事件"""
        if self.on_save:
            self.on_save(self.get_config())

    def _on_reset_click(self) -> None:
        """重置按钮点击事件"""
        if self.on_reset:
            self.on_reset()
