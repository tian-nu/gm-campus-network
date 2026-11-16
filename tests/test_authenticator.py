"""
认证器测试

v3.0 学校换成了 Panabit RAAS + 统一身份认证，协议跟旧的 CAS 完全不同，
所以这里按新协议重写：不再测 HTML 表单解析，改成测 JSON 接口、
AES 加密、MAC 规范化、SSO 授权地址拼接等真正会出错的环节。
"""

import os
import sys
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st, settings, assume

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campus_net_auth.core.authenticator import CampusNetAuthenticator, AuthResult, AuthError
from campus_net_auth.core.constants import Constants
from campus_net_auth.core.crypto import (
    encrypt_hex, decrypt_hex, _expand_key, _encrypt_block,
)
from campus_net_auth.config.defaults import DEFAULT_CONFIG


class FakeResp:
    """够用的 requests.Response 替身"""

    def __init__(self, payload=None, status_code=200, url="", text=""):
        self._payload = payload
        self.status_code = status_code
        self.url = url
        self.text = text
        self.headers = {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def make_auth() -> CampusNetAuthenticator:
    return CampusNetAuthenticator(DEFAULT_CONFIG.copy())


DEV = {"ip": "10.111.49.247", "mac": "74-d4-dd-36-15-6c", "adapter": "以太网"}


# ====================================================================== 加密

class TestCrypto:
    """AES-128-ECB + ZeroPadding，和服务端 pa_aes_encode 必须逐字节一致"""

    def test_nist_fips197_vector(self):
        """NIST FIPS-197 标准向量，用来确认 AES 本身没写错"""
        key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
        plain = bytes.fromhex("00112233445566778899aabbccddeeff")
        cipher = _encrypt_block(plain, _expand_key(key))
        assert cipher.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"

    @given(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                   min_size=1, max_size=40))
    @settings(max_examples=50, deadline=None)
    def test_round_trip(self, text):
        """任何 ASCII 字符串加密再解密都应还原"""
        assert decrypt_hex(encrypt_hex(text)) == text

    def test_output_is_lowercase_hex(self):
        """服务端只认小写 hex，大写会解不出来"""
        out = encrypt_hex("abc")
        assert out == out.lower()
        assert len(out) % 32 == 0

    def test_padding_is_zero(self):
        """正好 16 字节时不额外补块（ZeroPadding 不是 PKCS#7）"""
        assert len(encrypt_hex("0123456789abcdef")) == 32

    def test_chinese_password(self):
        assert decrypt_hex(encrypt_hex("密码123")) == "密码123"


# ====================================================================== 单元

