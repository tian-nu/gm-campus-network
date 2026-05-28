"""网络白名单功能测试"""

from unittest.mock import Mock, patch

from campus_net_auth.config.defaults import AppConfig, DEFAULT_CONFIG
from campus_net_auth.utils.network_info import NetworkInfo
from campus_net_auth.core.authenticator import CampusNetAuthenticator


# ========== 配置测试 ==========

def test_default_config_contains_whitelist_settings():
    assert DEFAULT_CONFIG["enable_network_whitelist"] is True
    whitelist = DEFAULT_CONFIG["network_name_whitelist"]
    assert "GM-living" in whitelist
    assert "东1-living" in whitelist


def test_app_config_round_trip_preserves_whitelist():
    config = AppConfig.from_dict({
        "enable_network_whitelist": False,
        "network_name_whitelist": "foo,bar,baz",
    })
    assert config.enable_network_whitelist is False
    assert "foo" in config.network_name_whitelist
    assert config.to_dict()["network_name_whitelist"] == "foo,bar,baz"


# ========== get_connected_network_names 测试 ==========

def test_get_connected_network_names_returns_wifi_ssid():
    netsh_output = """
        Name                   : Wi-Fi
        State                  : connected
        SSID                   : \u4e1c1-living
        BSSID                  : aa:bb:cc:dd:ee:ff
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout=netsh_output, returncode=0)
        with patch.object(NetworkInfo, "_logger"):
            names = NetworkInfo.get_connected_network_names()
    
    assert "东1-living" in names


def test_get_connected_network_names_ignores_bssid():
    netsh_output = """
        State                  : connected
        BSSID                  : aa:bb:cc:dd:ee:ff
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout=netsh_output, returncode=0)
        with patch.object(NetworkInfo, "_logger"):
            names = NetworkInfo.get_connected_network_names()
    
    # BSSID line should not produce a name
    assert "" not in names


def test_get_connected_network_names_returns_interface_names():
    netsh_output = """
Admin State    State          Type           Interface Name
-------------------------------------------------------------------------
Enabled        Connected      Dedicated      以太网
Enabled        Connected      Dedicated      Ethernet
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout=netsh_output, returncode=0)
        with patch.object(NetworkInfo, "_logger"):
            names = NetworkInfo.get_connected_network_names()
    
    assert "以太网" in names or "Ethernet" in names


# ========== is_network_whitelisted 测试 ==========

def test_is_whitelisted_empty_list_allows_all():
    """空白名单应允许所有网络"""
    with patch.object(NetworkInfo, "get_connected_network_names", return_value={"任意网络"}):
        assert NetworkInfo.is_network_whitelisted([]) is True


def test_is_whitelisted_none_allows_all():
    """None 白名单应允许所有网络"""
    with patch.object(NetworkInfo, "get_connected_network_names", return_value={"任意网络"}):
        assert NetworkInfo.is_network_whitelisted(None) is True


def test_is_whitelisted_matching_ssid():
    """匹配的网络名称应通过"""
    with patch.object(NetworkInfo, "get_connected_network_names", return_value={"东1-living"}):
        assert NetworkInfo.is_network_whitelisted(["东1-living", "GM-living"]) is True


def test_is_whitelisted_case_insensitive():
    """大小写不敏感匹配"""
    with patch.object(NetworkInfo, "get_connected_network_names", return_value={"GM-LIVING"}):
        assert NetworkInfo.is_network_whitelisted(["gm-living"]) is True


def test_is_whitelisted_blocks_non_matching():
    """不匹配的网络应被阻止"""
    with patch.object(NetworkInfo, "get_connected_network_names", return_value={"Home-WiFi"}):
        assert NetworkInfo.is_network_whitelisted(["东1-living", "GM-living"]) is False


def test_is_whitelisted_empty_names_allows():
    """无法获取网络名称时保守允许"""
    with patch.object(NetworkInfo, "get_connected_network_names", return_value=set()):
        assert NetworkInfo.is_network_whitelisted(["东1-living"]) is True


# ========== _parse_whitelist 测试 ==========

def test_parse_whitelist_simple():
    result = CampusNetAuthenticator._parse_whitelist("a,b,c")
    assert result == ["a", "b", "c"]


def test_parse_whitelist_with_spaces():
    result = CampusNetAuthenticator._parse_whitelist(" a ,  b , c ")
    assert result == ["a", "b", "c"]


def test_parse_whitelist_empty():
    assert CampusNetAuthenticator._parse_whitelist("") == []
    assert CampusNetAuthenticator._parse_whitelist(",") == []
