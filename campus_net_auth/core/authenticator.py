"""
校园网认证器（Panabit RAAS 版）

2026-11 学校换掉了整套认证系统：华为 AC Portal + CAS 全部下线，
现在用的是 Panabit「RAAS 认证计费」+ 统一身份认证 SSO。

认证有两条路，按门户下发的配置自动选：

  1. 账号密码直连（``/api/public/auth/login``）
     一次 POST 搞定，但学校把 ``account_enable`` 关成了 0，
     所以大多数时候这条走不通。

  2. 统一身份认证 SSO（默认走这条）
     门户 → SSO 授权 → SSO 登录页表单 POST → 回调带 code →
     ``/api/public/oauth/query_user_info`` 换认证。
     SSO 登录页没有验证码，密码明文走 HTTPS，可以完全自动化。

两条路最终都要落到「这个 IP+MAC 被 RADIUS 放行」，
所以认证完统一用 ``/api/public/auth/info`` 复核，不信接口自己的返回值。
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlencode, urljoin, urlparse, parse_qs, quote

import requests

from .constants import Constants
from .crypto import encrypt_hex
from ..utils.network_info import NetworkInfo


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    message: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AuthError(Exception):
    """认证过程中的可预期错误（凭据错、账号锁定等），带上给用户看的文案"""


class CampusNetAuthenticator:
    """校园网认证器（Panabit RAAS）"""

    # 判定「密码需要改」的关键词。学校每 3 个月强制改密，SSO 侧用提示页拦截，
    # 页面文案不固定，多收几种说法；命中后统一产出 Constants.PASSWORD_EXPIRED_MARK。
    _EXPIRED_KEYWORDS = (
        "密码已过期", "密码过期", "密码已失效", "有效期已过",
        "请修改密码", "需要修改密码", "修改密码后", "首次登录",
    )

    @classmethod
    def _is_password_expired(cls, text: str) -> bool:
        """文案是否表示密码需要修改（过期 / 首次登录强制改密）"""
        if not text:
            return False
        return any(k in text for k in cls._EXPIRED_KEYWORDS)


    def __init__(self, config: dict):
        """
        初始化认证器

        Args:
            config: 配置字典
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        self.session = self._new_session()

        # 状态管理
        self.is_logged_in = False
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.network_info = NetworkInfo.get_network_info(config)

        # 门户能力缓存（account_enable / oauth_enable），认证前刷新一次
        self._portal_caps: Optional[dict] = None

        # 计数器
        self.login_count = 0
        self.last_login_time: Optional[datetime] = None
        self.last_login_method: str = ""

    # ------------------------------------------------------------------ 基础

    def _new_session(self) -> requests.Session:
        """新建会话。禁用代理，避免出口 IP 与认证 IP 不一致被判作弊。"""
        s = requests.Session()
        s.headers.update(Constants.DEFAULT_HEADERS)
        s.proxies = {"http": None, "https": None}
        s.trust_env = False
        return s

    @property
    def timeout(self) -> int:
        return self.config.get("timeout", Constants.DEFAULT_TIMEOUT)

    def reset_session(self) -> None:
        """重置会话"""
        self.session = self._new_session()
        self._portal_caps = None
        self.is_logged_in = False

    def update_config(self, new_config: dict) -> None:
        """
        更新配置。

        这里不重新探测网卡——探测要跑 ipconfig，界面拖动设置项时会被卡住。
        真正的 IP/MAC 在 login() 里的 _device() 才刷新。
        """
        self.config.update(new_config)
        # 手工指定了 MAC 就立刻生效，方便宿舍里换了网卡对不上的情况
        if new_config.get("mac_address"):
            self.network_info["mac"] = new_config["mac_address"]

    # ------------------------------------------------------------------ 设备信息

    def _device(self, refresh: bool = True) -> dict:
        """
        取当前主用网卡的 IP / MAC。

        Returns:
            {"ip": "10.111.x.x", "mac": "aa-bb-cc-dd-ee-ff", "adapter": "以太网"}

        Raises:
            AuthError: 拿不到可用 IP（没连网 / 只拿到 169.254 自分配地址）
        """
        if refresh:
            self.network_info = NetworkInfo.get_network_info(self.config)

        ip = self.network_info.get("ip") or ""
        mac = self.network_info.get("mac") or ""
        adapter = self.network_info.get("adapter") or ""

        if not NetworkInfo.is_valid_ip(ip) or ip.startswith(("127.", "169.254.")):
            raise AuthError(
                "没有拿到有效的内网 IP（当前 %s）。请检查网线/WiFi 是否连上，"
                "如果显示 169.254.x.x 说明 DHCP 没拿到地址，重新插拔或等几秒。" % (ip or "空")
            )

        return {"ip": ip, "mac": self._normalize_mac(mac), "adapter": adapter}

    @staticmethod
    def _normalize_mac(mac: str) -> str:
        """
        统一 MAC 成 ``aa-bb-cc-dd-ee-ff``。

        服务端只认带分隔符的写法，写成 aabbccddeeff 会被解析成空，
        然后表现为"设备不认识"——排查起来很费劲，所以这里强制规范化。
        """
        hexonly = re.sub(r"[^0-9a-fA-F]", "", mac or "").lower()
        if len(hexonly) != 12:
            return ""
        return "-".join(hexonly[i:i + 2] for i in range(0, 12, 2))

    # ------------------------------------------------------------------ HTTP

    def _api_get(self, path: str, params: dict = None) -> dict:
        """GET 门户接口，返回 JSON dict"""
        url = Constants.API_BASE + path
        resp = self.session.get(url, params=params, timeout=self.timeout)
        return self._parse_json(resp, url)

    def _api_post(self, path: str, data: dict) -> dict:
        """POST 门户接口（form-urlencoded），返回 JSON dict"""
        url = Constants.API_BASE + path
        resp = self.session.post(url, data=data, timeout=self.timeout)
        return self._parse_json(resp, url)

    def _parse_json(self, resp: requests.Response, url: str) -> dict:
        try:
            payload = resp.json()
        except ValueError:
            snippet = (resp.text or "")[:200].replace("\n", " ")
            raise AuthError("接口 %s 返回的不是 JSON（HTTP %s）：%s"
                            % (url, resp.status_code, snippet))
        if not isinstance(payload, dict):
            raise AuthError("接口 %s 返回结构异常：%r" % (url, payload))
        return payload

    # ------------------------------------------------------------------ 状态查询

    def query_status(self, ip: str = None, mac: str = None) -> Optional[dict]:
        """
        查当前设备在服务端的在线状态。

        Returns:
            在线返回 stats 字典（含 username / session_time / tx / rx 等），
            未在线返回 None，接口异常也返回 None。
        """
        try:
            if ip is None or mac is None:
                dev = self._device()
                ip, mac = dev["ip"], dev["mac"]
            payload = self._api_get(Constants.EP_STATUS, {"ip": ip, "mac": mac})
        except AuthError:
            return None
        except requests.RequestException as e:
            self.logger.debug("查询在线状态失败: %s", e)
            return None

        data = payload.get("data")
        if isinstance(data, dict) and data.get("online"):
            return data
        return None

    def detect_network_status(self) -> bool:
        """
        检测网络是否可用（已认证 / 免认证放通都算 True）。

        判定顺序：
          1. 门户说这台设备在线 → 直接 True（最权威，不依赖公网）
          2. 门户连不上但公网通 → True（可能走了免认证放通）
          3. 都不行 → False

        Returns:
            True 表示网络已连通，False 表示需要认证
        """
        status = self.query_status()
        if status:
            self.is_logged_in = True
            return True

        # 门户说没在线，再用公网探一下：有些时段是免认证放通的
        for url in Constants.TEST_URLS:
            try:
                resp = self.session.get(url, timeout=min(self.timeout, 5),
                                        allow_redirects=False)
                if resp.status_code in (200, 204):
                    return True
                # 被重定向到门户 = 需要认证
                if resp.status_code in (301, 302, 307, 308):
                    location = resp.headers.get("Location", "")
                    if "xskd.gzittc.edu.cn" in location or "oauth.gzittc.edu.cn" in location:
                        return False
            except requests.RequestException:
                continue

        return False

    # ------------------------------------------------------------------ 门户能力

    def _portal_capabilities(self, dev: dict = None) -> dict:
        """拉一次门户配置，判断账号密码登录 / SSO 分别开没开"""
        if self._portal_caps is not None:
            return self._portal_caps

        caps = {"account_enable": True, "oauth_enable": True, "raw": {}}
        try:
            if dev is None:
                dev = self._device()
            payload = self._api_get(Constants.EP_CONF, {
                "ip": dev["ip"], "mac": dev["mac"], "vlan": "0.0",
            })
            cfg = ((payload.get("data") or {}).get("config") or {})
            caps["raw"] = cfg
            if "account_enable" in cfg:
                caps["account_enable"] = bool(int(cfg.get("account_enable") or 0))
            if "oauth_enable" in cfg:
                caps["oauth_enable"] = bool(int(cfg.get("oauth_enable") or 0))
            self.logger.info("门户登录方式：账号密码=%s，统一身份认证=%s",
                             "开" if caps["account_enable"] else "关",
                             "开" if caps["oauth_enable"] else "关")
        except (AuthError, requests.RequestException, ValueError, TypeError) as e:
            # 拉不到配置不致命，两条路都试一遍即可
            self.logger.debug("拉取门户配置失败，按默认都尝试: %s", e)

        self._portal_caps = caps
        return caps

    # ------------------------------------------------------------------ 登录入口

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        执行登录认证。

        Args:
            username: 学号
            password: 密码

        Returns:
            (success, message) 元组
        """
        self.username = (username or "").strip()
        self.password = (password or "").strip()

        if not self.username or not self.password:
            return False, "账号或密码为空"

        self.login_count += 1
        self.logger.info("开始认证，用户 %s（第 %d 次）", self.username, self.login_count)

        try:
            dev = self._device()
        except AuthError as e:
            return False, str(e)

        self.logger.info("当前网卡 %s  IP=%s  MAC=%s",
                         dev["adapter"] or "?", dev["ip"], dev["mac"])

        # 已经在线就别重复认证，避免白白消耗一次 RADIUS 请求
        status = self.query_status(dev["ip"], dev["mac"])
        if status:
            self._mark_ok("已在线")
            return True, "设备已在线（%s），无需认证" % status.get("username", self.username)

        caps = self._portal_capabilities(dev)
        errors = []

        # ---- 路线 1：账号密码直连
        if caps["account_enable"]:
            ok, msg = self._login_by_account(dev)
            if ok:
                self._mark_ok("账号密码")
                return True, msg
            errors.append("账号密码登录：%s" % msg)
            self.logger.warning("账号密码登录失败：%s", msg)
        else:
            self.logger.info("门户已关闭账号密码登录，跳过")

        # ---- 路线 2：统一身份认证
        if caps["oauth_enable"]:
            ok, msg = self._login_by_oauth(dev)
            if ok:
                self._mark_ok("统一身份认证")
                return True, msg
            errors.append("统一身份认证：%s" % msg)
            self.logger.warning("统一身份认证失败：%s", msg)
        else:
            errors.append("统一身份认证未开启")

        if not errors:
            return False, "门户没有开启任何可用的登录方式，请联系网络中心"

        joined = "；".join(errors)
        # 密码过期必须让上层明确看到标记：守护进程靠它停止无意义重试，
        # 用户也要知道该去统一身份认证改密码，而不是反复试密码。
        if any(self._is_password_expired(e) for e in errors):
            return False, "%s，请到统一身份认证修改密码后重试（%s）" % (
                Constants.PASSWORD_EXPIRED_MARK, joined)

        return False, joined

    def _mark_ok(self, method: str) -> None:
        self.is_logged_in = True
        self.last_login_time = datetime.now()
        self.last_login_method = method

    # ------------------------------------------------------------------ 路线 1

    def _login_by_account(self, dev: dict) -> Tuple[bool, str]:
        """
        账号密码直连认证。

        返回 code=2 / code=7 时说明这个账号绑了运营商宽带，需要再选一次
        「代拨账号」或「运营商」，第二次请求带上 id。
        """
        data = {
            "username": encrypt_hex(self.username),
            "password": encrypt_hex(self.password),
            "id": "",
            "code": "",
            "ip": dev["ip"],
            "mac": dev["mac"],
            "domain": "",
        }

        try:
            payload = self._api_post(Constants.EP_LOGIN, data)
        except AuthError as e:
            return False, str(e)
        except requests.RequestException as e:
            return False, "请求失败：%s" % e

        code = payload.get("code")
        msg = payload.get("msg") or ""

        if code == Constants.CODE_OK:
            return self._verify(dev, "账号密码")

        # 需要选代拨账号 / 运营商
        if code in (Constants.CODE_NEED_PROXY, Constants.CODE_NEED_ISP):
            endpoint = (Constants.EP_RADIUS_PROXY if code == Constants.CODE_NEED_PROXY
                        else Constants.EP_PORTAL_PROXY)
            options = payload.get("data") or []
            if not isinstance(options, list) or not options:
                return False, "服务端要求选择代拨账号，但没有返回可选列表"

            chosen = self._pick_proxy(options)
            if not chosen:
                return False, "代拨账号列表为空或没有可用项"

            self.logger.info("选择代拨账号：%s (id=%s)",
                             chosen.get("name") or chosen.get("account") or "?",
                             chosen.get("id"))
            data["id"] = chosen.get("id")
            try:
                payload = self._api_post(endpoint, data)
            except (AuthError, requests.RequestException) as e:
                return False, "代拨认证失败：%s" % e

            if payload.get("code") == Constants.CODE_OK:
                return self._verify(dev, "账号密码+代拨")
            return False, payload.get("msg") or "代拨认证失败"

        return False, self._explain_code(code, msg)

    def _pick_proxy(self, options: list) -> Optional[dict]:
        """
        从代拨账号里挑一个。

        优先用配置里指定的账号名，其次选电信（isp_id=1），
        否则取第一个——和网页上"只有一个账号时静默自动选择"的行为一致。
        """
        want = (self.config.get("proxy_account") or "").strip().lower()

        def name_of(item):
            return str(item.get("account") or item.get("name") or "").lower()

        if want:
            for item in options:
                if want in name_of(item):
                    return item

        for item in options:
            if str(item.get("isp_id")) == "1":
                return item

        return options[0]

    # ------------------------------------------------------------------ 路线 2

    def _build_authorize_url(self, dev: dict) -> str:
        """
        拼 SSO 授权地址。

        redirect_url 指回门户的 oauth.html 并带上本机的 IP/MAC——
        服务端就是靠这两个参数决定给谁放行的，缺一个都会认证到别人头上。
        """
        callback = "%s%s?%s" % (
            Constants.PORTAL_BASE, Constants.OAUTH_REDIRECT_PAGE,
            urlencode({"ip": dev["ip"], "mac": dev["mac"]}),
        )
        return "%s/sso/authorize?%s" % (Constants.SSO_BASE, urlencode({
            "client_id": Constants.OAUTH_CLIENT_ID,
            "redirect_url": callback,
            "response_type": "code",
            "state": Constants.OAUTH_STATE,
        }))

    def _login_by_oauth(self, dev: dict) -> Tuple[bool, str]:
        """
        走统一身份认证 SSO 完成认证。

        流程：
          1. GET /sso/authorize → 302 到 SSO 登录页
          2. 解析登录页的 __RequestVerificationToken
          3. POST 用户名/密码 → 302 到 /Sso/Auth2 → 302 回门户 /oauth.html?code=...
          4. 用 code 调 /oauth/query_user_info 换认证
        """
        authorize_url = self._build_authorize_url(dev)

        sso = requests.Session()
        sso.headers.update(Constants.SSO_HEADERS)
        sso.proxies = {"http": None, "https": None}
        sso.trust_env = False

        try:
            resp = sso.get(authorize_url, timeout=self.timeout, allow_redirects=True)
        except requests.RequestException as e:
            return False, "SSO 授权页打不开：%s" % e

        # 情况 A：SSO 会话还在，直接跳回门户并带上 code
        code = self._extract_code(resp.url)
        if code:
            self.logger.info("SSO 会话有效，直接拿到 code")
            return self._exchange_code(dev, code)

        # 情况 B：停在登录页，需要提交表单
        if "/Admin/User/Login" not in resp.url:
            return False, "SSO 未按预期跳转到登录页（当前 %s）" % resp.url

        token = self._extract_csrf(resp.text)
        if not token:
            return False, "SSO 登录页没找到 __RequestVerificationToken，页面结构可能变了"

        form_action = urljoin(resp.url, urlparse(resp.url).path + "?" + (urlparse(resp.url).query or ""))
        try:
            resp = sso.post(form_action, data={
                "username": self.username,
                "password": self.password,
                "remember": "true",
                "__RequestVerificationToken": token,
            }, timeout=self.timeout, allow_redirects=True)
        except requests.RequestException as e:
            return False, "SSO 登录请求失败：%s" % e

        code = self._extract_code(resp.url)
        if code:
            return self._exchange_code(dev, code)

        # 没拿到 code，说明密码错了或者账号状态异常
        return False, self._extract_sso_error(resp.text) or "SSO 登录未返回授权码（可能账号或密码错误）"

    def _exchange_code(self, dev: dict, code: str) -> Tuple[bool, str]:
        """用 SSO 的 code 换门户认证"""
        try:
            payload = self._api_get(Constants.EP_OAUTH_USER, {
                "code": code,
                "state": Constants.OAUTH_STATE,
                "ip": dev["ip"],
                "mac": dev["mac"],
                "domain": "",
            })
        except (AuthError, requests.RequestException) as e:
            return False, "用授权码换认证失败：%s" % e

        rc = payload.get("code")
        if rc == Constants.CODE_OK:
            return self._verify(dev, "统一身份认证")
        if rc == Constants.CODE_NO_PACKAGE:
            return False, "账号没有可用套餐，请先到自助中心购买"
        return False, payload.get("msg") or self._explain_code(rc, "")

    @staticmethod
    def _extract_code(url: str) -> str:
        """从回调 URL 里取 code 参数"""
        try:
            qs = parse_qs(urlparse(url).query)
        except Exception:
            return ""
        values = qs.get("code") or []
        return values[0] if values else ""

    @staticmethod
    def _extract_csrf(html: str) -> str:
        """从 SSO 登录页取防伪令牌"""
        m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
        if not m:
            m = re.search(r'value="([^"]+)"[^>]*name="__RequestVerificationToken"', html)
        return m.group(1) if m else ""

    @classmethod
    def _extract_sso_error(cls, html: str) -> str:
        """从 SSO 返回的 HTML 里抠出错误提示"""
        # 密码过期优先判：过期页既没有 validation-summary，也不一定带"错误/失败"字样，
        # 不先判就会掉到"账号或密码错误"的兜底文案，让用户白改一遍密码。
        plain = re.sub(r"<[^>]+>", " ", html or "")
        if cls._is_password_expired(plain):
            return "%s，请到统一身份认证修改密码后重试" % Constants.PASSWORD_EXPIRED_MARK

        patterns = [
            r'<div[^>]*class="[^"]*validation-summary-errors[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*field-validation-error[^"]*"[^>]*>(.*?)</span>',
            r'<li[^>]*>([^<]*(?:错误|失败|不存在|锁定|禁用)[^<]*)</li>',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, re.S)
            if m:
                text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                if text:
                    return "SSO 登录失败：%s" % text

        if "验证码" in html:
            return "SSO 要求输入验证码，无法自动登录，请手动登录一次"
        return ""

    # ------------------------------------------------------------------ 复核

    def _verify(self, dev: dict, method: str, retries: int = 3) -> Tuple[bool, str]:
        """
        认证完再问一次服务端，确认真的在线了。

        接口返回 code=0 不等于设备真的被放行（比如运营商侧没打通），
        所以以 /auth/info 的 online 为准。
        """
        for i in range(retries):
            time.sleep(1.0 + i)
            status = self.query_status(dev["ip"], dev["mac"])
            if status:
                self.logger.info("认证成功（%s），会话已建立", method)
                return True, "认证成功（%s）" % method

        return False, "认证接口返回成功，但设备仍未上线（可能被 2 台设备上限挤掉，或运营商侧未放通）"

    @staticmethod
    def _explain_code(code, msg: str) -> str:
        """把接口返回码翻译成人话"""
        if msg:
            return msg
        mapping = {
            1: "用户名或密码错误",
            3: "%s或首次登录，请先到统一身份认证修改密码" % Constants.PASSWORD_EXPIRED_MARK,
            4: "账号被锁定，请稍后再试",
            5: "认证次数过多，账号已被临时封禁，请稍后再试",
            6: "账号已欠费或未开通",
            8: "账号没有可用套餐",
        }
        return mapping.get(code, "认证失败（返回码 %s）" % code)

    # ------------------------------------------------------------------ 封禁 / 白名单

    @staticmethod
    def _is_account_banned(text: str) -> bool:
        """
        从服务端返回的文案里判断是不是「认证次数过多被临时封禁」。

        新系统把这类提示放在 JSON 的 msg 里（老系统是 HTML 错误块），
        所以这里只做纯文本匹配，不假设格式。
        """
        if not text:
            return False
        keywords = ("封禁", "禁止登录", "锁定", "次数过多", "暂时无法登录")
        return any(k in text for k in keywords)

    @staticmethod
    def _get_ban_duration(text: str, default_minutes: int = 30) -> int:
        """
        从提示文案里抠出封禁时长（分钟），抠不到用默认值。
        """
        if text:
            m = re.search(r"(\d+)\s*(?:分钟|min)", text)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
        return default_minutes

    @staticmethod
    def _parse_whitelist(raw: str) -> list:
        """把逗号分隔的白名单字符串拆成列表，忽略空项"""
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    # ------------------------------------------------------------------ 其它

    def logout(self) -> Tuple[bool, str]:
        """让服务端把当前设备下线（用于腾出 2 台设备名额）"""
        try:
            dev = self._device()
            payload = self._api_post("/auth/logout", {
                "ip": dev["ip"], "mac": dev["mac"], "domain": "",
            })
        except (AuthError, requests.RequestException) as e:
            return False, "注销失败：%s" % e

        if payload.get("code") == Constants.CODE_OK:
            self.is_logged_in = False
            return True, "已下线"
        return False, payload.get("msg") or "注销失败"

    def get_status_summary(self) -> dict:
        """给界面用的一行摘要"""
        dev = self.network_info or {}
        status = self.query_status()
        return {
            "ip": dev.get("ip"),
            "mac": dev.get("mac"),
            "adapter": dev.get("adapter"),
            "online": bool(status),
            "username": (status or {}).get("username"),
            "session_time": (status or {}).get("session_time"),
            "method": self.last_login_method,
        }
