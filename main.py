#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动认证工具 v1.5
修改关闭行为，添加真正的托盘图标
"""

import sys
import os
import json
import logging
import threading
import time
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import re
import socket
import uuid
from urllib.parse import urlparse, parse_qs, urlencode, urljoin

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('campus_net.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== 网络信息获取 ====================
class NetworkInfo:
    """网络信息获取"""

    @staticmethod
    def get_ip_address():
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            try:
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except:
                return "10.111.50.21"

    @staticmethod
    def get_mac_address():
        """获取本机MAC地址 - 使用学校记录的MAC"""
        return "74:d4:dd:36:15:6c"

    @staticmethod
    def get_network_info():
        """获取完整的网络信息"""
        return {
            'ip': NetworkInfo.get_ip_address(),
            'mac': NetworkInfo.get_mac_address(),
            'timestamp': int(time.time() * 1000)
        }


# ==================== 配置管理 ====================
class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file="config.json"):
        self.config_file = config_file

    def save(self, config: dict) -> bool:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def load(self) -> dict:
        """加载配置"""
        try:
            if not os.path.exists(self.config_file):
                return {}

            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {}


# ==================== 认证核心 ====================
class CampusNetAuthenticator:
    """校园网认证器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # 状态
        self.is_logged_in = False
        self.username = None
        self.password = None
        self.network_info = NetworkInfo.get_network_info()

        # 心跳相关
        self.heartbeat_interval = 120  # 心跳保持间隔（秒）
        self.reconnect_interval = 30  # 断线重连检测间隔（秒）
        self.heartbeat_thread = None
        self.reconnect_thread = None
        self.stop_heartbeat_flag = False
        self.stop_reconnect_flag = False

        # 登录计数器
        self.login_count = 0

    def detect_network_status(self) -> bool:
        """检测网络连通性"""
        test_urls = [
            "http://connectivitycheck.gstatic.com/generate_204",
            "http://www.baidu.com/favicon.ico",
            "http://www.qq.com/favicon.ico",
        ]

        for url in test_urls:
            try:
                response = requests.get(url, timeout=3, allow_redirects=False)
                # 检查是否被重定向到认证页面
                if response.status_code in [302, 307]:
                    location = response.headers.get('Location', '')
                    if '10.10.21.129' in location or 'cas.gzittc.com' in location:
                        return False
                # 正常访问
                if response.status_code in [200, 204]:
                    return True
            except:
                continue

        # 尝试访问portal.do检查是否已认证
        try:
            response = self.session.get("http://10.10.21.129/portal.do",
                                        timeout=3, allow_redirects=False)
            # 如果返回200，可能是未认证页面
            if response.status_code == 200:
                if 'portalScript' in response.text:
                    return False
        except:
            pass

        return False

    def get_auth_url(self):
        """获取认证URL"""
        try:
            # 直接构造portalScript.do URL
            params = {
                'wlanuserip': self.network_info['ip'],
                'wlanacname': 'Ne8000-M14',
                'usermac': self.network_info['mac'],
            }
            return f"http://10.10.21.129/portalScript.do?{urlencode(params)}"
        except Exception as e:
            logger.error(f"获取认证URL失败: {e}")
            return None

    def extract_form_fields(self, html: str) -> dict:
        """从HTML中提取表单字段"""
        fields = {}

        # 简化HTML
        html = html.replace('\n', ' ').replace('\r', '')

        # 查找所有隐藏字段
        hidden_patterns = [
            r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"',
            r"<input[^>]*type='hidden'[^>]*name='([^']+)'[^>]*value='([^']*)'",
        ]

        for pattern in hidden_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for name, value in matches:
                fields[name] = value

        # 特别查找关键字段
        for field in ['lt', 'execution', '_eventId']:
            patterns = [
                f'name="{field}"[^>]*value="([^"]+)"',
                f"name='{field}'[^>]*value='([^']+)'",
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    fields[field] = match.group(1)
                    break

        return fields

    def follow_redirects(self, start_response, max_redirects=10):
        """跟随重定向链 - 处理相对路径"""
        current_response = start_response
        redirect_count = 0

        while redirect_count < max_redirects:
            if current_response.status_code in [302, 303, 307, 200]:
                redirect_url = current_response.headers.get('Location', '')
                if not redirect_url:
                    break

                logger.info(f"重定向 {redirect_count + 1}: {redirect_url}")

                # 处理相对路径
                if redirect_url.startswith('/'):
                    if 'cas.gzittc.com' in current_response.url:
                        base_url = 'https://cas.gzittc.com'
                    elif 'xykd.gzittc.edu.cn' in current_response.url:
                        base_url = 'http://xykd.gzittc.edu.cn'
                    elif '10.10.21.129' in current_response.url:
                        base_url = 'http://10.10.21.129'
                    else:
                        base_url = 'http://xykd.gzittc.edu.cn'

                    redirect_url = urljoin(base_url, redirect_url)
                    logger.info(f"相对路径补全为: {redirect_url}")

                # 修复URL中的空格问题
                redirect_url = redirect_url.replace('vl an', 'vlan')

                # 访问重定向URL
                try:
                    current_response = self.session.get(redirect_url, timeout=10,
                                                        allow_redirects=False)
                    redirect_count += 1
                except Exception as e:
                    logger.error(f"跟随重定向失败: {e}")
                    break
            else:
                break

        logger.info(f"重定向结束，最终URL: {current_response.url}")
        return current_response

    def login(self, username: str, password: str):
        """执行登录"""
        self.username = username
        self.password = password

        try:
            self.login_count += 1
            logger.info(f"开始登录，用户: {username}，登录次数: {self.login_count}")

            # 首先检查网络状态
            network_ok = self.detect_network_status()
            if network_ok:
                logger.info("网络已连通，无需登录")
                self.is_logged_in = True
                return True, "网络已连通"

            logger.info("网络未连通，开始认证流程")

            # 获取认证URL
            auth_url = self.get_auth_url()
            if not auth_url:
                return False, "无法获取认证URL"

            logger.info(f"认证URL: {auth_url}")

            # 访问认证页面
            response = self.session.get(auth_url, timeout=10, allow_redirects=False)
            current_url = str(response.url)
            logger.info(f"当前URL: {current_url}")

            # 检查是否在portalScript.do页面
            if 'portalScript.do' in current_url:
                logger.info("在portalScript.do页面，准备单点登录")

                # 提取参数
                parsed_url = urlparse(current_url)
                params = parse_qs(parsed_url.query)

                # 构建单点登录URL
                sso_params = {
                    'wlanuserip': params.get('wlanuserip', [self.network_info['ip']])[0],
                    'wlanacname': params.get('wlanacname', ['Ne8000-M14'])[0],
                    'usermac': params.get('usermac', [self.network_info['mac']])[0],
                    'rand': str(int(time.time() * 1000))
                }

                sso_url = f"http://10.10.21.129/portalCasAuth.do?{urlencode(sso_params)}"
                logger.info(f"单点登录URL: {sso_url}")

                # 访问单点登录URL
                response = self.session.get(sso_url, timeout=10, allow_redirects=False)

                if response.status_code in [302, 303]:
                    redirect_url = response.headers.get('Location', '')
                    if redirect_url:
                        logger.info(f"单点登录重定向: {redirect_url}")
                        response = self.session.get(redirect_url, timeout=10, allow_redirects=True)
                        current_url = str(response.url)
                        logger.info(f"重定向后URL: {current_url}")

            # 检查是否在CAS页面
            if 'cas.gzittc.com' in current_url:
                logger.info("在CAS登录页面")

                # 提取表单字段
                form_fields = self.extract_form_fields(response.text)

                # 检查关键字段
                if not form_fields.get('lt'):
                    lt_match = re.search(r'LT-[^"\']+', response.text)
                    if lt_match:
                        form_fields['lt'] = lt_match.group(0)
                        logger.info(f"从页面提取到lt: {form_fields['lt']}")

                if not form_fields.get('execution'):
                    form_fields['execution'] = 'e1s1'
                    logger.info(f"使用默认execution: {form_fields['execution']}")

                if not form_fields.get('lt'):
                    return False, "无法找到登录令牌(lt)"

                # 准备登录数据
                login_data = {
                    'username': username,
                    'password': password,
                    'captcha': '',
                    'warn': 'true',
                    'lt': form_fields['lt'],
                    'execution': form_fields['execution'],
                    '_eventId': 'submit',
                    'submit': '登录'
                }

                # 添加其他字段
                for key, value in form_fields.items():
                    if key not in login_data:
                        login_data[key] = value

                # 记录提交数据（隐藏密码）
                log_data = {k: '***' if k == 'password' else v for k, v in login_data.items()}
                logger.info(f"提交登录数据: {log_data}")

                # 提交登录
                response = self.session.post(current_url, data=login_data,
                                             timeout=10, allow_redirects=False)

                logger.info(f"登录提交状态码: {response.status_code}")

                # 处理登录后的重定向
                # 为什么状态码200还是会进else分支？ 解决了
                if response.status_code in [302, 303, 200, '200']:
                    final_response = self.follow_redirects(response)
                    final_url = str(final_response.url)
                    logger.info(f"最终URL: {final_url}")

                    # 检查是否登录成功
                    if 'xykd.gzittc.edu.cn/portal/usertemp_computer/gongmao-pc-2025/logout.html' in final_url:
                        self.is_logged_in = True
                        logger.info("认证成功！")

                        # 验证网络连通性
                        time.sleep(1)
                        if self.detect_network_status():
                            logger.info("网络连通性验证通过")
                            return True, "认证成功"
                        else:
                            logger.warning("认证成功但网络连通性验证失败")
                            time.sleep(2)
                            if self.detect_network_status():
                                return True, "认证成功（网络稍后恢复）"
                            return False, "认证成功但无法访问外网"
                    else:
                        # 检查是否有错误信息
                        error_patterns = [
                            r'<div[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</div>',
                            r'<span[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</span>',
                            r'错误[：:]\s*([^<]+)',
                        ]

                        for pattern in error_patterns:
                            match = re.search(pattern, final_response.text, re.IGNORECASE)
                            if match:
                                error_msg = match.group(1).strip()
                                return False, f"登录失败: {error_msg}"

                        return False, f"未跳转到logout页面，当前页面: {final_url}"
                else:
                    return False, f"登录提交失败，状态码: {response.status_code}"

            return False, f"未知的页面状态: {current_url}"

        except requests.exceptions.Timeout:
            return False, "连接超时，请检查网络"
        except requests.exceptions.ConnectionError:
            return False, "连接错误，请检查网络"
        except Exception as e:
            logger.error(f"登录过程出错: {e}")
            import traceback
            with open('login_exception.txt', 'w', encoding='utf-8') as f:
                f.write(traceback.format_exc())
            return False, f"登录出错: {str(e)}"

    def start_heartbeat(self):
        """开始心跳保持 - 定期访问网站防止被踢下线"""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.stop_heartbeat()

        self.stop_heartbeat_flag = False

        def heartbeat_worker():
            while not self.stop_heartbeat_flag:
                try:
                    # 定期访问网站保持连接
                    try:
                        requests.get("http://www.baidu.com/favicon.ico", timeout=3)
                        logger.debug("心跳保持: 网络保持正常")
                    except:
                        logger.debug("心跳保持: 网络保持请求失败")

                    time.sleep(self.heartbeat_interval)

                except Exception as e:
                    logger.error(f"心跳保持出错: {e}")
                    time.sleep(self.heartbeat_interval)

        self.heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self.heartbeat_thread.start()
        logger.info(f"心跳保持已启动，间隔: {self.heartbeat_interval}秒")

    def start_reconnect(self):
        """开始断线重连检测 - 检测网络状态并在断开时重连"""
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            self.stop_reconnect()

        self.stop_reconnect_flag = False

        def reconnect_worker():
            last_login_attempt = 0
            login_cooldown = 30  # 登录冷却时间

            while not self.stop_reconnect_flag:
                try:
                    current_time = time.time()

                    # 检测网络状态
                    if not self.detect_network_status():
                        logger.warning("断线重连: 网络断开")

                        # 检查冷却时间
                        if current_time - last_login_attempt > login_cooldown:
                            if self.username and self.password:
                                logger.info("断线重连: 尝试重新登录")
                                last_login_attempt = current_time
                                success, message = self.login(self.username, self.password)
                                if success:
                                    logger.info("断线重连: 重新登录成功")
                                else:
                                    logger.error(f"断线重连: 重新登录失败: {message}")
                            else:
                                logger.warning("断线重连: 没有登录凭证，无法重新登录")
                    else:
                        # 每10次检测记录一次日志
                        if int(current_time) % 100 == 0:
                            logger.debug("断线重连: 网络正常")

                    time.sleep(self.reconnect_interval)

                except Exception as e:
                    logger.error(f"断线重连检测出错: {e}")
                    time.sleep(self.reconnect_interval)

        self.reconnect_thread = threading.Thread(target=reconnect_worker, daemon=True)
        self.reconnect_thread.start()
        logger.info(f"断线重连检测已启动，间隔: {self.reconnect_interval}秒")

    def stop_heartbeat(self):
        """停止心跳保持"""
        self.stop_heartbeat_flag = True
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        logger.info("心跳保持已停止")

    def stop_reconnect(self):
        """停止断线重连"""
        self.stop_reconnect_flag = True
        if self.reconnect_thread:
            self.reconnect_thread.join(timeout=5)
        logger.info("断线重连已停止")

    def stop_all(self):
        """停止所有后台服务"""
        self.stop_heartbeat()
        self.stop_reconnect()

    def set_heartbeat_interval(self, interval: int):
        """设置心跳保持间隔"""
        self.heartbeat_interval = interval
        logger.info(f"心跳保持间隔已设置为: {interval}秒")

    def set_reconnect_interval(self, interval: int):
        """设置断线重连检测间隔"""
        self.reconnect_interval = interval
        logger.info(f"断线重连检测间隔已设置为: {interval}秒")


# ==================== GUI界面 ====================
class ScrollableFrame:
    """可滚动的Frame"""

    def __init__(self, container, *args, **kwargs):
        # 创建Canvas和Scrollbar
        self.canvas = Canvas(container, *args, **kwargs)
        scrollbar = Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas)

        # 绑定滚动事件
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # 创建窗口
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # 绑定鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """处理鼠标滚轮事件"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def pack(self, **kwargs):
        """打包Canvas"""
        self.canvas.pack(**kwargs)


