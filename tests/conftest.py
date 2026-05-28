"""pytest 全局 fixtures"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _mock_network_detection():
    """默认 mock：避免测试时真实的网络操作"""
    with patch("campus_net_auth.utils.network_info.NetworkInfo.get_network_info",
               return_value={"ip": "10.0.0.1", "mac": "00:00:00:00:00:00", "timestamp": 0}), \
         patch("campus_net_auth.utils.network_info.NetworkInfo.is_valid_ip",
               return_value=True), \
         patch("campus_net_auth.utils.network_info.NetworkInfo.is_valid_mac",
               return_value=True):
        yield
