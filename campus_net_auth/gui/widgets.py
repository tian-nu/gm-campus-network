"""
自定义 GUI 控件
提供可复用的 UI 组件
"""

from tkinter import *
from tkinter import ttk
from typing import Optional, Callable


class ScrollableFrame:
    """可滚动的 Frame 容器"""

    def __init__(self, container: Widget, **kwargs):
        """
        初始化可滚动框架

        Args:
            container: 父容器
            **kwargs: Canvas 参数
        """
        self.canvas = Canvas(container, **kwargs)
        self.scrollbar = Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas)

        # 绑定滚动事件
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # 创建窗口
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 绑定鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """处理鼠标滚轮"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def pack(self, **kwargs):
        """打包 Canvas"""
        self.canvas.pack(**kwargs)


class LabeledEntry(Frame):
    """带标签的输入框"""

    def __init__(
        self,
        parent: Widget,
        label_text: str,
        show: str = "",
        width: int = 25,
        font: tuple = ("Microsoft YaHei UI", 10),
        **kwargs
    ):
        """
        初始化带标签的输入框

        Args:
            parent: 父容器
            label_text: 标签文本
            show: 密码显示字符
            width: 输入框宽度
            font: 字体
        """
        super().__init__(parent, **kwargs)

        self.var = StringVar()

        # 标签
        self.label = Label(self, text=label_text, font=font, width=8, anchor="e")
        self.label.pack(side=LEFT, padx=(0, 10))

        # 输入框
        self.entry = Entry(
            self,
            textvariable=self.var,
            font=font,
            width=width,
            show=show
        )
        self.entry.pack(side=LEFT, fill=X, expand=True)

    def get(self) -> str:
        """获取输入值"""
        return self.var.get()

    def set(self, value: str) -> None:
        """设置输入值"""
        self.var.set(value)

    def focus(self) -> None:
        """聚焦输入框"""
        self.entry.focus_set()


class StatusLabel(Frame):
    """状态标签"""

    def __init__(
        self,
        parent: Widget,
        label_text: str,
        initial_text: str = "未知",
        font: tuple = ("Microsoft YaHei UI", 10),
        **kwargs
    ):
        """
        初始化状态标签

        Args:
            parent: 父容器
            label_text: 标签文本
            initial_text: 初始状态文本
            font: 字体
        """
        super().__init__(parent, **kwargs)

        # 标签
        self.label = Label(self, text=label_text, font=font, width=10, anchor="e")
        self.label.pack(side=LEFT, padx=(0, 10))

        # 状态值
        self.value_label = Label(
            self,
            text=initial_text,
            font=(font[0], font[1], "bold"),
            fg="gray"
        )
        self.value_label.pack(side=LEFT)

    def set_status(self, text: str, color: str = "gray") -> None:
        """设置状态"""
        self.value_label.config(text=text, fg=color)

    def set_connected(self) -> None:
        """设置为已连接状态"""
        self.set_status("已连接", "#4CAF50")

    def set_disconnected(self) -> None:
        """设置为未连接状态"""
        self.set_status("未连接", "#F44336")

    def set_unknown(self) -> None:
        """设置为未知状态"""
        self.set_status("未知", "gray")


class SettingCheckbox(Frame):
    """设置复选框"""

    def __init__(
        self,
        parent: Widget,
        text: str,
        font: tuple = ("Microsoft YaHei UI", 10),
        **kwargs
    ):
        """
        初始化设置复选框

        Args:
            parent: 父容器
            text: 复选框文本
            font: 字体
        """
        super().__init__(parent, **kwargs)

        self.var = BooleanVar()

        self.checkbox = Checkbutton(
            self,
            text=text,
            variable=self.var,
            font=font
        )
        self.checkbox.pack(side=LEFT)

    def get(self) -> bool:
        """获取选中状态"""
        return self.var.get()

    def set(self, value: bool) -> None:
        """设置选中状态"""
        self.var.set(value)


class SettingSpinbox(Frame):
    """设置数字输入框"""

    def __init__(
        self,
        parent: Widget,
        label_text: str,
        min_val: int = 0,
        max_val: int = 100,
        default_val: int = 0,
        width: int = 8,
        font: tuple = ("Microsoft YaHei UI", 10),
        **kwargs
    ):
        """
        初始化设置数字输入框

        Args:
            parent: 父容器
            label_text: 标签文本
            min_val: 最小值
            max_val: 最大值
            default_val: 默认值
            width: 输入框宽度
            font: 字体
        """
        super().__init__(parent, **kwargs)

        self.var = IntVar(value=default_val)

        # 标签
        self.label = Label(self, text=label_text, font=font)
        self.label.pack(side=LEFT, padx=(0, 10))

        # 数字输入框
        self.spinbox = Spinbox(
            self,
            from_=min_val,
            to=max_val,
            textvariable=self.var,
            width=width,
            font=font
        )
        self.spinbox.pack(side=LEFT)

    def get(self) -> int:
        """获取值"""
        return self.var.get()

    def set(self, value: int) -> None:
        """设置值"""
        self.var.set(value)


class ActionButton(Button):
    """操作按钮"""

    def __init__(
        self,
        parent: Widget,
        text: str,
        command: Optional[Callable] = None,
        style: str = "primary",
        width: int = 15,
        height: int = 2,
        font: tuple = ("Microsoft YaHei UI", 11, "bold"),
        **kwargs
    ):
        """
        初始化操作按钮

        Args:
            parent: 父容器
            text: 按钮文本
            command: 点击回调
            style: 按钮样式 (primary, success, danger, default)
            width: 按钮宽度
            height: 按钮高度
            font: 字体
        """
        # 样式配置
        styles = {
            "primary": {"bg": "#2196F3", "fg": "white", "activebackground": "#1976D2"},
            "success": {"bg": "#4CAF50", "fg": "white", "activebackground": "#388E3C"},
            "danger": {"bg": "#F44336", "fg": "white", "activebackground": "#D32F2F"},
            "default": {"bg": "#E0E0E0", "fg": "#333333", "activebackground": "#BDBDBD"},
        }

        style_config = styles.get(style, styles["default"])

        super().__init__(
            parent,
            text=text,
            command=command,
            font=font,
            width=width,
            height=height,
            **style_config,
            **kwargs
        )

    def set_loading(self, loading: bool = True, loading_text: str = "处理中...") -> None:
        """设置加载状态"""
        if loading:
            self._original_text = self.cget("text")
            self.config(state=DISABLED, text=loading_text)
        else:
            self.config(state=NORMAL, text=getattr(self, "_original_text", self.cget("text")))


class SettingGroup(LabelFrame):
    """设置分组"""

    def __init__(
        self,
        parent: Widget,
        title: str,
        font: tuple = ("Microsoft YaHei UI", 11, "bold"),
        **kwargs
    ):
        """
        初始化设置分组

        Args:
            parent: 父容器
            title: 分组标题
            font: 字体
        """
        super().__init__(
            parent,
            text=title,
            font=font,
            padx=15,
            pady=10,
            **kwargs
        )
