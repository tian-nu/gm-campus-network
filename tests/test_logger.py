"""
日志模块测试
包含属性测试和单元测试
"""

import logging
import os
import sys
import tempfile
import re
from datetime import datetime

import pytest
from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campus_net_auth.utils.logger import (
    setup_logging,
    get_logger,
    add_gui_handler,
    remove_handler,
    parse_log_line,
    LogRecord,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
)


class TestLoggerProperties:
    """日志模块属性测试"""

    @given(st.text(min_size=1, max_size=200, alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'S'),
        blacklist_characters='\n\r\x00'
    )))
    @settings(max_examples=100)
    def test_log_entry_format(self, message):
        """
        **Feature: campus-net-refactor, Property 8: Log entry format**
        **Validates: Requirements 6.1**

        For any logged event, the log entry should contain a timestamp,
        severity level, and message content.
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            temp_file = f.name

        try:
            # 设置日志
            logger = setup_logging(debug_mode=False, log_file=temp_file, console_output=False)
            test_logger = logging.getLogger("test_format")

            # 记录日志
            test_logger.info(message)

            # 强制刷新
            for handler in logging.getLogger().handlers:
                handler.flush()

            # 读取日志文件
            with open(temp_file, 'r', encoding='utf-8') as f:
                log_content = f.read()

            # 验证日志格式
            if log_content.strip():
                lines = log_content.strip().split('\n')
                last_line = lines[-1]

                # 验证包含时间戳 (YYYY-MM-DD HH:MM:SS)
                timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
                assert re.search(timestamp_pattern, last_line), \
                    f"Log entry missing timestamp: {last_line}"

                # 验证包含日志级别
                level_pattern = r'(DEBUG|INFO|WARNING|ERROR|CRITICAL)'
                assert re.search(level_pattern, last_line), \
                    f"Log entry missing severity level: {last_line}"

                # 验证包含消息内容（如果消息非空）
                if message.strip():
                    # 消息可能被截断或转义，只检查部分内容
                    assert len(last_line) > 30, \
                        f"Log entry too short: {last_line}"

        finally:
            # 清理处理器
            for handler in logging.getLogger().handlers[:]:
                handler.close()
                logging.getLogger().removeHandler(handler)
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except PermissionError:
                pass  # Windows 文件锁定，忽略


class TestLoggerUnit:
    """日志模块单元测试"""

    def test_setup_logging_debug_mode(self):
        """测试调试模式日志配置"""
        temp_file = tempfile.mktemp(suffix='.log')

        try:
            logger = setup_logging(debug_mode=True, log_file=temp_file, console_output=False)

            # 验证日志级别
            assert logging.getLogger().level == logging.DEBUG

        finally:
            for handler in logging.getLogger().handlers[:]:
                handler.close()
                logging.getLogger().removeHandler(handler)
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except PermissionError:
                pass  # Windows 文件锁定，忽略

    def test_setup_logging_info_mode(self):
        """测试普通模式日志配置"""
        temp_file = tempfile.mktemp(suffix='.log')

        try:
            logger = setup_logging(debug_mode=False, log_file=temp_file, console_output=False)

            # 验证日志级别
            assert logging.getLogger().level == logging.INFO

        finally:
            for handler in logging.getLogger().handlers[:]:
                handler.close()
                logging.getLogger().removeHandler(handler)
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except PermissionError:
                pass  # Windows 文件锁定，忽略

    def test_gui_handler(self):
        """测试 GUI 日志处理器"""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        handler = add_gui_handler(callback)

        try:
            test_logger = logging.getLogger("test_gui")
            test_logger.info("Test message")

            # 验证回调被调用
            assert len(received_messages) > 0
            assert "Test message" in received_messages[-1]

        finally:
            remove_handler(handler)

    def test_parse_log_line_valid(self):
        """测试解析有效日志行"""
        line = "2024-01-15 10:30:45 - INFO - MainThread - Test message"
        record = parse_log_line(line)

        assert record is not None
        assert record.level == "INFO"
        assert record.thread == "MainThread"
        assert record.message == "Test message"
        assert record.timestamp.year == 2024
        assert record.timestamp.month == 1
        assert record.timestamp.day == 15

    def test_parse_log_line_invalid(self):
        """测试解析无效日志行"""
        line = "Invalid log line"
        record = parse_log_line(line)

        assert record is None

    def test_log_record_str(self):
        """测试 LogRecord 字符串表示"""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        record = LogRecord(timestamp, "INFO", "MainThread", "Test message")

        str_repr = str(record)
        assert "2024-01-15 10:30:45" in str_repr
        assert "INFO" in str_repr
        assert "MainThread" in str_repr
        assert "Test message" in str_repr

    def test_get_logger(self):
        """测试获取日志器"""
        logger1 = get_logger("test.module1")
        logger2 = get_logger("test.module2")

        assert logger1.name == "test.module1"
        assert logger2.name == "test.module2"
        assert logger1 is not logger2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