class CampusNetGUI:
    """校园网认证GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("校园网自动认证工具 v1.5")
        self.root.geometry("400x600")

        # 设置窗口图标
        try:
            if sys.platform == 'win32':
                self.root.iconbitmap(default='icon.ico')
        except:
            pass

        # 初始化认证器和配置管理器
        self.authenticator = CampusNetAuthenticator()
        self.config = ConfigManager()

        # 托盘图标状态
        self.tray_icon = None
        self.in_tray = False

        # 日志处理器
        self.log_handler = logging.Handler()
        self.log_handler.setLevel(logging.INFO)
        self.log_handler.emit = self.log_to_gui
        logging.getLogger().addHandler(self.log_handler)

        # 创建GUI
        self.create_widgets()

        # 加载配置
        self.load_config()

        # 设置定时器更新状态
        self.update_status()

        # 绑定关闭事件 - 直接退出，不弹窗
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        logger.info("校园网认证工具启动")

    def log_to_gui(self, record):
        """将日志输出到GUI"""
        try:
            msg = self.log_handler.format(record)
            if hasattr(self, 'log_text'):
                self.root.after(0, self.append_log, msg + "\n")
        except:
            pass

    def append_log(self, msg):
        """添加日志到文本框"""
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, msg)
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def create_widgets(self):
        """创建所有GUI控件"""
        # 创建标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 登录标签页
        self.create_login_tab()

        # 设置标签页（带滚动条）
        self.create_settings_tab()

        # 日志标签页
        self.create_log_tab()

    def create_login_tab(self):
        """创建登录标签页（简化版）"""
        login_tab = Frame(self.notebook)
        self.notebook.add(login_tab, text="登录")

        # 主框架
        main_frame = Frame(login_tab)
        main_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)

        # 标题
        title_label = Label(main_frame, text="校园网自动认证工具",
                            font=("Arial", 18, "bold"))
        title_label.pack(pady=(0, 30))

        # 账号信息框架
        cred_frame = Frame(main_frame)
        cred_frame.pack(fill=X, pady=(0, 20))

        # 学号
        Label(cred_frame, text="学号:", font=("Arial", 11)).grid(row=0, column=0, sticky=W, pady=10)
        self.username_var = StringVar()
        self.username_entry = Entry(cred_frame, textvariable=self.username_var,
                                    font=("Arial", 11), width=25)
        self.username_entry.grid(row=0, column=1, pady=10, padx=(10, 0))

        # 密码
        Label(cred_frame, text="密码:", font=("Arial", 11)).grid(row=1, column=0, sticky=W, pady=10)
        self.password_var = StringVar()
        self.password_entry = Entry(cred_frame, textvariable=self.password_var,
                                    show="*", font=("Arial", 11), width=25)
        self.password_entry.grid(row=1, column=1, pady=10, padx=(10, 0))

        # 登录按钮
        self.login_btn = Button(main_frame, text="一键登录", command=self.on_login,
                                font=("Arial", 12, "bold"), bg="#4CAF50", fg="white",
                                width=20, height=2)
        self.login_btn.pack(pady=10)

        # 最小化到托盘按钮
        self.tray_btn = Button(main_frame, text="最小化到托盘", command=self.minimize_to_tray,
                               font=("Arial", 10), bg="#2196F3", fg="white",
                               width=15, height=1)
        self.tray_btn.pack(pady=5)

        # 状态信息框架
        status_frame = LabelFrame(main_frame, text="系统状态", font=("Arial", 11),
                                  padx=15, pady=15)
        status_frame.pack(fill=X, pady=(10, 0))

        # 网络状态
        status_grid = Frame(status_frame)
        status_grid.pack(fill=X)

        Label(status_grid, text="网络状态:", font=("Arial", 10)).grid(row=0, column=0, sticky=W, pady=5)
        self.network_status_label = Label(status_grid, text="未知", fg="gray",
                                          font=("Arial", 10, "bold"))
        self.network_status_label.grid(row=0, column=1, sticky=W, pady=5, padx=(10, 0))

        # 登录状态
        Label(status_grid, text="登录状态:", font=("Arial", 10)).grid(row=1, column=0, sticky=W, pady=5)
        self.login_status_label = Label(status_grid, text="未登录", fg="gray",
                                        font=("Arial", 10, "bold"))
        self.login_status_label.grid(row=1, column=1, sticky=W, pady=5, padx=(10, 0))

        # 最后登录时间
        Label(status_grid, text="最后登录:", font=("Arial", 10)).grid(row=2, column=0, sticky=W, pady=5)
        self.last_login_label = Label(status_grid, text="无", font=("Arial", 10))
        self.last_login_label.grid(row=2, column=1, sticky=W, pady=5, padx=(10, 0))

        # 登录次数
        Label(status_grid, text="登录次数:", font=("Arial", 10)).grid(row=3, column=0, sticky=W, pady=5)
        self.login_count_label = Label(status_grid, text="0", font=("Arial", 10))
        self.login_count_label.grid(row=3, column=1, sticky=W, pady=5, padx=(10, 0))

        # 网络信息（IP和MAC）
        info_frame = Frame(status_frame)
        info_frame.pack(fill=X, pady=(10, 0))

        Label(info_frame, text="IP地址:", font=("Arial", 9)).pack(side=LEFT)
        self.ip_label = Label(info_frame, text=self.authenticator.network_info['ip'],
                              font=("Arial", 9), fg="blue")
        self.ip_label.pack(side=LEFT, padx=(5, 15))

        Label(info_frame, text="MAC地址:", font=("Arial", 9)).pack(side=LEFT)
        self.mac_label = Label(info_frame, text=self.authenticator.network_info['mac'],
                               font=("Arial", 9), fg="blue")
        self.mac_label.pack(side=LEFT, padx=(5, 0))

    def create_settings_tab(self):
        """创建设置标签页（带滚动条）"""
        settings_tab = Frame(self.notebook)
        self.notebook.add(settings_tab, text="设置")

        # 创建可滚动的Frame
        self.scrollable_frame = ScrollableFrame(settings_tab)

        # 获取滚动区域的内容Frame
        content_frame = self.scrollable_frame.scrollable_frame

        # 设置内容区域
        settings_content = Frame(content_frame, padx=20, pady=20)
        settings_content.pack(fill=BOTH, expand=True)

        # 标题
        title_label = Label(settings_content, text="设置选项",
                            font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # ==================== 启动设置 ====================
        startup_frame = LabelFrame(settings_content, text="启动设置",
                                   font=("Arial", 12, "bold"), padx=15, pady=15)
        startup_frame.pack(fill=X, pady=(0, 15))

        # 开机自启
        self.startup_var = BooleanVar()
        self.startup_cb = Checkbutton(startup_frame, text="开机自启",
                                      variable=self.startup_var,
                                      font=("Arial", 10))
        self.startup_cb.grid(row=0, column=0, sticky=W, pady=5)

        # 启动时自动登录
        self.auto_login_var = BooleanVar()
        self.auto_login_cb = Checkbutton(startup_frame, text="启动时自动登录",
                                         variable=self.auto_login_var,
                                         font=("Arial", 10))
        self.auto_login_cb.grid(row=1, column=0, sticky=W, pady=5)

        # ==================== 登录设置 ====================
        login_frame = LabelFrame(settings_content, text="登录设置",
                                 font=("Arial", 12, "bold"), padx=15, pady=15)
        login_frame.pack(fill=X, pady=(0, 15))

        # 记住密码
        self.remember_password_var = BooleanVar(value=True)
        self.remember_password_cb = Checkbutton(login_frame, text="记住密码",
                                                variable=self.remember_password_var,
                                                font=("Arial", 10))
        self.remember_password_cb.grid(row=0, column=0, sticky=W, pady=5)

        # 登录成功提示
        self.login_success_notify_var = BooleanVar(value=True)
        self.login_success_notify_cb = Checkbutton(login_frame, text="登录成功提示",
                                                   variable=self.login_success_notify_var,
                                                   font=("Arial", 10))
        self.login_success_notify_cb.grid(row=0, column=1, sticky=W, pady=5, padx=(20, 0))

        # 登录失败提示
        self.login_fail_notify_var = BooleanVar(value=True)
        self.login_fail_notify_cb = Checkbutton(login_frame, text="登录失败提示",
                                                variable=self.login_fail_notify_var,
                                                font=("Arial", 10))
        self.login_fail_notify_cb.grid(row=1, column=0, sticky=W, pady=5)

        # ==================== 网络设置 ====================
        network_frame = LabelFrame(settings_content, text="网络设置",
                                   font=("Arial", 12, "bold"), padx=15, pady=15)
        network_frame.pack(fill=X, pady=(0, 15))

        # 超时时间
        Label(network_frame, text="超时时间 (秒):", font=("Arial", 10)).grid(row=0, column=0, sticky=W, pady=5)
        self.timeout_var = IntVar(value=10)
        self.timeout_spin = Spinbox(network_frame, from_=5, to=60,
                                    textvariable=self.timeout_var,
                                    width=8, font=("Arial", 10))
        self.timeout_spin.grid(row=0, column=1, sticky=W, pady=5, padx=(10, 0))

        # 最大重试次数
        Label(network_frame, text="最大重试次数:", font=("Arial", 10)).grid(row=1, column=0, sticky=W, pady=5)
        self.max_retries_var = IntVar(value=3)
        self.max_retries_spin = Spinbox(network_frame, from_=1, to=10,
                                        textvariable=self.max_retries_var,
                                        width=8, font=("Arial", 10))
        self.max_retries_spin.grid(row=1, column=1, sticky=W, pady=5, padx=(10, 0))

        # ==================== 心跳保持设置 ====================
        heartbeat_frame = LabelFrame(settings_content, text="心跳保持设置",
                                     font=("Arial", 12, "bold"), padx=15, pady=15)
        heartbeat_frame.pack(fill=X, pady=(0, 15))

        # 启用心跳保持
        self.enable_heartbeat_var = BooleanVar(value=True)
        self.enable_heartbeat_cb = Checkbutton(heartbeat_frame, text="启用心跳保持",
                                               variable=self.enable_heartbeat_var,
                                               font=("Arial", 10))
        self.enable_heartbeat_cb.grid(row=0, column=0, sticky=W, pady=5)

        # 心跳保持间隔
        Label(heartbeat_frame, text="心跳间隔 (秒):", font=("Arial", 10)).grid(row=1, column=0, sticky=W, pady=5)
        self.heartbeat_interval_var = IntVar(value=120)
        self.heartbeat_interval_spin = Spinbox(heartbeat_frame, from_=30, to=600,
                                               textvariable=self.heartbeat_interval_var,
                                               width=8, font=("Arial", 10))
        self.heartbeat_interval_spin.grid(row=1, column=1, sticky=W, pady=5, padx=(10, 0))

        # 心跳目标网址
        Label(heartbeat_frame, text="心跳网址:", font=("Arial", 10)).grid(row=2, column=0, sticky=W, pady=5)
        self.heartbeat_url_var = StringVar(value="http://www.baidu.com/favicon.ico")
        self.heartbeat_url_entry = Entry(heartbeat_frame, textvariable=self.heartbeat_url_var,
                                         width=25, font=("Arial", 10))
        self.heartbeat_url_entry.grid(row=2, column=1, sticky=W, pady=5, padx=(10, 0))

        # ==================== 断线重连设置 ====================
        reconnect_frame = LabelFrame(settings_content, text="断线重连设置",
                                     font=("Arial", 12, "bold"), padx=15, pady=15)
        reconnect_frame.pack(fill=X, pady=(0, 15))

        # 启用断线重连
        self.enable_reconnect_var = BooleanVar(value=True)
        self.enable_reconnect_cb = Checkbutton(reconnect_frame, text="启用断线重连",
                                               variable=self.enable_reconnect_var,
                                               font=("Arial", 10))
        self.enable_reconnect_cb.grid(row=0, column=0, sticky=W, pady=5)

        # 重连检测间隔
        Label(reconnect_frame, text="检测间隔 (秒):", font=("Arial", 10)).grid(row=1, column=0, sticky=W, pady=5)
        self.reconnect_interval_var = IntVar(value=30)
        self.reconnect_interval_spin = Spinbox(reconnect_frame, from_=10, to=300,
                                               textvariable=self.reconnect_interval_var,
                                               width=8, font=("Arial", 10))
        self.reconnect_interval_spin.grid(row=1, column=1, sticky=W, pady=5, padx=(10, 0))

        # 重连冷却时间
        Label(reconnect_frame, text="冷却时间 (秒):", font=("Arial", 10)).grid(row=2, column=0, sticky=W, pady=5)
        self.reconnect_cooldown_var = IntVar(value=30)
        self.reconnect_cooldown_spin = Spinbox(reconnect_frame, from_=10, to=300,
                                               textvariable=self.reconnect_cooldown_var,
                                               width=8, font=("Arial", 10))
        self.reconnect_cooldown_spin.grid(row=2, column=1, sticky=W, pady=5, padx=(10, 0))

        # ==================== 高级设置 ====================
        advanced_frame = LabelFrame(settings_content, text="高级设置",
                                    font=("Arial", 12, "bold"), padx=15, pady=15)
        advanced_frame.pack(fill=X, pady=(0, 15))

        # 调试模式
        self.debug_mode_var = BooleanVar()
        self.debug_mode_cb = Checkbutton(advanced_frame, text="调试模式",
                                         variable=self.debug_mode_var,
                                         font=("Arial", 10))
        self.debug_mode_cb.grid(row=0, column=0, sticky=W, pady=5)

        # 详细日志
        self.verbose_log_var = BooleanVar(value=True)
        self.verbose_log_cb = Checkbutton(advanced_frame, text="详细日志",
                                          variable=self.verbose_log_var,
                                          font=("Arial", 10))
        self.verbose_log_cb.grid(row=0, column=1, sticky=W, pady=5, padx=(20, 0))

        # 自动清理日志
        self.auto_clean_log_var = BooleanVar(value=True)
        self.auto_clean_log_cb = Checkbutton(advanced_frame, text="自动清理日志",
                                             variable=self.auto_clean_log_var,
                                             font=("Arial", 10))
        self.auto_clean_log_cb.grid(row=1, column=0, sticky=W, pady=5)

        # 日志保留天数
        Label(advanced_frame, text="日志保留 (天):", font=("Arial", 10)).grid(row=1, column=1, sticky=W, pady=5,
                                                                              padx=(20, 0))
        self.log_retention_days_var = IntVar(value=7)
        self.log_retention_days_spin = Spinbox(advanced_frame, from_=1, to=30,
                                               textvariable=self.log_retention_days_var,
                                               width=8, font=("Arial", 10))
        self.log_retention_days_spin.grid(row=1, column=2, sticky=W, pady=5, padx=(10, 0))

        # ==================== 操作按钮 ====================
        button_frame = Frame(settings_content)
        button_frame.pack(fill=X, pady=(20, 10))

        # 保存设置按钮
        self.save_btn = Button(button_frame, text="保存设置", command=self.save_config,
                               font=("Arial", 11, "bold"), bg="#2196F3", fg="white",
                               width=15, height=2)
        self.save_btn.pack(side=LEFT, padx=(0, 10))

        # 恢复默认按钮
        self.reset_btn = Button(button_frame, text="恢复默认", command=self.reset_config,
                                font=("Arial", 11), width=15, height=2)
        self.reset_btn.pack(side=LEFT)

    def create_log_tab(self):
        """创建日志标签页"""
        log_tab = Frame(self.notebook)
        self.notebook.add(log_tab, text="日志")

        main_frame = Frame(log_tab)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(main_frame, wrap=WORD, width=80, height=25)
        self.log_text.pack(fill=BOTH, expand=True, pady=(0, 10))
        self.log_text.config(state=DISABLED)

        # 日志控制按钮
        button_frame = Frame(main_frame)
        button_frame.pack(fill=X)

        self.clear_log_btn = Button(button_frame, text="清空日志", command=self.clear_log, width=15)
        self.clear_log_btn.pack(side=LEFT, padx=(0, 10))

        self.save_log_btn = Button(button_frame, text="保存日志", command=self.save_log, width=15)
        self.save_log_btn.pack(side=LEFT, padx=(0, 10))

        self.open_log_btn = Button(button_frame, text="打开日志文件", command=self.open_log_file, width=15)
        self.open_log_btn.pack(side=LEFT)

    def load_config(self):
        """加载配置"""
        config = self.config.load()

        if config:
            # 账号信息
            self.username_var.set(config.get('username', ''))
            self.password_var.set(config.get('password', ''))

            # 启动设置
            self.startup_var.set(config.get('startup', False))
            self.auto_login_var.set(config.get('auto_login', False))

            # 登录设置
            self.remember_password_var.set(config.get('remember_password', True))
            self.login_success_notify_var.set(config.get('login_success_notify', True))
            self.login_fail_notify_var.set(config.get('login_fail_notify', True))

            # 网络设置
            self.timeout_var.set(config.get('timeout', 10))
            self.max_retries_var.set(config.get('max_retries', 3))

            # 心跳保持设置
            self.enable_heartbeat_var.set(config.get('enable_heartbeat', True))
            self.heartbeat_interval_var.set(config.get('heartbeat_interval', 120))
            self.heartbeat_url_var.set(config.get('heartbeat_url', 'http://www.baidu.com/favicon.ico'))

            # 断线重连设置
            self.enable_reconnect_var.set(config.get('enable_reconnect', True))
            self.reconnect_interval_var.set(config.get('reconnect_interval', 30))
            self.reconnect_cooldown_var.set(config.get('reconnect_cooldown', 30))

            # 高级设置
            self.debug_mode_var.set(config.get('debug_mode', False))
            self.verbose_log_var.set(config.get('verbose_log', True))
            self.auto_clean_log_var.set(config.get('auto_clean_log', True))
            self.log_retention_days_var.set(config.get('log_retention_days', 7))

            # 如果启用自动登录，自动开始
            if config.get('auto_login', False) and config.get('username') and config.get('password'):
                self.root.after(2000, self.auto_login)

    def save_config(self):
        """保存配置"""
        config = {
            # 账号信息
            'username': self.username_var.get(),
            'password': self.password_var.get() if self.remember_password_var.get() else '',

            # 启动设置
            'startup': self.startup_var.get(),
            'auto_login': self.auto_login_var.get(),

            # 登录设置
            'remember_password': self.remember_password_var.get(),
            'login_success_notify': self.login_success_notify_var.get(),
            'login_fail_notify': self.login_fail_notify_var.get(),

            # 网络设置
            'timeout': self.timeout_var.get(),
            'max_retries': self.max_retries_var.get(),

            # 心跳保持设置
            'enable_heartbeat': self.enable_heartbeat_var.get(),
            'heartbeat_interval': self.heartbeat_interval_var.get(),
            'heartbeat_url': self.heartbeat_url_var.get(),

            # 断线重连设置
            'enable_reconnect': self.enable_reconnect_var.get(),
            'reconnect_interval': self.reconnect_interval_var.get(),
            'reconnect_cooldown': self.reconnect_cooldown_var.get(),

            # 高级设置
            'debug_mode': self.debug_mode_var.get(),
            'verbose_log': self.verbose_log_var.get(),
            'auto_clean_log': self.auto_clean_log_var.get(),
            'log_retention_days': self.log_retention_days_var.get()
        }

        success = self.config.save(config)
        if success:
            # 静默保存，不弹窗提示
            logger.info("配置已保存")

            # 应用设置
            self.apply_settings()
        else:
            logger.error("配置保存失败")

    def reset_config(self):
        """恢复默认配置"""
        result = messagebox.askyesno("确认", "确定要恢复默认设置吗？")
        if result:
            # 清除所有设置
            self.username_var.set('')
            self.password_var.set('')

            # 启动设置默认值
            self.startup_var.set(False)
            self.auto_login_var.set(False)

            # 登录设置默认值
            self.remember_password_var.set(True)
            self.login_success_notify_var.set(True)
            self.login_fail_notify_var.set(True)

            # 网络设置默认值
            self.timeout_var.set(10)
            self.max_retries_var.set(3)

            # 心跳保持设置默认值
            self.enable_heartbeat_var.set(True)
            self.heartbeat_interval_var.set(120)
            self.heartbeat_url_var.set('http://www.baidu.com/favicon.ico')

            # 断线重连设置默认值
            self.enable_reconnect_var.set(True)
            self.reconnect_interval_var.set(30)
            self.reconnect_cooldown_var.set(30)

            # 高级设置默认值
            self.debug_mode_var.set(False)
            self.verbose_log_var.set(True)
            self.auto_clean_log_var.set(True)
            self.log_retention_days_var.set(7)

            # 保存默认配置
            self.save_config()
            logger.info("已恢复默认设置")
            messagebox.showinfo("成功", "已恢复默认设置")

    def apply_settings(self):
        """应用设置"""
        # 设置认证器参数
        self.authenticator.set_heartbeat_interval(self.heartbeat_interval_var.get())

        # 如果有断线重连设置，也需要应用
        if hasattr(self.authenticator, 'set_reconnect_interval'):
            self.authenticator.set_reconnect_interval(self.reconnect_interval_var.get())

        # 停止并重新启动服务
        if self.authenticator.is_logged_in:
            self.authenticator.stop_all()

            # 启动心跳保持
            if self.enable_heartbeat_var.get():
                self.authenticator.start_heartbeat()
                logger.info("心跳保持已启动")

            # 启动断线重连
            if self.enable_reconnect_var.get():
                self.authenticator.start_reconnect()
                logger.info("断线重连已启动")

    def on_login(self):
        """登录按钮点击事件"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showwarning("警告", "请输入账号和密码")
            return

        # 禁用按钮，防止重复点击
        self.login_btn.config(state=DISABLED, text="登录中...")

        # 在工作线程中执行登录
        threading.Thread(target=self.login_thread, args=(username, password), daemon=True).start()

    def login_thread(self, username, password):
        """登录线程"""
        try:
            success, message = self.authenticator.login(username, password)
            self.root.after(0, lambda: self.on_login_finished(success, message))
        except Exception as e:
            self.root.after(0, lambda: self.on_login_finished(False, f"登录异常: {str(e)}"))

    def on_login_finished(self, success, message):
        """登录完成"""
        # 恢复按钮状态
        self.login_btn.config(state=NORMAL, text="一键登录")

        if success:
            logger.info(f"登录成功")

            # 更新最后登录时间
            self.last_login_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            # 更新登录次数
            current_count = int(self.login_count_label.cget("text"))
            self.login_count_label.config(text=str(current_count + 1))

            # 启动服务
            self.apply_settings()

            # 登录成功提示
            if self.login_success_notify_var.get():
                messagebox.showinfo("成功", f"登录成功: {message}")
        else:
            logger.error(f"登录失败: {message}")

            # 检查是否是因为网络已经连通
            if "网络已连通" in message:
                # 网络已经连通，不算失败
                self.authenticator.is_logged_in = True
                logger.info("网络已连通，无需登录")
            else:
                # 真正的登录失败
                if self.login_fail_notify_var.get():
                    messagebox.showerror("登录失败", message)

    def auto_login(self):
        """自动登录"""
        logger.info("尝试自动登录...")
        self.on_login()

    def minimize_to_tray(self):
        """最小化到托盘"""
        try:
            # 隐藏窗口
            self.root.withdraw()
            self.in_tray = True

            # 导入托盘库（使用pystray）
            try:
                import pystray
                from PIL import Image, ImageDraw

                # 创建托盘图标
                def create_image():
                    # 创建一个简单的图标
                    image = Image.new('RGB', (64, 64), color='#2196F3')
                    dc = ImageDraw.Draw(image)
                    dc.rectangle([16, 16, 48, 48], fill='white')
                    return image

                # 托盘菜单
                menu = (
                    pystray.MenuItem('显示窗口', self.restore_from_tray),
                    pystray.MenuItem('退出', self.quit_from_tray)
                )

                # 创建托盘图标
                image = create_image()
                self.tray_icon = pystray.Icon("campus_net", image, "校园网认证工具", menu)

                # 在新线程中运行托盘图标
                threading.Thread(target=self.tray_icon.run, daemon=True).start()

                logger.info("已最小化到托盘")

            except ImportError:
                # 如果pystray未安装，使用简单的方法
                logger.warning("pystray未安装，使用简单的最小化")
                self.root.iconify()  # 最小化到任务栏

        except Exception as e:
            logger.error(f"最小化到托盘失败: {e}")
            self.root.deiconify()  # 恢复窗口显示

    def restore_from_tray(self):
        """从托盘恢复窗口"""
        try:
            # 停止托盘图标
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None

            # 恢复窗口
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.in_tray = False

            logger.info("已从托盘恢复窗口")

        except Exception as e:
            logger.error(f"从托盘恢复失败: {e}")

    def quit_from_tray(self):
        """从托盘退出"""
        # 停止托盘图标
        if self.tray_icon:
            self.tray_icon.stop()

        # 直接退出程序
        self.authenticator.stop_all()
        self.root.quit()
        self.root.destroy()

    def update_status(self):
        """更新状态"""
        # 在工作线程中检查网络状态
        threading.Thread(target=self.check_network_status_thread, daemon=True).start()

        # 每5秒更新一次状态
        self.root.after(5000, self.update_status)

    def check_network_status_thread(self):
        """检查网络状态的线程"""
        try:
            network_ok = self.authenticator.detect_network_status()
            login_ok = self.authenticator.is_logged_in

            # 在主线程中更新UI
            self.root.after(0, lambda: self.update_status_ui(network_ok, login_ok))
        except Exception as e:
            logger.error(f"检查网络状态出错: {e}")

    def update_status_ui(self, network_ok, login_ok):
        """更新状态UI"""
        # 更新网络状态
        if network_ok:
            self.network_status_label.config(text="已连接", fg="green")
        else:
            self.network_status_label.config(text="未连接", fg="red")

        # 更新登录状态
        if login_ok:
            self.login_status_label.config(text="已登录", fg="green")
        else:
            self.login_status_label.config(text="未登录", fg="red")

    def clear_log(self):
        """清空日志"""
        result = messagebox.askyesno("确认", "确定要清空日志吗？")
        if result:
            self.log_text.config(state=NORMAL)
            self.log_text.delete(1.0, END)
            self.log_text.config(state=DISABLED)
            logger.info("日志已清空")

    def save_log(self):
        """保存日志到文件"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, END))
                logger.info(f"日志已保存到: {filename}")
                messagebox.showinfo("成功", f"日志已保存到:\n{filename}")
            except Exception as e:
                logger.error(f"保存日志失败: {e}")
                messagebox.showerror("错误", f"保存日志失败: {e}")

    def open_log_file(self):
        """打开日志文件"""
        try:
            if os.path.exists('campus_net.log'):
                if sys.platform == 'win32':
                    os.startfile('campus_net.log')
                elif sys.platform == 'darwin':
                    os.system(f'open campus_net.log')
                else:
                    os.system(f'xdg-open campus_net.log')
            else:
                messagebox.showinfo("提示", "日志文件不存在")
        except Exception as e:
            logger.error(f"打开日志文件失败: {e}")
            messagebox.showerror("错误", f"打开日志文件失败: {e}")

    def on_closing(self):
        """关闭窗口事件 - 直接退出，不弹窗"""
        # 静默保存配置
        self.save_config()

        # 停止所有服务
        self.authenticator.stop_all()

        # 如果正在托盘，先停止托盘图标
        if self.in_tray and self.tray_icon:
            self.tray_icon.stop()

        # 直接销毁窗口
        self.root.destroy()


def main():
    """主函数"""
    root = Tk()
    app = CampusNetGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()