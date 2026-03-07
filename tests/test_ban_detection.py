"""
封禁检测功能测试
测试账号封禁检测和自动重试功能
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campus_net_auth.core.authenticator import CampusNetAuthenticator
from campus_net_auth.config.defaults import DEFAULT_CONFIG


class TestBanDetection:
    """封禁检测测试"""

    def test_is_account_banned_positive(self):
        """测试封禁检测 - 被封禁情况"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)
        
        # 模拟包含封禁关键词的HTML内容
        html_with_ban = """
        <html>
        <body>
        <div class="error">您的账号已被封禁30分钟，请稍后再试</div>
        </body>
        </html>
        """
        
        assert authenticator._is_account_banned(html_with_ban) is True

    def test_is_account_banned_negative(self):
        """测试封禁检测 - 未封禁情况"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)
        
        # 模拟正常的HTML内容
        normal_html = """
        <html>
        <body>
        <div class="success">登录成功</div>
        </body>
        </html>
        """
        
        assert authenticator._is_account_banned(normal_html) is False

    def test_get_ban_duration_with_match(self):
        """测试提取封禁时长 - 匹配到时长"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)
        
        html_with_duration = """
        <html>
        <body>
        <div class="error">您的账号已被封禁15分钟，请稍后再试</div>
        </body>
        </html>
        """
        
        duration = authenticator._get_ban_duration(html_with_duration)
        assert duration == 15

    def test_get_ban_duration_without_match(self):
        """测试提取封禁时长 - 未匹配到时长，使用默认值"""
        config = DEFAULT_CONFIG.copy()
        authenticator = CampusNetAuthenticator(config)
        
        html_without_duration = """
        <html>
        <body>
        <div class="error">您的账号已被封禁，请稍后再试</div>
        </body>
        </html>
        """
        
        duration = authenticator._get_ban_duration(html_without_duration)
        assert duration == 30  # 默认30分钟

if __name__ == "__main__":
    pytest.main([__file__, "-v"])