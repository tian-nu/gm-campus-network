"""
日志配置模块
提供统一的日志配置和管理
"""

import logging
import sys
from typing import Optional, Callable
from datetime import datetime


# 日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"
LOG_FORMAT_SIMPLE = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LogRecord:
    """日志记录数据类"""

    def __init__(self, timestamp: datetime, level: str, thread: str, message: str):
        self.timestamp = timestamp
        self.level = level
        self.thread = thread
        self.message = message

    def __str__(self):
        return f"{self.timestamp.strftime(LOG_DATE_FORMAT)} - {self.level} - {self.thread} - {self.message}"


class GUILogHandler(logging.Handler):
    """GUI 日志处理器，将日志发送到 GUI 回调"""

    def __init__(self, callback: Callable[[str], None]):
        """
        初始化 GUI 日志处理器

        Args:
            callback: 接收日志消息的回调函数
        """
        super().__init__()
        self.callback = callback
        self.setFormatter(logging.Formatter(LOG_FORMAT))

    def emit(self, record: logging.LogRecord):
        """发送日志记录"""
        try:
            msg = self.format(record)
            self.callback(msg + "\n")
        except Exception:
            self.handleError(record)


def setup_logging(
    debug_mode: bool = False,
    log_file: str = "campus_net.log",
    console_output: bool = True
) -> logging.Logger:
    """
    配置日志系统

    Args:
        debug_mode: 是否启用调试模式
        log_file: 日志文件路径
        console_output: 是否输出到控制台

    Returns:
        配置好的 Logger 实例
    """
    log_level = logging.DEBUG if debug_mode else logging.INFO

    # 获取根日志器
    root_logger = logging.getLogger()

    # 移除已存在的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 文件处理器
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"无法创建日志文件: {e}", file=sys.stderr)

    # 控制台处理器
    if console_output:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(log_level)
        root_logger.addHandler(stream_handler)

    # 设置日志级别
    root_logger.setLevel(log_level)

    return logging.getLogger(__name__)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器

    Args:
        name: 日志器名称

    Returns:
        Logger 实例
    """
    return logging.getLogger(name)


def add_gui_handler(callback: Callable[[str], None], level: int = logging.INFO) -> GUILogHandler:
    """
    添加 GUI 日志处理器

    Args:
        callback: 日志回调函数
        level: 日志级别

    Returns:
        GUILogHandler 实例
    """
    handler = GUILogHandler(callback)
    handler.setLevel(level)
    logging.getLogger().addHandler(handler)
    return handler


def remove_handler(handler: logging.Handler) -> None:
    """
    移除日志处理器

    Args:
        handler: 要移除的处理器
    """
    logging.getLogger().removeHandler(handler)


def parse_log_line(line: str) -> Optional[LogRecord]:
    """
    解析日志行

    Args:
        line: 日志行字符串

    Returns:
        LogRecord 实例或 None
    """
    try:
        # 格式: 2024-01-01 12:00:00 - INFO - MainThread - Message
        parts = line.split(" - ", 3)
        if len(parts) >= 4:
            timestamp = datetime.strptime(parts[0], LOG_DATE_FORMAT)
            level = parts[1]
            thread = parts[2]
            message = parts[3].strip()
            return LogRecord(timestamp, level, thread, message)
    except Exception:
        pass
    return None
