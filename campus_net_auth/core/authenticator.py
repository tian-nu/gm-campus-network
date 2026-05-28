"""
校园网认证器
负责 CAS 认证流程的核心逻辑
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urljoin

import requests

from .constants import Constants
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


class CampusNetAuthenticator:
    """校园网认证器"""

    def __init__(self, config: dict[str, object]):
        """
        初始化认证器

        Args:
            config: 配置字典
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # 创建请求会话
        self.session = requests.Session()
        self.session.headers.update(Constants.DEFAULT_HEADERS)
        # 禁用代理，避免因代理IP不一致导致封禁
        self.session.proxies = {"http": None, "https": None}
        # 禁用环境变量中的代理设置
        self.session.trust_env = False

        # 状态管理
        self.is_logged_in = False
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        # 使用占位值避免阻塞启动，实际值在 login() 中刷新
        self.network_info = {"ip": "10.0.0.1", "mac": "00:00:00:00:00:00", "timestamp": 0}

        # 计数器
        self.login_count = 0
        self.last_login_time: Optional[datetime] = None

    @property
    def timeout(self) -> int:
        """获取请求超时时间"""
        return self.config.get("timeout", Constants.DEFAULT_TIMEOUT)

    def detect_network_status(self) -> bool:
        """
        检测网络连通性（多URL并行检测 + portal优先检测）

        Returns:
            True 表示网络已连通，False 表示需要认证
        """
        import concurrent.futures

        session = self.session  # 使用已配置 trust_env=False 的 session

        # ===== 优先检测：portal 页面可达说明在校园网环境，需要认证 =====
        try:
            response = session.get(
                f"http://{Constants.PORTAL_IP}/portal.do",
                timeout=self.timeout,
                allow_redirects=False,
            )
            if response.status_code == 200 and "portalScript" in response.text:
                self.logger.debug("Portal 页面可达且包含认证脚本，需要认证")
                return False
        except Exception as e:
            self.logger.debug(f"检查 Portal 页面失败: {e}")

        def check_single_url(url: str) -> tuple:
            """检测单个URL

            Returns:
                (url, result, reason) 其中 result:
                - True:  确认连通
                - False: 确认需要认证
                - None:  HTTPS 返回 200 但在 captive portal 下不可靠，不计入投票
            """
            try:
                response = session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=False,
                )

                # 检查是否重定向到认证页面
                if response.status_code in [302, 307]:
                    location = response.headers.get("Location", "")
                    if Constants.PORTAL_IP in location or Constants.CAS_DOMAIN in location:
                        return (url, False, "redirect_to_portal")
                    # 任何 302/307 重定向都可能是 captive portal
                    return (url, False, f"redirect_{response.status_code}")

                # 204 无内容 — 最可靠的连通标志
                if response.status_code == 204:
                    return (url, True, "ok")

                # 200 需要验证不是 captive portal 假响应
                if response.status_code == 200:
                    ct = response.headers.get("Content-Type", "").lower()
                    # HTML 响应可能是 captive portal 页面
                    if "text/html" in ct:
                        return (url, False, "captive_portal_html")

                    # HTTPS URL 在 captive portal 下可能返回 200 但网络并未真正可用
                    # （校园网通常只劫持 HTTP，HTTPS 直接放行）
                    if url.startswith("https://"):
                        return (url, None, "https_unreliable")

                    # HTTP 返回非 HTML 200 — 可信的连通标志
                    return (url, True, "ok")

                return (url, False, f"status_{response.status_code}")

            except Exception as e:
                return (url, False, str(e))

        # 并行检测所有 URL
        http_success_count = 0   # HTTP 成功（可信）
        https_unreliable_count = 0  # HTTPS 200 但不可靠
        redirect_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(Constants.TEST_URLS)) as executor:
            futures = {executor.submit(check_single_url, url): url for url in Constants.TEST_URLS}
            
            for future in concurrent.futures.as_completed(futures, timeout=self.timeout + 2):
                try:
                    url, result, reason = future.result()
                    if result is True:
                        http_success_count += 1
                        self.logger.debug(f"HTTP检测成功: {url}")
                    elif result is None:
                        https_unreliable_count += 1
                        self.logger.debug(f"HTTPS返回200但不可靠: {url}")
                    elif reason == "redirect_to_portal":
                        redirect_count += 1
                        self.logger.debug(f"URL重定向到认证页面: {url}")
                    else:
                        self.logger.debug(f"URL检测失败: {url}, 原因: {reason}")
                except Exception as e:
                    self.logger.debug(f"URL检测异常: {e}")

        # 有任何重定向到认证页面的证据，直接认为需要认证
        if redirect_count > 0:
            return False

        # 只有 HTTP 请求成功才算可信（HTTPS 在 captive portal 下不可靠）
        # 至少 1 个 HTTP 成功即可判断连通
        if http_success_count >= 1:
            self.logger.info(f"网络已连通（HTTP成功: {http_success_count}, HTTPS不可靠: {https_unreliable_count}）")
            return True

        # 仅 HTTPS 返回 200，但无 HTTP 成功 — 很可能是 captive portal 放行了 HTTPS
        # 保守判断为需要认证
        if https_unreliable_count > 0 and http_success_count == 0:
            self.logger.info("仅HTTPS可达但HTTP不可达，可能是captive portal放行HTTPS，判断为需要认证")
            return False

        return False

    def login(self, username: str, password: str,
              force: bool = False) -> Tuple[bool, str]:
        """
        执行登录认证

        Args:
            username: 用户名（学号）
            password: 密码
            force: 强制认证，跳过"已连通"早期检查（重连服务使用）
        """
        self.username = username.strip()
        self.password = password.strip()
        self.login_count += 1

        self.logger.info(f"开始登录，用户: {self.username}，第 {self.login_count} 次")

        # 在首次登录前刷新网络信息（IP、MAC），在后台线程中不阻塞UI
        self._ensure_network_info()

        # 检查网络名称白名单
        if self.config.get("enable_network_whitelist", True):
            whitelist = self._parse_whitelist(
                self.config.get("network_name_whitelist", "")
            )
            if whitelist and not NetworkInfo.is_network_whitelisted(whitelist):
                self.logger.warning("当前网络不在白名单中，拒绝登录")
                return False, "当前网络不在白名单中，已跳过登录"

        # 先检查网络状态（手动/自动登录时提前返回，重连服务 force=True 跳过）
        if not force and self.detect_network_status():
            # 二次验证：尝试访问认证入口，如果 portal 还在说明 detect 误判
            try:
                verify_resp = self.session.get(
                    f"http://{Constants.PORTAL_IP}/portalScript.do",
                    timeout=self.timeout,
                    allow_redirects=False,
                )
                if verify_resp.status_code == 200 and "portalScript" in verify_resp.text:
                    self.logger.warning("detect_network_status 返回连通但 portal 仍可达，修正为需要认证")
                    # 不提前返回，继续走认证流程
                else:
                    self.logger.info("网络已连通，无需登录")
                    self.is_logged_in = True
                    self.last_login_time = datetime.now()
                    return True, "网络已连通"
            except Exception:
                # portal 不可达，确认网络确实已连通
                self.logger.info("网络已连通，无需登录")
                self.is_logged_in = True
                self.last_login_time = datetime.now()
                return True, "网络已连通"

        self.logger.info("开始认证流程")

        try:
            # 构建认证 URL
            auth_url = self._build_auth_url()
            self.logger.info(f"认证 URL: {auth_url}")

            # 访问认证页面
            response = self.session.get(
                auth_url,
                timeout=self.timeout,
                allow_redirects=False
            )
            current_url = str(response.url)

            # 处理 portalScript.do 页面
            if "portalScript.do" in current_url:
                response, is_banned = self._handle_portal_script(response, current_url)
                if is_banned:
                    return False, "账号已被封禁，服务器返回错误，请稍后再试"
                current_url = str(response.url)

            # 处理 CAS 登录页面
            if Constants.CAS_DOMAIN in current_url:
                return self._handle_cas_login(response, current_url)

            return False, f"未知的页面状态: {current_url}"

        except requests.exceptions.Timeout:
            self.logger.error("连接超时")
            return False, "连接超时，请检查网络"
        except requests.exceptions.ConnectionError:
            self.logger.error("连接错误")
            return False, "连接错误，请检查网络"
        except Exception as e:
            self.logger.error(f"登录过程出错: {e}", exc_info=True)
            return False, f"登录出错: {str(e)}"

    def _build_auth_url(self) -> str:
        """构建认证 URL"""
        params = {
            "wlanuserip": self.network_info["ip"],
            "wlanacname": Constants.WLAN_AC_NAME,
            "usermac": self.network_info["mac"],
        }
        return f"http://{Constants.PORTAL_IP}/portalScript.do?{urlencode(params)}"

    def _handle_portal_script(self, response: requests.Response, current_url: str) -> Tuple[requests.Response, bool]:
        """处理 portalScript.do 页面

        Returns:
            (response, is_banned) 元组，is_banned 表示是否检测到服务器错误（封禁）
        """
        self.logger.info("在 portalScript.do 页面，准备单点登录")

        # 提取参数
        parsed_url = urlparse(current_url)
        params = parse_qs(parsed_url.query)

        # 构建单点登录 URL
        sso_params = {
            "wlanuserip": params.get("wlanuserip", [self.network_info["ip"]])[0],
            "wlanacname": params.get("wlanacname", [Constants.WLAN_AC_NAME])[0],
            "usermac": params.get("usermac", [self.network_info["mac"]])[0],
            "rand": str(int(time.time() * 1000))
        }

        sso_url = f"http://{Constants.PORTAL_IP}/portalCasAuth.do?{urlencode(sso_params)}"
        self.logger.info(f"单点登录 URL: {sso_url}")

        # 访问单点登录 URL
        response = self.session.get(
            sso_url,
            timeout=self.timeout,
            allow_redirects=False
        )

        # 检测服务器错误（通常表示账号被封禁）
        if self._is_server_error_banned(response.text):
            self.logger.warning("检测到服务器错误，账号可能被封禁")
            return response, True

        if response.status_code in [302, 303]:
            redirect_url = response.headers.get("Location", "")
            if redirect_url:
                self.logger.info(f"单点登录重定向: {redirect_url}")
                response = self.session.get(
                    redirect_url,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                # 检测重定向后的服务器错误
                if self._is_server_error_banned(response.text):
                    self.logger.warning("检测到服务器错误，账号可能被封禁")
                    return response, True

        return response, False

    def _is_server_error_banned(self, html: str) -> bool:
        """检测服务器错误页面是否表示封禁状态"""
        server_error_keywords = [
            "The server encountered an error and was unable to complete your request",
            "The server encountered an error",
            "server error",
            "服务器错误",
            "无法完成请求",
        ]

        html_lower = html.lower()
        for keyword in server_error_keywords:
            if keyword.lower() in html_lower:
                return True
        return False

    def _handle_cas_login(self, response: requests.Response, current_url: str) -> Tuple[bool, str]:
        """处理 CAS 登录页面"""
        self.logger.info("在 CAS 登录页面")

        # 提取表单字段
        form_fields = self._extract_form_fields(response.text)

        # 检查关键令牌
        if not form_fields.get("lt"):
            # 检查是否因封禁导致无法获取令牌
            if self._is_account_banned(response.text):
                ban_duration = self._get_ban_duration(response.text)
                return False, f"账号已被封禁，时长约为{ban_duration}分钟，请稍后再试"
            return False, "无法找到登录令牌(lt)"

        # 准备登录数据
        login_data = {
            "username": self.username,
            "password": self.password,
            "captcha": "",
            "warn": "true",
            "lt": form_fields["lt"],
            "execution": form_fields.get("execution", "e1s1"),
            "_eventId": form_fields.get("_eventId", "submit"),
            "submit": "登录"
        }

        # 添加其他字段
        for key, value in form_fields.items():
            if key not in login_data:
                login_data[key] = value

        # 记录提交数据（隐藏密码）
        log_data = {k: "***" if k == "password" else v for k, v in login_data.items()}
        self.logger.info(f"提交登录数据: {log_data}")

        # 提交登录
        response = self.session.post(
            current_url,
            data=login_data,
            timeout=self.timeout,
            allow_redirects=False
        )

        self.logger.info(f"登录提交状态码: {response.status_code}")

        # 处理重定向
        final_response = self._follow_redirects(response)
        final_url = str(final_response.url)

        # 检查登录结果
        if Constants.LOGOUT_PAGE in final_url:
            self.is_logged_in = True
            self.last_login_time = datetime.now()
            self.logger.info("认证成功！")

            # 验证网络连通性
            time.sleep(1)
            if self.detect_network_status():
                return True, "认证成功"
            else:
                time.sleep(2)
                if self.detect_network_status():
                    return True, "认证成功（网络稍后恢复）"
                return False, "认证成功但无法访问外网"
        else:
            # 提取错误信息
            error_msg = self._extract_error_message(final_response.text)
            
            # 检查是否被封禁
            if self._is_account_banned(final_response.text):
                ban_duration = self._get_ban_duration(final_response.text)
                return False, f"账号已被封禁，时长约为{ban_duration}分钟，请稍后再试"
                
            return False, error_msg or f"未跳转到 logout 页面，当前页面: {final_url}"

    def _extract_form_fields(self, html: str) -> dict:
        """提取表单字段"""
        fields = {}
        html = html.replace("\n", " ").replace("\r", "")

        # 匹配隐藏字段
        hidden_pattern = r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']'
        matches = re.findall(hidden_pattern, html, re.IGNORECASE)
        for name, value in matches:
            fields[name] = value

        # 确保关键字段存在
        if "execution" not in fields:
            fields["execution"] = "e1s1"
        if "_eventId" not in fields:
            fields["_eventId"] = "submit"

        # 单独提取 lt（关键令牌）
        if "lt" not in fields:
            lt_match = re.search(r'LT-[^"\'<>\s]+', html)
            if lt_match:
                fields["lt"] = lt_match.group(0)

        return fields

    def _follow_redirects(self, start_response: requests.Response, max_redirects: int = None) -> requests.Response:
        """跟随重定向链"""
        if max_redirects is None:
            max_redirects = Constants.MAX_REDIRECTS

        current_response = start_response
        redirect_count = 0

        while redirect_count < max_redirects:
            if current_response.status_code in [302, 303, 307]:
                redirect_url = current_response.headers.get("Location", "")
                if not redirect_url:
                    break

                self.logger.info(f"重定向 {redirect_count + 1}: {redirect_url}")

                # 处理相对路径
                if redirect_url.startswith("/"):
                    base_url = self._get_base_url(current_response.url)
                    redirect_url = urljoin(base_url, redirect_url)

                # 修复 URL 中的错误
                redirect_url = redirect_url.replace("vl an", "vlan")

                try:
                    current_response = self.session.get(
                        redirect_url,
                        timeout=self.timeout,
                        allow_redirects=False
                    )
                    redirect_count += 1
                except Exception as e:
                    self.logger.error(f"跟随重定向失败: {e}")
                    break
            else:
                break

        self.logger.info(f"重定向结束，最终 URL: {current_response.url}")
        return current_response

    def _get_base_url(self, current_url: str) -> str:
        """获取基础 URL"""
        if Constants.CAS_DOMAIN in current_url:
            return f"https://{Constants.CAS_DOMAIN}"
        elif Constants.PORTAL_DOMAIN in current_url:
            return f"http://{Constants.PORTAL_DOMAIN}"
        elif Constants.PORTAL_IP in current_url:
            return f"http://{Constants.PORTAL_IP}"
        return f"http://{Constants.PORTAL_DOMAIN}"

    def _extract_error_message(self, html: str) -> str:
        """提取错误信息"""
        error_patterns = [
            r'<div[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</div>',
            r'<span[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</span>',
            r'错误[：:]\s*([^<]+)',
            r'用户名或密码错误',
            r'认证失败',
        ]

        for pattern in error_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                msg = match.group(1).strip() if len(match.groups()) > 0 else match.group(0)
                return f"登录失败: {msg}"

        return ""

    def _is_account_banned(self, html: str) -> bool:
        """检查账号是否被封禁"""
        ban_keywords = [
            "封禁",
            "禁止登录",
            "限制登录",
            "频繁登录",
            "登录次数过多",
            "账户锁定",
            "账号锁定"
        ]
        
        for keyword in ban_keywords:
            if keyword in html:
                return True
        return False

    def _get_ban_duration(self, html: str) -> int:
        """从网页内容中提取封禁时长（分钟），默认返回30分钟"""
        # 尝试匹配类似"封禁30分钟"的文本
        ban_duration_pattern = r'封禁(\d+)分钟'
        match = re.search(ban_duration_pattern, html)
        if match:
            return int(match.group(1))
        return 30  # 默认30分钟

    @staticmethod
    def _parse_whitelist(whitelist_str: str) -> list:
        """
        解析白名单字符串为列表

        Args:
            whitelist_str: 逗号分隔的白名单字符串

        Returns:
            网络名称列表
        """
        if not whitelist_str:
            return []
        return [w.strip() for w in whitelist_str.split(",") if w.strip()]

    def _ensure_network_info(self) -> None:
        """刷新网络信息（IP/MAC），在 login() 中后台线程调用，不阻塞 UI"""
        try:
            self.network_info = NetworkInfo.get_network_info(self.config)
        except Exception as e:
            self.logger.warning(f"刷新网络信息失败: {e}，使用占位值")
            self.network_info = {
                "ip": "10.0.0.1", "mac": "00:00:00:00:00:00", "timestamp": 0
            }

    def update_config(self, new_config: dict) -> None:
        """更新配置（网络信息在 login() 中刷新，此处不阻塞）"""
        self.config.update(new_config)

    def reset_session(self) -> None:
        """重置会话"""
        self.session = requests.Session()
        self.session.headers.update(Constants.DEFAULT_HEADERS)
        # 禁用代理，避免因代理IP不一致导致封禁
        self.session.proxies = {"http": None, "https": None}
        self.session.trust_env = False
        self.is_logged_in = False
