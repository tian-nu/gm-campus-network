"""
认证器测试
包含属性测试和单元测试
"""

import os
import sys
from unittest.mock import Mock, patch, MagicMock

import pytest
from hypothesis import given, strategies as st, settings, assume

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campus_net_auth.core.authenticator import CampusNetAuthenticator, AuthResult
from campus_net_auth.config.defaults import DEFAULT_CONFIG


class TestAuthenticatorProperties:
    """认证器属性测试"""

    @given(st.booleans())
    @settings(max_examples=100)
    def test_network_detection_consistency(self, network_connected):
        """
        **Feature: campus-net-refactor, Property 1: Network detection consistency**
        **Validates: Requirements 1.2**

        For any network state, if the Authenticator detects the network as connected,
        then calling login should return early with a "network already connected" message.
        """
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        with patch.object(authenticator, 'detect_network_status', return_value=network_connected):
            if network_connected:
                # 网络已连通时，应该直接返回成功
                success, message = authenticator.login("test_user", "test_pass")
                assert success is True
                assert "网络已连通" in message or "已连通" in message
                assert authenticator.is_logged_in is True
            else:
                # 网络未连通时，会尝试认证（这里会失败因为没有真实服务器）
                # 我们只验证它不会返回"网络已连通"
                with patch.object(authenticator.session, 'get', side_effect=Exception("Mock error")):
                    success, message = authenticator.login("test_user", "test_pass")
                    assert "网络已连通" not in message

    @given(
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @settings(max_examples=100)
    def test_authentication_error_messages(self, username, password):
        """
        **Feature: campus-net-refactor, Property 2: Authentication error messages**
        **Validates: Requirements 1.3**

        For any authentication attempt with invalid credentials (simulated by mock),
        the Authenticator should return a tuple (False, message) where message
        contains a non-empty error description.
        """
        assume(len(username.strip()) > 0 and len(password.strip()) > 0)

        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        # 模拟网络未连通，且认证失败
        with patch.object(authenticator, 'detect_network_status', return_value=False):
            # 模拟请求返回错误页面
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.url = "https://cas.gzittc.com/login"
            mock_response.text = '<div class="error">用户名或密码错误</div>'
            mock_response.headers = {}

            with patch.object(authenticator.session, 'get', return_value=mock_response):
                with patch.object(authenticator.session, 'post', return_value=mock_response):
                    success, message = authenticator.login(username, password)

                    # 验证返回格式
                    assert isinstance(success, bool)
                    assert isinstance(message, str)

                    # 如果失败，消息应该非空
                    if not success:
                        assert len(message) > 0, "Error message should not be empty"


class TestAuthenticatorUnit:
    """认证器单元测试"""

    def test_init(self):
        """测试初始化"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        assert authenticator.is_logged_in is False
        assert authenticator.login_count == 0
        assert authenticator.username is None
        assert authenticator.password is None

    def test_timeout_property(self):
        """测试超时属性"""
        config = DEFAULT_CONFIG.copy()
        config["timeout"] = 20
        authenticator = CampusNetAuthenticator(config)

        assert authenticator.timeout == 20

    def test_update_config(self):
        """测试更新配置"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        new_config = {"timeout": 30, "mac_address": "aa:bb:cc:dd:ee:ff"}
        authenticator.update_config(new_config)

        assert authenticator.config["timeout"] == 30
        assert authenticator.network_info["mac"] == "aa:bb:cc:dd:ee:ff"

    def test_reset_session(self):
        """测试重置会话"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)
        authenticator.is_logged_in = True

        authenticator.reset_session()

        assert authenticator.is_logged_in is False

    def test_extract_form_fields(self):
        """测试提取表单字段"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        html = '''
        <form>
            <input type="hidden" name="lt" value="LT-12345-abcdef">
            <input type="hidden" name="execution" value="e1s1">
            <input type="hidden" name="_eventId" value="submit">
        </form>
        '''

        fields = authenticator._extract_form_fields(html)

        assert fields["lt"] == "LT-12345-abcdef"
        assert fields["execution"] == "e1s1"
        assert fields["_eventId"] == "submit"

    def test_extract_form_fields_missing_lt(self):
        """测试提取表单字段 - 缺少 lt 时从文本中查找"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        html = '''
        <script>var lt = "LT-67890-xyz";</script>
        '''

        fields = authenticator._extract_form_fields(html)

        assert fields["lt"] == "LT-67890-xyz"

    def test_extract_error_message(self):
        """测试提取错误信息"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        html = '<div class="error">用户名或密码错误</div>'
        error = authenticator._extract_error_message(html)

        assert "用户名或密码错误" in error

    def test_extract_error_message_no_error(self):
        """测试提取错误信息 - 无错误"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        html = '<div class="success">登录成功</div>'
        error = authenticator._extract_error_message(html)

        assert error == ""

    def test_build_auth_url(self):
        """测试构建认证 URL"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        url = authenticator._build_auth_url()

        assert "portalScript.do" in url
        assert "wlanuserip" in url
        assert "wlanacname" in url
        assert "usermac" in url

    def test_login_increments_count(self):
        """测试登录计数递增"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)

        with patch.object(authenticator, 'detect_network_status', return_value=True):
            authenticator.login("user1", "pass1")
            assert authenticator.login_count == 1

            authenticator.login("user2", "pass2")
            assert authenticator.login_count == 2


class TestAuthResult:
    """AuthResult 数据类测试"""

    def test_auth_result_success(self):
        """测试成功结果"""
        result = AuthResult(success=True, message="认证成功")

        assert result.success is True
        assert result.message == "认证成功"
        assert result.timestamp is not None

    def test_auth_result_failure(self):
        """测试失败结果"""
        result = AuthResult(success=False, message="用户名或密码错误")

        assert result.success is False
        assert result.message == "用户名或密码错误"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