class TestAuthenticatorUnit:
    """认证器单元测试"""

    def test_init(self):
        auth = make_auth()
        assert auth.is_logged_in is False
        assert auth.login_count == 0
        assert auth.username is None
        assert auth.password is None

    def test_timeout_property(self):
        config = DEFAULT_CONFIG.copy()
        config["timeout"] = 20
        assert CampusNetAuthenticator(config).timeout == 20

    def test_update_config(self):
        auth = make_auth()
        auth.update_config({"timeout": 30, "mac_address": "aa:bb:cc:dd:ee:ff"})

        assert auth.config["timeout"] == 30
        assert auth.network_info["mac"] == "aa:bb:cc:dd:ee:ff"

    def test_update_config_without_mac_keeps_detected(self):
        """没指定 MAC 时不能把自动探测到的值冲掉"""
        auth = make_auth()
        before = auth.network_info["mac"]
        auth.update_config({"timeout": 15})
        assert auth.network_info["mac"] == before

    def test_reset_session(self):
        auth = make_auth()
        auth.is_logged_in = True
        auth._portal_caps = {"account_enable": False}

        auth.reset_session()

        assert auth.is_logged_in is False
        assert auth._portal_caps is None

    # ---------------------------------------------------------------- MAC

    @pytest.mark.parametrize("raw,expected", [
        ("74-D4-DD-36-15-6C", "74-d4-dd-36-15-6c"),
        ("74d4dd36156c", "74-d4-dd-36-15-6c"),
        ("74:d4:dd:36:15:6c", "74-d4-dd-36-15-6c"),
        ("", ""),
        ("abc", ""),
    ])
    def test_normalize_mac(self, raw, expected):
        """服务端只认 aa-bb-cc 写法，其它格式一律规范化"""
        assert CampusNetAuthenticator._normalize_mac(raw) == expected

    # ---------------------------------------------------------------- SSO

    def test_build_authorize_url(self):
        """授权地址必须把本机 IP/MAC 塞进 redirect_url，否则会认证到别人头上"""
        url = make_auth()._build_authorize_url(DEV)

        assert url.startswith(Constants.SSO_BASE + "/sso/authorize?")
        assert "client_id=" + Constants.OAUTH_CLIENT_ID in url
        assert "response_type=code" in url
        assert "ip%3D10.111.49.247" in url
        assert "mac%3D74-d4-dd-36-15-6c" in url

    @pytest.mark.parametrize("url,expected", [
        ("https://xskd.gzittc.edu.cn/oauth.html?ip=1.2.3.4&code=abc123", "abc123"),
        ("https://xskd.gzittc.edu.cn/oauth.html?code=xyz&state=OAUTH", "xyz"),
        ("https://oauth.gzittc.edu.cn/Admin/User/Login", ""),
        ("", ""),
    ])
    def test_extract_code(self, url, expected):
        assert CampusNetAuthenticator._extract_code(url) == expected

    @pytest.mark.parametrize("html,expected", [
        ('<input name="__RequestVerificationToken" type="hidden" value="tok123">', "tok123"),
        ('<input value="tok456" name="__RequestVerificationToken" />', "tok456"),
        ("<html><body>no token</body></html>", ""),
    ])
    def test_extract_csrf(self, html, expected):
        assert CampusNetAuthenticator._extract_csrf(html) == expected

    def test_extract_sso_error(self):
        html = '<div class="validation-summary-errors"><li>用户名或密码错误</li></div>'
        msg = CampusNetAuthenticator._extract_sso_error(html)
        assert "用户名或密码错误" in msg

    def test_extract_sso_error_captcha(self):
        """真出了验证码就必须老实报错，不能假装能自动登录"""
        msg = CampusNetAuthenticator._extract_sso_error("<div>请输入验证码</div>")
        assert "验证码" in msg

    def test_extract_sso_error_none(self):
        assert CampusNetAuthenticator._extract_sso_error("<div>ok</div>") == ""

    # ---------------------------------------------------------------- 密码过期

    @pytest.mark.parametrize("html", [
        '<div class="tip">您的密码已过期，请修改密码后继续</div>',
        "<p>密码有效期已过，请重新设置</p>",
        "<li>密码已失效，需要修改密码</li>",
    ])
    def test_extract_sso_error_password_expired(self, html):
        """SSO 的过期提示页必须被识别成"过期"，否则用户会以为是密码错"""
        msg = CampusNetAuthenticator._extract_sso_error(html)
        assert Constants.PASSWORD_EXPIRED_MARK in msg

    def test_extract_sso_error_wrong_password_not_expired(self):
        """密码真错了不能误判成过期，否则让用户白改一遍密码"""
        html = '<div class="validation-summary-errors"><li>用户名或密码错误</li></div>'
        assert Constants.PASSWORD_EXPIRED_MARK not in CampusNetAuthenticator._extract_sso_error(html)

    def test_explain_code_pwd_change_marks_expired(self):
        """code=3（首次登录/密码过期）必须带过期标记，守护进程靠它停重试"""
        msg = CampusNetAuthenticator._explain_code(3, "")
        assert Constants.PASSWORD_EXPIRED_MARK in msg

    def test_is_password_expired(self):
        assert CampusNetAuthenticator._is_password_expired("密码已过期") is True
        assert CampusNetAuthenticator._is_password_expired("用户名或密码错误") is False
        assert CampusNetAuthenticator._is_password_expired("") is False

    # ---------------------------------------------------------------- 代拨

    def test_pick_proxy_by_config(self):
        """配置指定了就按配置选，哪怕它不是电信"""
        config = DEFAULT_CONFIG.copy()
        config["proxy_account"] = "gzlan2637"
        auth = CampusNetAuthenticator(config)

        options = [
            {"id": 1, "account": "GZLAN2637019652", "isp_id": 1},
            {"id": 2, "account": "GZLAN9999000000", "isp_id": 2},
        ]
        assert auth._pick_proxy(options)["id"] == 1

    def test_pick_proxy_prefers_telecom(self):
        auth = make_auth()
        options = [
            {"id": 5, "account": "MOBILE-1", "isp_id": 2},
            {"id": 6, "account": "TELECOM-1", "isp_id": 1},
        ]
        assert auth._pick_proxy(options)["id"] == 6

    def test_pick_proxy_falls_back_to_first(self):
        auth = make_auth()
        options = [{"id": 9, "account": "X", "isp_id": 3}]
        assert auth._pick_proxy(options)["id"] == 9

    # ---------------------------------------------------------------- 文案

    def test_explain_code_prefers_server_message(self):
        assert CampusNetAuthenticator._explain_code(1, "密码错了") == "密码错了"

    def test_explain_code_maps_known(self):
        assert "密码" in CampusNetAuthenticator._explain_code(1, "")
        assert "套餐" in CampusNetAuthenticator._explain_code(8, "")

    def test_explain_code_unknown(self):
        assert "999" in CampusNetAuthenticator._explain_code(999, "")


