"""
登录标签页
提供用户登录界面
"""

import logging
import threading
from datetime import datetime
from tkinter import *
from typing import Callable, Optional

from ..widgets import LabeledEntry, StatusLabel, ActionButton, SettingGroup
from ...utils.network_info import NetworkInfo


class LoginTab(Frame):
    """登录标签页"""

    def __init__(
        self,
        parent: Widget,
        on_login: Optional[Callable[[str, str], None]] = None,
        on_minimize: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        """
        初始化登录标签页

        Args:
            parent: 父容器
            on_login: 登录回调函数
            on_minimize: 最小化回调函数
        """
        super().__init__(parent, **kwargs)

        self.logger = logging.getLogger(__name__)
        self.on_login = on_login
        self.on_minimize = on_minimize

        # 状态
        self.is_logging_in = False
        self.login_count = 0
        self.last_login_time: Optional[datetime] = None
        self.check_proxy_before_login = True  # 是否在登录前检测代理
        self._proxy_warned = False  # 是否已提示过代理警告

        self._create_widgets()

    def _create_widgets(self) -> None:
        """创建控件"""
        # 主框架
        main_frame = Frame(self, padx=30, pady=20)
        main_frame.pack(fill=BOTH, expand=True)

        # 标题
        title_label = Label(
            main_frame,
            text="校园网自动认证",
            font=("Microsoft YaHei UI", 20, "bold"),
            fg="#333333"
        )
        title_label.pack(pady=(0, 10))

        # 副标题
        subtitle_label = Label(
            main_frame,
            text="Campus Network Authentication",
            font=("Microsoft YaHei UI", 10),
            fg="#666666"
        )
        subtitle_label.pack(pady=(0, 30))

        # 登录表单
        form_frame = Frame(main_frame)
        form_frame.pack(fill=X, pady=(0, 20))

        # 学号输入
        self.username_entry = LabeledEntry(
            form_frame,
            label_text="学号:",
            width=22
        )
        self.username_entry.pack(fill=X, pady=8)

        # 密码输入
        self.password_entry = LabeledEntry(
            form_frame,
            label_text="密码:",
            show="●",
            width=22
        )
        self.password_entry.pack(fill=X, pady=8)

        # 按钮区域
        button_frame = Frame(main_frame)
        button_frame.pack(fill=X, pady=15)

        # 登录按钮
        self.login_btn = ActionButton(
            button_frame,
            text="一键登录",
            command=self._on_login_click,
            style="success",
            width=18,
            height=2
        )
        self.login_btn.pack(pady=5)

        # 代理警告标签（默认隐藏）
        self.proxy_warning_label = Label(
            button_frame,
            text="⚠ 检测到代理已开启，登录可能被封禁",
            font=("Microsoft YaHei UI", 9),
            fg="#FF9800"
        )

        # 最小化按钮
        self.minimize_btn = ActionButton(
            button_frame,
            text="最小化到托盘",
            command=self._on_minimize_click,
            style="primary",
            width=14,
            height=1,
            font=("Microsoft YaHei UI", 9)
        )
        self.minimize_btn.pack(pady=5)

        # 状态区域
        status_group = SettingGroup(main_frame, title="系统状态")
        status_group.pack(fill=X, pady=(15, 0))

        # 网络状态
        self.network_status = StatusLabel(
            status_group,
            label_text="网络状态:",
            initial_text="检测中..."
        )
        self.network_status.pack(fill=X, pady=3)

        # 登录状态
        self.login_status = StatusLabel(
            status_group,
            label_text="登录状态:",
            initial_text="未登录"
        )
        self.login_status.pack(fill=X, pady=3)

        # 最后登录
        self.last_login_status = StatusLabel(
            status_group,
            label_text="最后登录:",
            initial_text="无"
        )
        self.last_login_status.pack(fill=X, pady=3)

        # 登录次数
        self.login_count_status = StatusLabel(
            status_group,
            label_text="登录次数:",
            initial_text="0"
        )
        self.login_count_status.pack(fill=X, pady=3)

        # 网络信息
        self.network_info_frame = Frame(status_group)
        self.network_info_frame.pack(fill=X, pady=(10, 5))

        self.ip_label = Label(
            self.network_info_frame,
            text="IP: 获取中...",
            font=("Microsoft YaHei UI", 9),
            fg="#666666"
        )
        self.ip_label.pack(side=LEFT, padx=(0, 20))

        self.mac_label = Label(
            self.network_info_frame,
            text="MAC: 获取中...",
            font=("Microsoft YaHei UI", 9),
            fg="#666666"
        )
        self.mac_label.pack(side=LEFT)

        # 消息提示区域
        self.message_label = Label(
            main_frame,
            text="",
            font=("Microsoft YaHei UI", 10),
            fg="#666666",
            wraplength=350
        )
        self.message_label.pack(fill=X, pady=(10, 0))

    def _show_message(self, message: str, msg_type: str = "info") -> None:
        """
        显示消息提示

        Args:
            message: 消息内容
            msg_type: 消息类型 (success, error, warning, info)
        """
        colors = {
            "success": "#4CAF50",
            "error": "#F44336",
            "warning": "#FF9800",
            "info": "#2196F3"
        }
        color = colors.get(msg_type, "#666666")
        self.message_label.config(text=message, fg=color)

        # 5秒后清除消息
        self.after(5000, lambda: self.message_label.config(text=""))

    def _on_login_click(self) -> None:
        """登录按钮点击"""
        if self.is_logging_in:
            return

        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self._show_message("请输入学号和密码", "warning")
            return

        # 检测代理（仅首次提示，不影响操作）
        if self.check_proxy_before_login and not self._proxy_warned:
            has_proxy, warning_msg = NetworkInfo.check_proxy_before_login()
            if has_proxy:
                # 显示警告标签，不弹窗
                self.proxy_warning_label.pack(pady=(5, 0))
                self._proxy_warned = True
                self.logger.warning("检测到代理已开启")

        self.is_logging_in = True
        self.login_btn.set_loading(True, "登录中...")

        if self.on_login:
            # 在后台线程执行登录
            threading.Thread(
                target=self._do_login,
                args=(username, password),
                daemon=True
            ).start()

    def _do_login(self, username: str, password: str) -> None:
        """执行登录（后台线程）"""
        try:
            if self.on_login:
                self.on_login(username, password)
        except Exception as e:
            self.logger.error(f"登录异常: {e}")
            self.after(0, lambda: self.on_login_finished(False, f"登录异常: {e}"))

    def _on_minimize_click(self) -> None:
        """最小化按钮点击"""
        if self.on_minimize:
            self.on_minimize()

    def on_login_finished(self, success: bool, message: str) -> None:
        """登录完成回调"""
        self.is_logging_in = False
        self.login_btn.set_loading(False)

        if success:
            self.login_count += 1
            self.last_login_time = datetime.now()

            self.login_status.set_status("已登录", "#4CAF50")
            self.last_login_status.set_status(
                self.last_login_time.strftime("%Y-%m-%d %H:%M:%S"),
                "#333333"
            )
            self.login_count_status.set_status(str(self.login_count), "#333333")

            self._show_message(message, "success")
        else:
            if "网络已连通" in message:
                self._show_message(message, "info")
            else:
                self._show_message(message, "error")

    def set_credentials(self, username: str, password: str) -> None:
        """设置登录凭证"""
        self.username_entry.set(username)
        self.password_entry.set(password)

    def get_credentials(self) -> tuple:
        """获取登录凭证"""
        return self.username_entry.get(), self.password_entry.get()

    def update_network_status(self, connected: bool) -> None:
        """更新网络状态"""
        if connected:
            self.network_status.set_connected()
        else:
            self.network_status.set_disconnected()

    def update_login_status(self, logged_in: bool) -> None:
        """更新登录状态"""
        if logged_in:
            self.login_status.set_status("已登录", "#4CAF50")
        else:
            self.login_status.set_status("未登录", "#F44336")

    def update_network_info(self, ip: str, mac: str) -> None:
        """更新网络信息"""
        self.ip_label.config(text=f"IP: {ip}")
        self.mac_label.config(text=f"MAC: {mac}")
