import re
import requests
from urllib.parse import unquote, urlparse, parse_qs
from bs4 import BeautifulSoup


class AuthManager:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0)',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'
        })

    def _decode_params(self, url: str) -> dict:
        """完善参数解析逻辑"""
        try:
            # 双重解码URL
            decoded_url = unquote(unquote(url))
            # 分割查询参数
            parsed = urlparse(decoded_url)
            return dict(parse_qs(parsed.query))
        except Exception as e:
            print(f"参数解析失败: {str(e)}")
            return {}

    def _get_cas_tokens(self, html: str) -> dict:
        """增强型令牌提取"""
        tokens = {'lt': '', 'execution': ''}
        try:
            # 方法1：使用BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            tokens['lt'] = soup.find('input', {'name': 'lt'})['value']
            tokens['execution'] = soup.find('input', {'name': 'execution'})['value']
        except Exception as e:
            print(f"BeautifulSoup提取失败: {str(e)}，尝试正则匹配")

        # 方法2：备用正则表达式
        if not tokens['lt']:
            lt_match = re.search(r'name=["\']lt["\']\s+value=["\']([^"\']+)["\']', html)
            tokens['lt'] = lt_match.group(1) if lt_match else ''
        if not tokens['execution']:
            execution_match = re.search(r'name=["\']execution["\']\s+value=["\']([^"\']+)["\']', html)
            tokens['execution'] = execution_match.group(1) if execution_match else ''

        return tokens

    def login_flow(self, username: str, password: str) -> bool:
        try:
            # ================= 第一阶段：初始化请求 =================
            init_res = self.session.get(
                "http://2.2.2.2",
                # https://cas.gzittc.com/lyuapServer/login
                # http://2.2.2.2"
                allow_redirects=True,
                timeout=10
            )
            print(f"初始化请求最终URL: {init_res.url}")

            # ================= 第二阶段：CAS认证 =================
            # 提取动态令牌
            tokens = self._get_cas_tokens(init_res.text)
            if not all(tokens.values()):
                raise ValueError("CAS参数提取失败，请检查页面结构")

            # 构造认证数据
            auth_data = {
                'username': username,
                'password': password,
                'lt': tokens['lt'],
                'execution': tokens['execution'],
                '_eventId': 'submit',
                'submit': '登录'  # 有些系统需要提交按钮值
            }

            # 获取表单提交地址
            form_action = self._get_form_action(init_res.text) or init_res.url

            # 提交认证请求
            cas_res = self.session.post(
                form_action,
                data=auth_data,
                allow_redirects=False
            )
            print(f"CAS认证状态码: {cas_res.status_code}")

            # ================= 第三阶段：处理重定向 =================
            if cas_res.status_code == 302:
                redirect_url = cas_res.headers['Location']
                print(f"重定向至: {redirect_url}")

                # 处理ST票据
                st_params = self._decode_params(redirect_url)
                print(f"解析的ST参数: {st_params}")

                # 构造最终认证请求
                final_url = "https://xykd.gzittc.edu.cn/portalCasAuth.do"
                # https://cas.gzittc.com/lyuapServer/login
                # https://xykd.gzittc.edu.cn/portalCasAuth.do
                final_params = {
                    'wlanuserip': st_params.get('wlanuserip', [''])[0],
                    'wlanacname': st_params.get('wlanacname', [''])[0],
                    'usermac': st_params.get('usermac', [''])[0],
                    'rand': st_params.get('rand', [''])[0],
                    'ticket': st_params.get('ticket', [''])[0]
                }
                print(f"最终请求参数: {final_params}")

                final_res = self.session.get(
                    final_url,
                    params=final_params,
                    allow_redirects=True
                )
                print(f"最终认证URL: {final_res.url}")

                # 处理可能的JavaScript跳转
                return self._handle_js_redirects(final_res)

            # 处理200状态码情况
            elif cas_res.status_code == 200:
                print("可能需要处理验证码或其他认证方式")
                return self._handle_special_case(cas_res)

            return False
        except Exception as e:
            print(f"[认证流程异常] {str(e)}")
            return False

    def _get_form_action(self, html: str) -> str:
        """提取表单提交地址"""
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form')
        return form['action'] if form and 'action' in form.attrs else None

    def _handle_js_redirects(self, response) -> bool:
        """处理多级JavaScript跳转"""
        redirect_count = 0
        current_html = response.text

        while redirect_count < 3:  # 防止无限循环
            redirect_url = re.search(r'location\.href\s*=\s*["\'](.*?)["\']', current_html)
            if not redirect_url:
                break

            print(f"处理JS跳转至: {redirect_url.group(1)}")
            new_res = self.session.get(redirect_url.group(1))
            current_html = new_res.text
            redirect_count += 1

        # 最终检查网络状态
        return self.check_session()

    def _handle_special_case(self, response):
        """处理特殊响应情况"""
        # 检查是否有验证码
        if 'captcha' in response.text:
            print("检测到验证码，需要人工处理")
            # 这里可以添加验证码处理逻辑
            return False

        # 检查是否有错误提示
        error_msg = re.search(r'<div class="error">(.*?)</div>', response.text)
        if error_msg:
            print(f"错误提示: {error_msg.group(1)}")

        return False

    def check_session(self) -> bool:
        """改进的会话检查"""
        test_urls = [
            "http://connect.rom.miui.com/generate_204",  # 小米检测地址
            "http://www.baidu.com",
            "http://2.2.2.2/status"
        ]

        for url in test_urls:
            try:
                resp = self.session.get(url, timeout=5)
                if resp.status_code in [204, 200]:
                    return True
            except:
                continue
        return False