# ====================================================================== 登录流程

class TestLoginFlow:
    """登录主流程：以 /auth/info 的 online 为准，不信接口自己的返回值"""

    def test_already_online_skips_login(self):
        """已在线就直接返回，不要白白消耗一次 RADIUS 请求"""
        auth = make_auth()

        with patch.object(auth, "query_status", return_value={"username": "23031901151"}):
            with patch.object(auth, "_login_by_oauth") as oauth:
                ok, msg = auth.login("23031901151", "pwd")

        assert ok is True
        assert "无需认证" in msg
        oauth.assert_not_called()

    def test_empty_credentials_rejected(self):
        ok, msg = make_auth().login("", "")
        assert ok is False
        assert "为空" in msg

    def test_oauth_used_when_account_login_disabled(self):
        """学校把 account_enable 关成 0，必须走 SSO"""
        auth = make_auth()

        with patch.object(auth, "query_status", return_value=None), \
             patch.object(auth, "_portal_capabilities",
                          return_value={"account_enable": False, "oauth_enable": True}), \
             patch.object(auth, "_login_by_oauth", return_value=(True, "认证成功（统一身份认证）")) as oauth, \
             patch.object(auth, "_login_by_account") as account:
            ok, msg = auth.login("23031901151", "pwd")

        assert ok is True
        oauth.assert_called_once()
        account.assert_not_called()

    def test_account_login_used_when_enabled(self):
        auth = make_auth()

        with patch.object(auth, "query_status", return_value=None), \
             patch.object(auth, "_portal_capabilities",
                          return_value={"account_enable": True, "oauth_enable": True}), \
             patch.object(auth, "_login_by_account", return_value=(True, "认证成功（账号密码）")), \
             patch.object(auth, "_login_by_oauth") as oauth:
            ok, _ = auth.login("23031901151", "pwd")

        assert ok is True
        oauth.assert_not_called()

    def test_both_routes_failing_reports_both(self):
        auth = make_auth()

        with patch.object(auth, "query_status", return_value=None), \
             patch.object(auth, "_portal_capabilities",
                          return_value={"account_enable": True, "oauth_enable": True}), \
             patch.object(auth, "_login_by_account", return_value=(False, "密码错误")), \
             patch.object(auth, "_login_by_oauth", return_value=(False, "SSO 挂了")):
            ok, msg = auth.login("23031901151", "pwd")

        assert ok is False
        assert "密码错误" in msg and "SSO 挂了" in msg

    def test_invalid_ip_raises_friendly_error(self):
        """拿到 169.254 自分配地址时要说人话，而不是抛异常"""
        auth = make_auth()
        bad = {"ip": "169.254.10.20", "mac": "74-d4-dd-36-15-6c", "timestamp": 0}

        with patch("campus_net_auth.utils.network_info.NetworkInfo.get_network_info",
                   return_value=bad):
            ok, msg = auth.login("23031901151", "pwd")

        assert ok is False
        assert "IP" in msg

    def test_login_increments_count(self):
        auth = make_auth()

        with patch.object(auth, "query_status", return_value={"username": "u"}):
            auth.login("u1", "p1")
            auth.login("u2", "p2")

        assert auth.login_count == 2

    def test_verify_rejects_code_zero_without_online(self):
        """接口说成功但设备没上线，不能报成功"""
        auth = make_auth()

        with patch.object(auth, "query_status", return_value=None), \
             patch("campus_net_auth.core.authenticator.time.sleep"):
            ok, msg = auth._verify(DEV, "账号密码", retries=2)

        assert ok is False
        assert "仍未上线" in msg

    def test_verify_accepts_online(self):
        auth = make_auth()

        with patch.object(auth, "query_status", return_value={"username": "u"}), \
             patch("campus_net_auth.core.authenticator.time.sleep"):
            ok, _ = auth._verify(DEV, "账号密码")

        assert ok is True


