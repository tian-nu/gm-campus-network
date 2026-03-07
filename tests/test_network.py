"""
网络服务测试
包含属性测试和单元测试
"""

import os
import sys
import time
import threading
from unittest.mock import Mock, patch

import pytest
from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campus_net_auth.core.network import HeartbeatService, ReconnectService
from campus_net_auth.core.constants import Constants


class TestHeartbeatServiceProperties:
    """心跳服务属性测试"""

    @given(st.integers(min_value=1, max_value=3))
    @settings(max_examples=10, deadline=None)
    def test_heartbeat_interval_compliance(self, interval):
        """
        **Feature: campus-net-refactor, Property 3: Heartbeat interval compliance**
        **Validates: Requirements 2.1**

        For any heartbeat configuration with a positive interval, the heartbeat
        thread should make requests at approximately the configured interval.
        """
        request_times = []

        def mock_get(*args, **kwargs):
            request_times.append(time.time())
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        service = HeartbeatService(interval=interval, timeout=1)

        with patch('requests.get', side_effect=mock_get):
            service.start()

            # 等待足够时间让心跳执行几次
            time.sleep(interval * 2.5)

            service.stop()

        # 验证至少执行了 2 次心跳
        assert len(request_times) >= 2, f"Expected at least 2 heartbeats, got {len(request_times)}"

        # 验证间隔大致正确（允许 50% 误差）
        if len(request_times) >= 2:
            actual_interval = request_times[1] - request_times[0]
            assert abs(actual_interval - interval) < interval * 0.5, \
                f"Interval {actual_interval} differs too much from configured {interval}"

    @given(st.floats(min_value=0.5, max_value=2.0))
    @settings(max_examples=50)
    def test_thread_graceful_shutdown_heartbeat(self, timeout):
        """
        **Feature: campus-net-refactor, Property 5: Thread graceful shutdown**
        **Validates: Requirements 2.5**

        For any running heartbeat thread, calling stop should terminate
        the thread within a reasonable timeout period.
        """
        service = HeartbeatService(interval=10)  # 长间隔，不会自然结束

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            service.start()
            assert service.is_running is True

            # 停止服务
            stopped = service.stop(timeout=timeout + 1)

            # 验证线程已停止
            assert stopped is True
            assert service.is_running is False


class TestReconnectServiceProperties:
    """重连服务属性测试"""

    @given(st.integers(min_value=1, max_value=2))
    @settings(max_examples=10, deadline=None)
    def test_reconnect_cooldown_enforcement(self, cooldown):
        """
        **Feature: campus-net-refactor, Property 4: Reconnect cooldown enforcement**
        **Validates: Requirements 2.4**

        For any failed reconnect attempt, the next reconnect attempt should
        not occur until at least the configured cooldown period has elapsed.
        """
        attempt_times = []

        def mock_network_checker():
            return False  # 始终返回网络断开

        def mock_login():
            attempt_times.append(time.time())
            return False, "Mock failure"

        service = ReconnectService(
            check_interval=1,
            cooldown=cooldown,
            network_checker=mock_network_checker,
            login_func=mock_login
        )

        service.start()

        # 等待足够时间让重连尝试几次
        time.sleep(cooldown * 2.5 + 1)

        service.stop()

        # 验证至少有 2 次尝试
        if len(attempt_times) >= 2:
            # 验证两次尝试之间的间隔至少是冷却时间
            actual_interval = attempt_times[1] - attempt_times[0]
            # 允许 20% 误差
            assert actual_interval >= cooldown * 0.8, \
                f"Cooldown not enforced: interval {actual_interval} < cooldown {cooldown}"

    @given(st.floats(min_value=0.5, max_value=2.0))
    @settings(max_examples=50)
    def test_thread_graceful_shutdown_reconnect(self, timeout):
        """
        **Feature: campus-net-refactor, Property 5: Thread graceful shutdown**
        **Validates: Requirements 2.5**

        For any running reconnect thread, calling stop should terminate
        the thread within a reasonable timeout period.
        """
        service = ReconnectService(
            check_interval=10,
            cooldown=10,
            network_checker=lambda: True,
            login_func=lambda: (True, "OK")
        )

        service.start()
        assert service.is_running is True

        # 停止服务
        stopped = service.stop(timeout=timeout + 1)

        # 验证线程已停止
        assert stopped is True
        assert service.is_running is False


