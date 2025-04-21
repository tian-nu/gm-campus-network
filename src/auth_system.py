import os
import re
import time
import json
import requests
import socket
from urllib.parse import unquote, urlparse, parse_qs, urljoin
from bs4 import BeautifulSoup


class AuthManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, logger=None):
        self.session = requests.Session()
        self.logger = logger or (lambda msg: print(f"[Auth] {msg}"))
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive'
        })

    def _log(self, message: str):
        self.logger(f"{time.strftime('%H:%M:%S')} {message}")

    def _safe_request(self, method: str, url: str, **kwargs):
        """增强型网络请求，解决超时问题"""
        # 增加超时到15秒，添加代理支持
        timeout = kwargs.pop('timeout', 15)
        proxies = {
            'http': os.getenv('HTTP_PROXY'),
            'https': os.getenv('HTTPS_PROXY')
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                # 添加随机延迟防止频闪
                time.sleep(attempt * 0.5)

                resp = self.session.request(
                    method=method,
                    url=url,
                    timeout=timeout,
                    proxies=proxies,
                    allow_redirects=False,  # 手动处理重定向
                    **kwargs
                )

                # 处理特殊重定向
                if resp.status_code in (301, 302, 303, 307, 308):
                    new_url = resp.headers.get('Location')
                    if new_url.startswith('/'):
                        new_url = urljoin(url, new_url)
                    self._log(f"重定向至: {new_url}")
                    return self._safe_request('GET', new_url)

                resp.raise_for_status()
                return resp

            except (requests.Timeout, requests.ConnectionError) as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                delay = (attempt + 1) * 5  # 递增延迟：5,10,15秒
                self._log(f"网络错误 ({e}), {delay}秒后重试...")
                time.sleep(delay)

    def _decode_params(self, url: str) -> dict:
        """增强版参数解析，修复wlanacname缺失问题"""
        try:
            # 四重解码处理特殊编码
            decoded = unquote(unquote(unquote(unquote(url))))
            parsed = urlparse(decoded)

            # 精确提取关键参数
            params = {
                'wlanuserip': parse_qs(parsed.query).get('wlanuserip', [''])[0],
                'wlanacname': parse_qs(parsed.query).get('wlanacname', ['Ne8000-M14'])[0],  # 默认值
                'usermac': parse_qs(parsed.query).get('usermac', [''])[0]
            }

            # 处理特殊编码情况（如%3A转冒号）
            params['usermac'] = unquote(params['usermac']).replace('%3A', ':')
            return params
        except Exception as e:
            self._log(f"参数解析失败: {str(e)}")
            return {'wlanacname': 'Ne8000-M14'}  # 返回默认关键参数

    def _get_local_ip(self) -> str:
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
        except Exception:
            return '192.168.1.1'  # 默认值

    def _get_mac_address(self) -> str:
        """获取MAC地址"""
        try:
            from uuid import getnode
            mac = getnode()
            return ':'.join(("%012X" % mac)[i:i + 2] for i in range(0, 12, 2))
        except:
            return '00:00:00:00:00:00'  # 默认值

    def _extract_cas_params(self, html: str) -> dict:
        """改进的CAS参数提取"""
        params = {'lt': '', 'execution': ''}

        # 使用更健壮的正则表达式
        lt_pattern = r'<input\s+type="hidden"\s+name="lt"\s+value="([^"]+)"\s*/>'
        execution_pattern = r'<input\s+type="hidden"\s+name="execution"\s+value="([^"]+)"\s*/>'

        lt_match = re.search(lt_pattern, html, re.DOTALL)
        exec_match = re.search(execution_pattern, html, re.DOTALL)

        params['lt'] = lt_match.group(1) if lt_match else ''
        params['execution'] = exec_match.group(1) if exec_match else ''

        return params

    def _validate_params(self, params: dict) -> bool:
        """智能参数验证"""
        required = {
            'wlanuserip': r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
            'wlanacname': r'^[\w-]+$',
            'usermac': r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        }

        for key, pattern in required.items():
            value = params.get(key, '')
            if not re.match(pattern, str(value)):
                self._log(f"参数验证失败: {key}={value}")
                return False
        return True

    def login_flow(self, username: str, password: str) -> bool:
        try:
            # 清除旧会话
            self.session.cookies.clear()

            # 第一阶段：获取初始参数
            portal_res = self._safe_request('GET', "http://2.2.2.2")
            service_params = self._decode_params(portal_res.url)

            # 第二阶段：获取CAS票据
            cas_res = self._safe_request('GET', portal_res.url)
            tokens = self._extract_cas_params(cas_res.text)

            # 第三阶段：构建认证payload
            auth_payload = {
                'username': username,
                'password': password,
                'lt': tokens['lt'],
                'execution': tokens['execution'],
                '_eventId': 'submit',
                'submit': '登录',
                'loginType': '1',
                'vlan': '',
                'domain': '',
                'service': unquote(service_params.get('service', ''))
            }

            # 第四阶段：提交认证请求
            post_url = cas_res.url.replace('/login?', '/login;jsessionid=')  # 处理JSessionID
            post_res = self._safe_request('POST', post_url, data=auth_payload)

            # 第五阶段：处理重定向链
            if post_res.status_code == 302:
                redirect_url = post_res.headers['Location']
                final_res = self._safe_request('GET', redirect_url)

                # 验证最终结果
                if 'ticket=' in final_res.url or 'success' in final_res.text:
                    self._log("CAS认证成功")
                    return True

            # 错误处理
            error_msg = re.search(r'<div class="error">(.+?)</div>', final_res.text)
            if error_msg:
                self._log(f"认证失败: {error_msg.group(1)}")

            return False

        except Exception as e:
            self._log(f"认证流程异常: {str(e)}")
            return False

        except requests.RequestException as e:
            self._log(f"网络请求异常: {str(e)}")
            return False

    def _extract_fallback_params(self, html: str) -> dict:
        """使用更可靠的解析方式"""
        params = {}

        # 方法1：使用纯正则表达式
        acname_match = re.search(r'wlanacname\s*[:=]\s*["\']([^"\']+)["\']', html)
        if acname_match:
            params['wlanacname'] = acname_match.group(1)

        # 方法2：回退到标准HTML解析器
        try:
            soup = BeautifulSoup(html, 'html.parser')  # 使用内置解析器
            hidden_inputs = soup.find_all('input', {'type': 'hidden'})
            for inp in hidden_inputs:
                if inp.get('name') == 'wlanacname':
                    params['wlanacname'] = inp.get('value', '')
        except Exception as e:
            self._log(f"HTML解析失败: {str(e)}")

        return params

    def check_online(self) -> bool:
        """增强型在线检测"""
        test_urls = [
            'http://2.2.2.2/quickauth.do?action=check',
            'http://connect.rom.miui.com/generate_204',
            'http://www.qq.com'
        ]

        for url in test_urls:
            try:
                resp = self.session.get(url, timeout=5)
                if resp.status_code == 204:  # 特殊检测状态码
                    return True
                if 'success' in resp.text.lower():
                    return True
            except:
                continue
        return False