# ====================================================================== 属性测试

class TestAuthenticatorProperties:
    """认证器属性测试"""

    @given(st.booleans())
    @settings(max_examples=30, deadline=None)
    def test_online_always_returns_early_success(self, online):
        """
        只要服务端说这台设备在线，login 就必须立刻返回成功，
        不能再去打认证接口（否则会挤掉自己的会话）。
        """
        auth = make_auth()
        status = {"username": "23031901151"} if online else None

        with patch.object(auth, "query_status", return_value=status), \
             patch.object(auth, "_portal_capabilities",
                          return_value={"account_enable": False, "oauth_enable": True}), \
             patch.object(auth, "_login_by_oauth", return_value=(False, "认证失败")):
            ok, msg = auth.login("23031901151", "pwd")

        assert ok is online
        if online:
            assert "无需认证" in msg

    @given(
        st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N"))),
        st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N")))
    )
    @settings(max_examples=30, deadline=None)
    def test_error_messages_never_empty(self, username, password):
        """认证失败时必须有可读的提示，不能返回空字符串"""
        assume(username.strip() and password.strip())
        auth = make_auth()

        with patch.object(auth, "query_status", return_value=None), \
             patch.object(auth, "_portal_capabilities",
                          return_value={"account_enable": True, "oauth_enable": True}), \
             patch.object(auth, "_login_by_account", return_value=(False, "认证失败")), \
             patch.object(auth, "_login_by_oauth", return_value=(False, "认证失败")):
            ok, msg = auth.login(username, password)

        assert ok is False
        assert isinstance(msg, str) and len(msg) > 0


# ====================================================================== AuthResult

class TestAuthResult:
    """AuthResult 数据类测试"""

    def test_auth_result_success(self):
        result = AuthResult(success=True, message="认证成功")
        assert result.success is True
        assert result.message == "认证成功"
        assert result.timestamp is not None

    def test_auth_result_failure(self):
        result = AuthResult(success=False, message="用户名或密码错误")
        assert result.success is False
        assert result.message == "用户名或密码错误"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
