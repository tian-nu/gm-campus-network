"""
登录标签页
提供用户登录界面
"""

import logging
import threading
from datetime import datetime
from tkinter import *
from typing import Callable

from ..widgets import LabeledEntry, StatusLabel, ActionButton, SettingGroup
from ...utils.network_info import NetworkInfo


class LoginTab(Frame):
    """登录标签页"""
    
    # 类型注解
    logger: logging.Logger
    on_login: Callable[[str, str], None] | None
    on_minimize: Callable[[], None] | None
    is_logging_in: bool
    login_count: int
    last_login_time: datetime | None
    check_proxy_before_login: bool
    _proxy_warned: bool
    scrollable_frame: Frame
    username_entry: LabeledEntry
    password_entry: LabeledEntry
    login_btn: ActionButton
    proxy_warning_label: Label
    minimize_btn: ActionButton
    network_status: StatusLabel
    login_status: StatusLabel
    last_login_status: StatusLabel
    login_count_status: StatusLabel
    network_info_frame: Frame
    ip_label: Label
    mac_label: Label
    network_name_label: Label
    message_label: Label

    def __init__(
        self,
        parent: Widget,
        on_login: Callable[[str, str], None] | None = None,
        on_minimize: Callable[[], None] | None = None,
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
        self._login_timeout_id = None
        self.login_count = 0
        self.last_login_time: datetime | None = None
        self.check_proxy_before_login = True  # 是否在登录前检测代理
        self._proxy_warned = False  # 是否已提示过代理警告

        self._create_widgets()

    def _create_widgets(self) -> None:
        """创建控件"""
        # 创建Canvas和Scrollbar实现滚动
        canvas = Canvas(self, bg="#f5f5f5", highlightthickness=0)
        scrollbar = Scrollbar(self, orient=VERTICAL, command=canvas.yview)

        # 可滚动的Frame
        self.scrollable_frame = Frame(canvas, padx=30, pady=20)

        # 创建window — 不设 width，等 Configure 事件修正
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # 配置滚动区域
        def _configure_scroll_region(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        _ = self.scrollable_frame.bind("<Configure>", _configure_scroll_region)
        canvas.configure(yscrollcommand=scrollbar.set)

        # 打包Canvas和Scrollbar
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        _ = canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 窗口大小改变时调整canvas宽度
        def _on_canvas_configure(_event):
            canvas.update_idletasks()
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:
                canvas.itemconfig("all", width=canvas_width)

        canvas.bind("<Configure>", _on_canvas_configure)
        # 延迟触发一次初始对齐，确保窗口完全渲染后修正宽度
        self.after(300, lambda: _on_canvas_configure(None))

        # 标题
        title_label = Label(
            self.scrollable_frame,
            text="校园网自动认证",
            font=("Microsoft YaHei UI", 20, "bold"),
            fg="#333333"
        )
        title_label.pack(pady=(0, 10))

        # 副标题
        subtitle_label = Label(
            self.scrollable_frame,
            text="Campus Network Authentication",
            font=("Microsoft YaHei UI", 10),
            fg="#666666"
        )
        subtitle_label.pack(pady=(0, 30))

        # 登录表单
        form_frame = Frame(self.scrollable_frame)
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
        button_frame = Frame(self.scrollable_frame)
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
        status_group = SettingGroup(self.scrollable_frame, title="系统状态")
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

        self.network_name_label = Label(
            self.network_info_frame,
            text="网名: 检测中...",
            font=("Microsoft YaHei UI", 9),
            fg="#666666"
        )
        self.network_name_label.pack(side=LEFT, padx=(20, 0))

        # 消息提示区域
        self.message_label = Label(
            self.scrollable_frame,
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

        self.is_logging_in = True
        self.login_btn.set_loading(True, "登录中...")

        # 超时保护：60秒后自动重置状态，防止按钮永久不可点击
        self._login_timeout_id = self.after(60000, self._on_login_timeout)

        if self.on_login:
            # 在后台线程执行登录（代理检测也在线程中进行，避免阻塞UI）
            threading.Thread(
                target=self._do_login,
                args=(username, password),
                daemon=True
            ).start()

    def _do_login(self, username: str, password: str) -> None:
        """执行登录（后台线程，包含代理检测以避免阻塞 UI）"""
        try:
            # 检测代理（在线程中执行，避免阻塞 UI）
            if self.check_proxy_before_login and not self._proxy_warned:
                self.after(0, lambda: self.login_btn.config(text="检测代理..."))
                has_proxy, _warning_msg = NetworkInfo.check_proxy_before_login()
                if has_proxy:
                    self.after(0, self._show_proxy_warning)

            self.after(0, lambda: self.login_btn.config(text="登录中..."))

            if self.on_login:
                self.on_login(username, password)
        except Exception as e:
            self.logger.error(f"登录异常: {e}")
            self.after(0, lambda: self.on_login_finished(False, f"登录异常: {e}"))

    def _show_proxy_warning(self) -> None:
        """显示代理警告（必须在主线程调用）"""
        self.proxy_warning_label.pack(pady=(5, 0))
        self._proxy_warned = True
        self.logger.warning("检测到代理已开启")

    def _on_minimize_click(self) -> None:
        """最小化按钮点击"""
        if self.on_minimize:
            self.on_minimize()

    def _on_login_timeout(self) -> None:
        """登录超时保护：防止 is_logging_in 卡死导致按钮永久不可点击"""
        if self.is_logging_in:
            self.logger.warning("登录超时，自动重置状态")
            self.is_logging_in = False
            self.login_btn.set_loading(False)
            self._show_message("登录超时，请重试", "warning")

    def on_login_finished(self, success: bool, message: str) -> None:
        """登录完成回调"""
        # 取消超时保护
        if hasattr(self, '_login_timeout_id') and self._login_timeout_id:
            self.after_cancel(self._login_timeout_id)
            self._login_timeout_id = None

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
        _ = self.username_entry.set(username)
        _ = self.password_entry.set(password)

    def get_credentials(self) -> tuple[str, str]:
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

    def update_network_name(self, names: set | None = None) -> None:
        """
        更新当前网络名称显示

        Args:
            names: 网络名称集合，None 时自动获取
        """
        if names is None:
            try:
                names = NetworkInfo.get_connected_network_names()
            except Exception:
                names = set()

        if names:
            text = "网名: " + ", ".join(sorted(names))
            self.network_name_label.config(text=text, fg="#666666")
        else:
            self.network_name_label.config(text="网名: 未检测到", fg="#999999")