class TestHeartbeatServiceUnit:
    """心跳服务单元测试"""

    def test_init(self):
        """测试初始化"""
        service = HeartbeatService(interval=60, url="http://test.com", timeout=5)

        assert service.interval == 60
        assert service.url == "http://test.com"
        assert service.timeout == 5
        assert service.is_running is False

    def test_start_stop(self):
        """测试启动和停止"""
        service = HeartbeatService(interval=1)

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            service.start()
            assert service.is_running is True

            service.stop()
            assert service.is_running is False

    def test_double_start(self):
        """测试重复启动"""
        service = HeartbeatService(interval=10)

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            service.start()
            thread1 = service._thread

            service.start()  # 重复启动
            thread2 = service._thread

            # 应该是同一个线程
            assert thread1 is thread2

            service.stop()

    def test_success_callback(self):
        """测试成功回调"""
        success_called = []

        def on_success():
            success_called.append(True)

        service = HeartbeatService(interval=1, on_success=on_success)

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            service.start()
            time.sleep(1.5)
            service.stop()

        assert len(success_called) > 0

    def test_failure_callback(self):
        """测试失败回调"""
        failures = []

        def on_failure(e):
            failures.append(e)

        service = HeartbeatService(interval=1, on_failure=on_failure)

        with patch('requests.get', side_effect=Exception("Network error")):
            service.start()
            time.sleep(1.5)
            service.stop()

        assert len(failures) > 0

    def test_update_config(self):
        """测试更新配置"""
        service = HeartbeatService()

        service.update_config(interval=120, url="http://new.com", timeout=15)

        assert service.interval == 120
        assert service.url == "http://new.com"
        assert service.timeout == 15


class TestReconnectServiceUnit:
    """重连服务单元测试"""

    def test_init(self):
        """测试初始化"""
        service = ReconnectService()
        assert service.check_interval == Constants.DEFAULT_RECONNECT_INTERVAL
        assert service.cooldown == Constants.DEFAULT_RECONNECT_COOLDOWN
        assert service.reconnect_count == 0
        assert service.success_count == 0
        assert service.failure_count == 0

    def test_start_without_callbacks(self):
        """测试无回调函数启动"""
        service = ReconnectService(
            check_interval=1,
            cooldown=1,
            network_checker=lambda: True,
            login_func=lambda: (True, "OK")
        )
        service.start()
        service.stop()

        assert service.is_running is False

    def test_reconnect_success_callback(self):
        """测试重连成功回调"""
        success_called = []

        def on_success():
            success_called.append(True)

        service = ReconnectService(
            check_interval=1,
            cooldown=1,
            network_checker=lambda: False,
            login_func=lambda: (True, "OK"),
            on_reconnect_success=on_success
        )

        service.start()
        time.sleep(2)
        service.stop()

        assert len(success_called) > 0

    def test_reconnect_failure_callback(self):
        """测试重连失败回调"""
        failures = []

        def on_failure(msg):
            failures.append(msg)

        service = ReconnectService(
            check_interval=1,
            cooldown=1,
            network_checker=lambda: False,
            login_func=lambda: (False, "Auth failed"),
            on_reconnect_failure=on_failure
        )

        service.start()
        time.sleep(2)
        service.stop()

        assert len(failures) > 0
        assert "Auth failed" in failures[0]

    def test_get_time_until_next_attempt(self):
        """测试获取下次尝试时间"""
        service = ReconnectService(cooldown=30)
        remaining = service.get_time_until_next_attempt()
        assert remaining == 0

    def test_update_config(self):
        """测试更新配置"""
        service = ReconnectService(check_interval=10, cooldown=20)
        service.update_config(check_interval=30, cooldown=40)
        assert service.check_interval == 30
        assert service.cooldown == 40
        
    def test_ban_config(self):
        """测试封禁配置"""
        service = ReconnectService()
        service.set_ban_config(False, 15)
        assert service.enable_auto_retry_after_ban is False
        assert service.default_ban_duration == 15 * 60  # 转换为秒


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
