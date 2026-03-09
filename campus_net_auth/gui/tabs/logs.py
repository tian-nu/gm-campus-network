"""
日志标签页
提供日志查看和管理界面（性能优化版）
"""

import logging
import os
import sys
from tkinter import *
from tkinter import filedialog
from typing import Optional

from ..widgets import ActionButton


class LogsTab(Frame):
    """日志标签页（轻量级实现）"""

    # 最大显示行数(进一步减少以提升性能)
    MAX_LINES = 200
    # 日志更新防抖间隔（毫秒）
    UPDATE_INTERVAL = 200

    # 类型注解
    logger: logging.Logger
    log_file: str
    log_text: Text | None
    status_label: Label | None
    _log_buffer: list[str]
    _pending_update: bool
    _line_count: int

    def __init__(self, parent: Widget, log_file: str = "campus_net.log", **kwargs):
        """
        初始化日志标签页

        Args:
            parent: 父容器
            log_file: 日志文件路径
        """
        super().__init__(parent, **kwargs)

        self.logger = logging.getLogger(__name__)
        self.log_file = log_file
        
        # 日志缓冲区
        self._log_buffer = []
        self._pending_update = False
        self._line_count = 0

        # 初始化属性
        self.log_text: Text | None = None
        self.status_label: Label | None = None

        self._create_widgets()

    def _create_widgets(self) -> None:
        """创建控件"""
        main_frame = Frame(self, padx=15, pady=15)
        main_frame.pack(fill=BOTH, expand=True)

        # 标题
        Label(
            main_frame,
            text="运行日志",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg="#333333"
        ).pack(anchor=W, pady=(0, 10))

        # 日志文本框（使用 Text + 垂直 Scrollbar，wrap=CHAR 性能更好）
        text_frame = Frame(main_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        # 垂直滚动条
        scrollbar = Scrollbar(text_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Text控件使用wrap=CHAR（比WORD性能更好，且可以自动换行）
        self.log_text = Text(
            text_frame,
            wrap=CHAR,  # 按字符换行，性能优于WORD，用户体验优于NONE
            font=("Consolas", 9),
            bg="#1E1E1E",
            fg="#D4D4D4",
            insertbackground="white",
            selectbackground="#264F78",
            height=20,
            yscrollcommand=scrollbar.set,
            state=DISABLED,
            tabs=("4c",)  # 设置tab宽度
        )
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

        # 按钮区域
        button_frame = Frame(main_frame)
        button_frame.pack(fill=X)

        ActionButton(
            button_frame,
            text="清空日志",
            command=self._clear_log,
            style="default",
            width=10,
            height=1,
            font=("Microsoft YaHei UI", 9)
        ).pack(side=LEFT, padx=(0, 8))

        ActionButton(
            button_frame,
            text="保存日志",
            command=self._save_log,
            style="primary",
            width=10,
            height=1,
            font=("Microsoft YaHei UI", 9)
        ).pack(side=LEFT, padx=(0, 8))

        ActionButton(
            button_frame,
            text="打开日志文件",
            command=self._open_log_file,
            style="default",
            width=12,
            height=1,
            font=("Microsoft YaHei UI", 9)
        ).pack(side=LEFT, padx=(0, 8))

        ActionButton(
            button_frame,
            text="刷新",
            command=self._refresh_log,
            style="default",
            width=8,
            height=1,
            font=("Microsoft YaHei UI", 9)
        ).pack(side=LEFT)

        # 状态栏
        self.status_label = Label(
            main_frame,
            text="共 0 行日志",
            font=("Microsoft YaHei UI", 9),
            fg="#666666"
        )
        self.status_label.pack(anchor=W, pady=(5, 0))

    def append_log(self, message: str) -> None:
        """
        添加日志消息（带缓冲和防抖）

        Args:
            message: 日志消息
        """
        # 添加到缓冲区
        self._log_buffer.append(message)
        
        # 防抖更新
        if not self._pending_update:
            self._pending_update = True
            self.after(self.UPDATE_INTERVAL, self._flush_log_buffer)

    def _flush_log_buffer(self) -> None:
        """刷新日志缓冲区到 UI"""
        if not self._log_buffer:
            self._pending_update = False
            return

        # 批量处理
        messages = self._log_buffer
        self._log_buffer = []
        self._pending_update = False

        # 合并消息
        combined = "".join(messages)

        # 更新 UI
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, combined)
        self._line_count += len(messages)

        # 限制行数
        if self._line_count > self.MAX_LINES:
            self._trim_excess_lines()

        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

        # 更新状态（不遍历文本）
        self.status_label.config(text=f"共 {self._line_count} 行日志")

    def _trim_excess_lines(self) -> None:
        """裁剪多余的日志行"""
        excess = self._line_count - self.MAX_LINES
        if excess > 0:
            self.log_text.delete("1.0", f"{excess + 1}.0")
            self._line_count = self.MAX_LINES

    def _clear_log(self) -> None:
        """清空日志"""
        self.log_text.config(state=NORMAL)
        self.log_text.delete(1.0, END)
        self.log_text.config(state=DISABLED)
        self._line_count = 0
        self._log_buffer.clear()
        self.status_label.config(text="共 0 行日志")
        self._show_status("✓ 日志已清空", "success")
        self.logger.info("日志显示已清空")

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

    def _save_log(self) -> None:
        """保存日志"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("日志文件", "*.log"), ("所有文件", "*.*")],
            title="保存日志"
        )

        if filename:
            try:
                content = self.log_text.get(1.0, END)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                self._show_status(f"✓ 日志已保存到: {filename}", "success")
            except Exception as e:
                self.logger.error(f"保存日志失败: {e}")
                self._show_status(f"✗ 保存失败: {e}", "error")

    def _open_log_file(self) -> None:
        """打开日志文件"""
        try:
            if os.path.exists(self.log_file):
                if sys.platform == "win32":
                    os.startfile(self.log_file)
                elif sys.platform == "darwin":
                    os.system(f"open {self.log_file}")
                else:
                    os.system(f"xdg-open {self.log_file}")
                self._show_status("✓ 已打开日志文件", "success")
            else:
                self._show_status("日志文件不存在", "warning")
        except Exception as e:
            self.logger.error(f"打开日志文件失败: {e}")
            self._show_status(f"✗ 打开失败: {e}", "error")

    def _refresh_log(self) -> None:
        """刷新日志（从文件加载）"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, "r", encoding="utf-8") as f:
                    # 只读取最后 MAX_LINES 行
                    lines = f.readlines()
                    recent_lines = lines[-self.MAX_LINES:] if len(lines) > self.MAX_LINES else lines

                self.log_text.config(state=NORMAL)
                self.log_text.delete(1.0, END)
                self.log_text.insert(END, "".join(recent_lines))
                self.log_text.see(END)
                self.log_text.config(state=DISABLED)
                
                self._line_count = len(recent_lines)
                self.status_label.config(text=f"已加载 {self._line_count} 行日志")
            else:
                self.status_label.config(text="日志文件不存在")
        except Exception as e:
            self.logger.error(f"刷新日志失败: {e}")
            self.status_label.config(text=f"刷新失败: {e}")

    def get_log_content(self) -> str:
        """获取日志内容"""
        return self.log_text.get(1.0, END)
