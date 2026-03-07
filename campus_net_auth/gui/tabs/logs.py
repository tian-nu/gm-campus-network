"""
日志标签页
提供日志查看和管理界面
"""

import logging
import os
import sys
from tkinter import *
from tkinter import scrolledtext, filedialog
from typing import Optional

from ..widgets import ActionButton


class LogsTab(Frame):
    """日志标签页"""

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

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=WORD,
            font=("Consolas", 9),
            bg="#1E1E1E",
            fg="#D4D4D4",
            insertbackground="white",
            selectbackground="#264F78",
            height=20
        )
        self.log_text.pack(fill=BOTH, expand=True, pady=(0, 10))
        self.log_text.config(state=DISABLED)

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
            text="",
            font=("Microsoft YaHei UI", 9),
            fg="#666666"
        )
        self.status_label.pack(anchor=W, pady=(5, 0))

    def append_log(self, message: str) -> None:
        """
        添加日志消息

        Args:
            message: 日志消息
        """
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, message)
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

        # 更新状态
        line_count = int(self.log_text.index('end-1c').split('.')[0])
        self.status_label.config(text=f"共 {line_count} 行日志")

    def _clear_log(self) -> None:
        """清空日志"""
        self.log_text.config(state=NORMAL)
        self.log_text.delete(1.0, END)
        self.log_text.config(state=DISABLED)
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
                    # 只读取最后 1000 行
                    lines = f.readlines()
                    recent_lines = lines[-1000:] if len(lines) > 1000 else lines

                self.log_text.config(state=NORMAL)
                self.log_text.delete(1.0, END)
                self.log_text.insert(END, "".join(recent_lines))
                self.log_text.see(END)
                self.log_text.config(state=DISABLED)

                self.status_label.config(text=f"已加载 {len(recent_lines)} 行日志")
            else:
                self.status_label.config(text="日志文件不存在")
        except Exception as e:
            self.logger.error(f"刷新日志失败: {e}")
            self.status_label.config(text=f"刷新失败: {e}")

    def get_log_content(self) -> str:
        """获取日志内容"""
        return self.log_text.get(1.0, END)
