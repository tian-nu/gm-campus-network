import re
import time
import json
import requests
import socket
from urllib.parse import unquote, urlparse, parse_qs
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
        """增强型带重试机制的请求方法"""
        for attempt in range(self.MAX_RETRIES):
            try:
                # 添加随机参数防止缓存
                if method == 'GET' and '?' not in url:
                    url += f'?_={int(time.time() * 1000)}'
                elif method == 'GET':
                    url += f'&_={int(time.time() * 1000)}'

                resp = self.session.request(method, url,
                                            timeout=10,
                                            allow_redirects=False,
                                            **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                self._log(f"请求失败 ({e}), 第{attempt + 1}次重试...")
                time.sleep(self.RETRY_DELAY * (attempt + 1))

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
        """深度提取CAS参数（支持多种页面结构）"""
        params = {'lt': '', 'execution': ''}

        # 方法1：优先使用BeautifulSoup解析
        try:
            soup = BeautifulSoup(html, 'lxml')
            # 查找所有隐藏输入字段
            hidden_inputs = soup.find_all('input', type='hidden')
            for inp in hidden_inputs:
                if inp.get('name') == 'lt':
                    params['lt'] = inp.get('value', '')
                elif inp.get('name') == 'execution':
                    params['execution'] = inp.get('value', '')
        except Exception as e:
            self._log(f"BeautifulSoup解析失败: {str(e)}")

        # 方法2：正则表达式备选方案
        if not params['lt']:
            lt_patterns = [
                r'name="lt"\s+value="([^"]+)"',
                r'lt\s*=\s*["\']([^"\']+)["\']',
                r'<input.*?name="lt".*?value="(.*?)"'
            ]
            for pattern in lt_patterns:
                match = re.search(pattern, html, re.I)
                if match:
                    params['lt'] = match.group(1)
                    break

        if not params['execution']:
            exec_patterns = [
                r'name="execution"\s+value="([^"]+)"',
                r'execution\s*=\s*["\']([^"\']+)["\']',
                r'<input.*?name="execution".*?value="(.*?)"'
            ]
            for pattern in exec_patterns:
                match = re.search(pattern, html, re.I)
                if match:
                    params['execution'] = match.group(1)
                    break

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
            # 阶段0：清除旧会话
            self.session.cookies.clear()

            # 阶段1：获取portal参数（强制刷新）
            portal_res = self._safe_request('GET', "http://2.2.2.2")
            self._log(f"初始跳转URL: {portal_res.url}")

            # 阶段2：解析参数（带自动补全）
            service_params = self._decode_params(portal_res.url)
            self._log(f"解析参数: {json.dumps(service_params, indent=2)}")

            # 阶段2.5：从页面内容补充参数
            if not self._validate_params(service_params):
                fallback_params = self._extract_fallback_params(portal_res.text)
                service_params.update(fallback_params)
                self._log(f"补充后参数: {json.dumps(service_params, indent=2)}")

            # 阶段3：获取CAS页面
            cas_res = self._safe_request('GET', portal_res.url)
            tokens = self._extract_cas_params(cas_res.text)
            self._log(f"获取令牌: lt={tokens['lt'][:10]}... execution={tokens['execution'][:10]}...")

            # 阶段4：构造认证请求
            auth_payload = {
                'username': username,
                'password': password,
                'lt': tokens['lt'],
                'execution': tokens['execution'],
                '_eventId': 'submit',
                'submit': '登录',
                'loginType': '1',
                'vlan': '',
                'domain': ''
            }

            post_res = self._safe_request('POST',
                                          url=cas_res.url,
                                          data=auth_payload,
                                          headers={
                                              'Origin': urlparse(cas_res.url).scheme + '://' + urlparse(
                                                  cas_res.url).netloc,
                                              'Referer': cas_res.url
                                          }
                                          )

            # 阶段5：处理重定向链
            if post_res.status_code in [302, 307]:
                redirect_url = post_res.headers.get('Location', '')
                self._log(f"首次重定向至: {redirect_url}")

                # 自动跟随重定向
                final_res = self._safe_request('GET', redirect_url, allow_redirects=True)
                success_patterns = [
                    r'location\.href="http://www\.qq\.com"',  # 常见成功标识
                    r'认证成功',
                    r'login-success',
                    r'resultCode=1'
                ]

                for pattern in success_patterns:
                    if re.search(pattern, final_res.text, re.I):
                        self._log("最终认证成功")
                        return True

            # 错误处理
            error_patterns = {
                r'账号或密码错误': '密码错误',
                r'账号已欠费': '账号欠费',
                r'已达到最大会话数': '多设备登录',
                r'认证请求过于频繁': '操作频繁'
            }

            for pattern, msg in error_patterns.items():
                if re.search(pattern, post_res.text):
                    self._log(f"认证失败原因: {msg}")
                    return False

            return False

        except requests.RequestException as e:
            self._log(f"网络请求异常: {str(e)}")
            return False
        except Exception as e:
            self._log(f"未知错误: {str(e)}")
            return False

    def _extract_fallback_params(self, html: str) -> dict:
        """从页面内容提取备用参数"""
        params = {}

        # 方法1：解析JavaScript变量
        js_patterns = {
            'wlanuserip': r'wlanuserip\s*=\s*["\']([^"\']+)["\']',
            'wlanacname': r'wlanacname\s*=\s*["\']([^"\']+)["\']',
            'usermac': r'usermac\s*=\s*["\']([^"\']+)["\']'
        }

        for key, pattern in js_patterns.items():
            match = re.search(pattern, html)
            if match:
                params[key] = match.group(1)

        # 方法2：查找隐藏表单字段
        soup = BeautifulSoup(html, 'html.parser')
        for inp in soup.find_all('input', {'type': 'hidden'}):
            if inp['name'] in ['wlanuserip', 'wlanacname', 'usermac']:
                params[inp['name']] = inp['value']

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