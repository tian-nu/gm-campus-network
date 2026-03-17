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
from ..utils.network_info import NetworkInfo, get_proxy_detector


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
        self.network_info = NetworkInfo.get_network_info(config)

        # 计数器
        self.login_count = 0
        self.last_login_time: Optional[datetime] = None

    @property
    def timeout(self) -> int:
        """获取请求超时时间"""
        return self.config.get("timeout", Constants.DEFAULT_TIMEOUT)

    def detect_network_status(self) -> bool:
        """
        检测网络连通性（多URL并行检测）

        Returns:
            True 表示网络已连通，False 表示需要认证
        """
        import concurrent.futures
        
        # 禁用代理，避免因代理IP不一致导致封禁
        no_proxy = {"http": None, "https": None}
        
        def check_single_url(url: str) -> tuple:
            """检测单个URL"""
            try:
                response = requests.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=False,
                    proxies=no_proxy
                )

                # 检查是否重定向到认证页面
                if response.status_code in [302, 307]:
                    location = response.headers.get("Location", "")
                    if Constants.PORTAL_IP in location or Constants.CAS_DOMAIN in location:
                        return (url, False, "redirect_to_portal")

                # 正常访问
                if response.status_code in [200, 204]:
                    return (url, True, "ok")

                return (url, False, f"status_{response.status_code}")

            except Exception as e:
                return (url, False, str(e))

        # 并行检测所有URL
        success_count = 0
        redirect_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(check_single_url, url): url for url in Constants.TEST_URLS}
            
            for future in concurrent.futures.as_completed(futures, timeout=self.timeout + 2):
                try:
                    url, success, reason = future.result()
                    if success:
                        success_count += 1
                        self.logger.debug(f"URL检测成功: {url}")
                    elif reason == "redirect_to_portal":
                        redirect_count += 1
                        self.logger.debug(f"URL重定向到认证页面: {url}")
                except Exception as e:
                    self.logger.debug(f"URL检测异常: {e}")

        # 多数投票机制：超过半数URL成功则认为网络正常
        if success_count >= len(Constants.TEST_URLS) // 2 + 1:
            return True

        # 检查认证页面状态
        try:
            response = self.session.get(
                f"http://{Constants.PORTAL_IP}/portal.do",
                timeout=self.timeout,
                allow_redirects=False,
                proxies=no_proxy
            )
            if response.status_code == 200 and "portalScript" in response.text:
                return False
        except Exception as e:
            self.logger.debug(f"检查认证页面失败: {e}")

        # 有重定向到认证页面，则认为需要认证
        if redirect_count > 0:
            return False

        return False

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        执行登录认证

        Args:
            username: 用户名（学号）
            password: 密码

        Returns:
            (success, message) 元组
        """
        self.username = username.strip()
        self.password = password.strip()
        self.login_count += 1

        self.logger.info(f"开始登录，用户: {self.username}，第 {self.login_count} 次")

        # 检查代理/VPN状态 - 如果检测到代理可能代理校园网，阻止登录
        if self.config.get("strict_proxy_check", True):
            proxy_detector = get_proxy_detector()
            should_block, block_reason = proxy_detector.should_block_campus_login()

            if should_block:
                self.logger.warning(f"检测到代理/VPN，阻止登录: {block_reason}")
                return False, f"🚫 检测到代理/VPN已开启\n\n{block_reason}\n\n请关闭代理后再登录校园网，否则可能导致账号被封禁！"

        # 先检查网络状态
        if self.detect_network_status():
            self.logger.info("网络已连通，无需登录")
            self.is_logged_in = True
            self.last_login_time = datetime.now()
            return True, "网络已连通"

        self.logger.info("网络未连通，开始认证流程")

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

    def update_config(self, new_config: dict) -> None:
        """更新配置"""
        self.config.update(new_config)
        self.network_info = NetworkInfo.get_network_info(self.config)

    def reset_session(self) -> None:
        """重置会话"""
        self.session = requests.Session()
        self.session.headers.update(Constants.DEFAULT_HEADERS)
        # 禁用代理，避免因代理IP不一致导致封禁
        self.session.proxies = {"http": None, "https": None}
        self.session.trust_env = False
        self.is_logged_in = False
