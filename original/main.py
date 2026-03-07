#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动认证工具 v1.5
优化点：
1. 提取常量，便于维护
2. 优化线程管理（Event替代布尔标志）
3. 统一异常处理和日志格式
4. 简化重复的GUI代码
5. 增强配置管理的健壮性
6. 提升网络请求的稳定性
"""

import sys
import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from tkinter import *
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import re
import socket
from urllib.parse import urlparse, parse_qs, urlencode, urljoin


# ==================== 常量定义（统一管理硬编码值） ====================
class Constants:
    """系统常量定义"""
    # 网络认证相关
    PORTAL_IP = "10.10.21.129"
    CAS_DOMAIN = "cas.gzittc.com"
    PORTAL_DOMAIN = "xykd.gzittc.edu.cn"
    LOGOUT_PAGE = "xykd.gzittc.edu.cn/portal/usertemp_computer/gongmao-pc-2025/logout.html"

    # 网络检测URL
    TEST_URLS = [
        "http://connectivitycheck.gstatic.com/generate_204",
        "http://www.baidu.com/favicon.ico",
        "http://www.qq.com/favicon.ico",
    ]

    # 默认配置
    DEFAULT_CONFIG = {
        "username": "",
        "password": "",
        "startup": False,
        "auto_login": False,
        "remember_password": True,
        "login_success_notify": True,
        "login_fail_notify": True,
        "timeout": 10,
        "max_retries": 3,
        "enable_heartbeat": True,
        "heartbeat_interval": 120,
        "heartbeat_url": "http://www.baidu.com/favicon.ico",
        "enable_reconnect": True,
        "reconnect_interval": 30,
        "reconnect_cooldown": 30,
        "debug_mode": False,
        "verbose_log": True,
        "auto_clean_log": True,
        "log_retention_days": 7,
        "mac_address": "74:d4:dd:36:15:6c"  # 可配置的MAC地址
    }

    # 日志配置
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"
    LOG_FILE = "campus_net.log"

    # GUI相关
    WINDOW_TITLE = "校园网自动认证工具 v1.5"
    WINDOW_SIZE = "400x600"
    DEFAULT_FONT = ("Arial", 10)
    BUTTON_FONT = ("Arial", 11, "bold")


# ==================== 日志配置 ====================
def setup_logging(debug_mode: bool = False):
    """配置日志系统"""
    log_level = logging.DEBUG if debug_mode else logging.INFO

    # 移除已存在的处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建处理器
    file_handler = logging.FileHandler(Constants.LOG_FILE, encoding="utf-8")
    stream_handler = logging.StreamHandler()

    # 设置格式
    formatter = logging.Formatter(Constants.LOG_FORMAT)
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # 添加处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(log_level)

    return logging.getLogger(__name__)


# ==================== 网络信息获取 ====================
class NetworkInfo:
    """网络信息获取工具类"""

    @staticmethod
    def get_ip_address() -> str:
        """获取本机IP地址（优雅的异常处理）"""
        try:
            # 优先通过连接外部服务器获取
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("114.114.114.114", 80))
                return s.getsockname()[0]
        except Exception:
            try:
                # 备用方案：通过主机名获取
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except Exception:
                return "10.111.50.21"  # 兜底值

    @staticmethod
    def get_mac_address(config: dict) -> str:
        """从配置获取MAC地址"""
        return config.get("mac_address", Constants.DEFAULT_CONFIG["mac_address"])

    @classmethod
    def get_network_info(cls, config: dict) -> dict:
        """获取完整的网络信息"""
        return {
            "ip": cls.get_ip_address(),
            "mac": cls.get_mac_address(config),
            "timestamp": int(time.time() * 1000)
        }


# ==================== 配置管理 ====================
class ConfigManager:
    """配置管理器（优化版）"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)

    def load(self) -> dict:
        """加载配置（自动合并默认值）"""
        try:
            if not os.path.exists(self.config_file):
                return Constants.DEFAULT_CONFIG.copy()

            with open(self.config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)

            # 合并配置（确保所有默认键都存在）
            config = Constants.DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config

        except Exception as e:
            self.logger.error(f"加载配置失败，使用默认配置: {e}")
            return Constants.DEFAULT_CONFIG.copy()

    def save(self, config: dict) -> bool:
        """保存配置（确保目录存在）"""
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True

        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False

    def clean_old_logs(self, retention_days: int = 7):
        """清理过期日志（自动清理功能）"""
        try:
            if not os.path.exists(Constants.LOG_FILE):
                return

            file_stats = os.stat(Constants.LOG_FILE)
            file_age = datetime.now() - datetime.fromtimestamp(file_stats.st_mtime)

            if file_age > timedelta(days=retention_days):
                # 备份旧日志
                backup_name = f"{Constants.LOG_FILE}.{datetime.now().strftime('%Y%m%d')}"
                os.rename(Constants.LOG_FILE, backup_name)
                self.logger.info(f"已备份旧日志到: {backup_name}")

                # 创建新日志文件
                open(Constants.LOG_FILE, "w", encoding="utf-8").close()
                self.logger.info("已创建新日志文件")

        except Exception as e:
            self.logger.error(f"清理日志失败: {e}")


# ==================== 认证核心 ====================
class CampusNetAuthenticator:
    """校园网认证器（优化版）"""

    def __init__(self, config: dict):
        self.logger = logging.getLogger(__name__)
        self.config = config

        # 请求会话（复用连接）
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        # 状态管理
        self.is_logged_in = False
        self.username = None
        self.password = None
        self.network_info = NetworkInfo.get_network_info(config)

        # 线程管理（使用Event更安全）
        self.heartbeat_stop_event = threading.Event()
        self.reconnect_stop_event = threading.Event()
        self.heartbeat_thread = None
        self.reconnect_thread = None

        # 计数器
        self.login_count = 0

        # 请求超时配置
        self.timeout = self.config.get("timeout", Constants.DEFAULT_CONFIG["timeout"])

    def _get_request_timeout(self) -> int:
        """获取请求超时时间"""
        return self.config.get("timeout", Constants.DEFAULT_CONFIG["timeout"])

    def detect_network_status(self) -> bool:
        """检测网络连通性（优化版）"""
        for url in Constants.TEST_URLS:
            try:
                response = requests.get(
                    url,
                    timeout=self._get_request_timeout(),
                    allow_redirects=False
                )

                # 检查重定向到认证页面
                if response.status_code in [302, 307]:
                    location = response.headers.get("Location", "")
                    if Constants.PORTAL_IP in location or Constants.CAS_DOMAIN in location:
                        return False

                # 正常访问
                if response.status_code in [200, 204]:
                    return True

            except Exception as e:
                self.logger.debug(f"检测URL {url} 失败: {e}")
                continue

        # 检查认证页面状态
        try:
            response = self.session.get(
                f"http://{Constants.PORTAL_IP}/portal.do",
                timeout=self._get_request_timeout(),
                allow_redirects=False
            )
            if response.status_code == 200 and "portalScript" in response.text:
                return False
        except Exception as e:
            self.logger.debug(f"检查认证页面失败: {e}")

        return False

    def _build_auth_url(self) -> str:
        """构建认证URL（提取重复逻辑）"""
        params = {
            "wlanuserip": self.network_info["ip"],
            "wlanacname": "Ne8000-M14",
            "usermac": self.network_info["mac"],
        }
        return f"http://{Constants.PORTAL_IP}/portalScript.do?{urlencode(params)}"

    def _extract_form_fields(self, html: str) -> dict:
        """提取表单字段（优化正则匹配）"""
        fields = {}
        html = html.replace("\n", " ").replace("\r", "")

        # 匹配隐藏字段的通用模式
        hidden_patterns = [
            r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']+)["\']',
        ]

        for pattern in hidden_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for name, value in matches:
                fields[name] = value

        # 确保关键字段存在
        required_fields = ["lt", "execution", "_eventId"]
        for field in required_fields:
            if field not in fields:
                if field == "execution":
                    fields[field] = "e1s1"
                elif field == "_eventId":
                    fields[field] = "submit"

        # 单独提取lt（关键令牌）
        if "lt" not in fields:
            lt_match = re.search(r'LT-[^"\']+', html)
            if lt_match:
                fields["lt"] = lt_match.group(0)

        return fields

    def _follow_redirects(self, start_response, max_redirects: int = 10) -> requests.Response:
        """跟随重定向链（优化版）"""
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
                    self.logger.info(f"补全路径: {redirect_url}")

                # 修复URL中的错误
                redirect_url = redirect_url.replace("vl an", "vlan")

                try:
                    current_response = self.session.get(
                        redirect_url,
                        timeout=self._get_request_timeout(),
                        allow_redirects=False
                    )
                    redirect_count += 1
                except Exception as e:
                    self.logger.error(f"跟随重定向失败: {e}")
                    break
            else:
                break

        self.logger.info(f"重定向结束，最终URL: {current_response.url}")
        return current_response

    def _get_base_url(self, current_url: str) -> str:
        """获取基础URL（优化路径补全）"""
        if Constants.CAS_DOMAIN in current_url:
            return f"https://{Constants.CAS_DOMAIN}"
        elif Constants.PORTAL_DOMAIN in current_url:
            return f"http://{Constants.PORTAL_DOMAIN}"
        elif Constants.PORTAL_IP in current_url:
            return f"http://{Constants.PORTAL_IP}"
        return f"http://{Constants.PORTAL_DOMAIN}"

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """执行登录（优化版）"""
        self.username = username.strip()
        self.password = password.strip()
        self.login_count += 1

        self.logger.info(f"开始登录，用户: {self.username}，次数: {self.login_count}")

        # 先检查网络状态
        if self.detect_network_status():
            self.logger.info("网络已连通，无需登录")
            self.is_logged_in = True
            return True, "网络已连通"

        self.logger.info("网络未连通，开始认证流程")

        try:
            # 获取认证URL
            auth_url = self._build_auth_url()
            self.logger.info(f"认证URL: {auth_url}")

            # 访问认证页面
            response = self.session.get(
                auth_url,
                timeout=self._get_request_timeout(),
                allow_redirects=False
            )
            current_url = str(response.url)

            # 处理portalScript.do页面
            if "portalScript.do" in current_url:
                response = self._handle_portal_script(response, current_url)
                current_url = str(response.url)

            # 处理CAS登录页面
            if Constants.CAS_DOMAIN in current_url:
                return self._handle_cas_login(response, current_url)

            return False, f"未知的页面状态: {current_url}"

        except requests.exceptions.Timeout:
            return False, "连接超时，请检查网络"
        except requests.exceptions.ConnectionError:
            return False, "连接错误，请检查网络"
        except Exception as e:
            self.logger.error(f"登录过程出错: {e}", exc_info=True)
            # 保存异常信息
            with open("login_exception.txt", "w", encoding="utf-8") as f:
                f.write(f"{datetime.now()}\n{str(e)}\n")
            return False, f"登录出错: {str(e)}"

    def _handle_portal_script(self, response: requests.Response, current_url: str) -> requests.Response:
        """处理portalScript.do页面（提取重复逻辑）"""
        self.logger.info("在portalScript.do页面，准备单点登录")

        # 提取参数
        parsed_url = urlparse(current_url)
        params = parse_qs(parsed_url.query)

        # 构建单点登录URL
        sso_params = {
            "wlanuserip": params.get("wlanuserip", [self.network_info["ip"]])[0],
            "wlanacname": params.get("wlanacname", ["Ne8000-M14"])[0],
            "usermac": params.get("usermac", [self.network_info["mac"]])[0],
            "rand": str(int(time.time() * 1000))
        }

        sso_url = f"http://{Constants.PORTAL_IP}/portalCasAuth.do?{urlencode(sso_params)}"
        self.logger.info(f"单点登录URL: {sso_url}")

        # 访问单点登录URL
        response = self.session.get(
            sso_url,
            timeout=self._get_request_timeout(),
            allow_redirects=False
        )

        if response.status_code in [302, 303]:
            redirect_url = response.headers.get("Location", "")
            if redirect_url:
                self.logger.info(f"单点登录重定向: {redirect_url}")
                response = self.session.get(
                    redirect_url,
                    timeout=self._get_request_timeout(),
                    allow_redirects=True
                )

        return response

    def _handle_cas_login(self, response: requests.Response, current_url: str) -> tuple[bool, str]:
        """处理CAS登录页面（提取重复逻辑）"""
        self.logger.info("在CAS登录页面")

        # 提取表单字段
        form_fields = self._extract_form_fields(response.text)

        # 检查关键令牌
        if not form_fields.get("lt"):
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
            timeout=self._get_request_timeout(),
            allow_redirects=False
        )

        self.logger.info(f"登录提交状态码: {response.status_code}")

        # 处理重定向
        final_response = self._follow_redirects(response)
        final_url = str(final_response.url)

        # 检查登录结果
        if Constants.LOGOUT_PAGE in final_url:
            self.is_logged_in = True
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
            return False, error_msg or f"未跳转到logout页面，当前页面: {final_url}"

    def _extract_error_message(self, html: str) -> str:
        """提取错误信息（优化版）"""
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
                return f"登录失败: {match.group(1).strip() if len(match.groups()) > 0 else match.group(0)}"

        return ""

    def start_heartbeat(self):
        """启动心跳保持（使用Event控制）"""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.stop_heartbeat()

        self.heartbeat_stop_event.clear()
        interval = self.config.get("heartbeat_interval", Constants.DEFAULT_CONFIG["heartbeat_interval"])

        def heartbeat_worker():
            self.logger.info(f"心跳保持启动，间隔: {interval}秒")
            while not self.heartbeat_stop_event.is_set():
                try:
                    requests.get(
                        self.config.get("heartbeat_url", Constants.DEFAULT_CONFIG["heartbeat_url"]),
                        timeout=self._get_request_timeout()
                    )
                    self.logger.debug("心跳保持: 网络正常")
                except Exception as e:
                    self.logger.debug(f"心跳保持: 请求失败: {e}")
                finally:
                    self.heartbeat_stop_event.wait(interval)

        self.heartbeat_thread = threading.Thread(
            target=heartbeat_worker,
            name="HeartbeatThread",
            daemon=True
        )
        self.heartbeat_thread.start()

    def start_reconnect(self):
        """启动断线重连（使用Event控制）"""
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            self.stop_reconnect()

        self.reconnect_stop_event.clear()
        interval = self.config.get("reconnect_interval", Constants.DEFAULT_CONFIG["reconnect_interval"])
        cooldown = self.config.get("reconnect_cooldown", Constants.DEFAULT_CONFIG["reconnect_cooldown"])

        def reconnect_worker():
            self.logger.info(f"断线重连启动，检测间隔: {interval}秒，冷却时间: {cooldown}秒")
            last_login_attempt = 0

            while not self.reconnect_stop_event.is_set():
                try:
                    current_time = time.time()

                    if not self.detect_network_status():
                        self.logger.warning("断线重连: 网络断开")

                        if current_time - last_login_attempt > cooldown:
                            if self.username and self.password:
                                self.logger.info("断线重连: 尝试重新登录")
                                last_login_attempt = current_time
                                success, message = self.login(self.username, self.password)
                                if success:
                                    self.logger.info("断线重连: 重新登录成功")
                                else:
                                    self.logger.error(f"断线重连: 失败: {message}")
                            else:
                                self.logger.warning("断线重连: 无登录凭证")
                    else:
                        if int(current_time) % 100 == 0:
                            self.logger.debug("断线重连: 网络正常")

                    self.reconnect_stop_event.wait(interval)

                except Exception as e:
                    self.logger.error(f"断线重连出错: {e}")
                    self.reconnect_stop_event.wait(interval)

        self.reconnect_thread = threading.Thread(
            target=reconnect_worker,
            name="ReconnectThread",
            daemon=True
        )
        self.reconnect_thread.start()

    def stop_heartbeat(self):
        """停止心跳保持"""
        self.heartbeat_stop_event.set()
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        self.logger.info("心跳保持已停止")

    def stop_reconnect(self):
        """停止断线重连"""
        self.reconnect_stop_event.set()
        if self.reconnect_thread:
            self.reconnect_thread.join(timeout=5)
        self.logger.info("断线重连已停止")

    def stop_all(self):
        """停止所有后台服务"""
        self.stop_heartbeat()
        self.stop_reconnect()

    def update_config(self, new_config: dict):
        """更新配置"""
        self.config.update(new_config)
        self.timeout = self.config.get("timeout", Constants.DEFAULT_CONFIG["timeout"])
        self.network_info = NetworkInfo.get_network_info(self.config)


# ==================== GUI组件 ====================
class ScrollableFrame:
    """可滚动的Frame（优化版）"""

    def __init__(self, container, **kwargs):
        self.canvas = Canvas(container, **kwargs)
        self.scrollbar = Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas)

        # 绑定滚动事件
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # 创建窗口
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 绑定鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """处理鼠标滚轮"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def pack(self, **kwargs):
        """打包Canvas"""
        self.canvas.pack(**kwargs)


class CampusNetGUI:
    """校园网认证GUI（优化版）"""

    def __init__(self, root):
        self.root = root
        self.root.title(Constants.WINDOW_TITLE)
        self.root.geometry(Constants.WINDOW_SIZE)

        # 初始化组件
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()

        # 配置日志
        self.logger = setup_logging(self.config.get("debug_mode", False))

        # 初始化认证器
        self.authenticator = CampusNetAuthenticator(self.config)

        # 托盘状态
        self.tray_icon = None
        self.in_tray = False

        # 日志处理器
        self.log_handler = self._create_log_handler()
        logging.getLogger().addHandler(self.log_handler)

        # 创建GUI
        self._create_widgets()

        # 加载配置到UI
        self._load_config_to_ui()

        # 自动清理日志
        if self.config.get("auto_clean_log"):
            self.config_manager.clean_old_logs(self.config.get("log_retention_days"))

        # 自动登录（如果配置开启）
        if self.config.get("auto_login") and self.config.get("username") and self.config.get("password"):
            self.root.after(2000, self._auto_login)

        # 定期更新状态
        self._update_status()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.logger.info("校园网认证工具启动完成")

    def _create_log_handler(self):
        """创建GUI日志处理器"""
        handler = logging.Handler()
        handler.setLevel(logging.INFO)

        def emit(record):
            """自定义日志输出"""
            try:
                msg = handler.format(record)
                if hasattr(self, "log_text"):
                    self.root.after(0, self._append_log, msg + "\n")
            except Exception:
                pass

        handler.emit = emit
        return handler

    def _append_log(self, msg):
        """添加日志到文本框"""
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, msg)
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def _create_widgets(self):
        """创建所有GUI控件（优化版）"""
        # 创建标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 创建各标签页
        self._create_login_tab()
        self._create_settings_tab()
        self._create_log_tab()

    def _create_login_tab(self):
        """创建登录标签页"""
        login_tab = Frame(self.notebook)
        self.notebook.add(login_tab, text="登录")

        # 主框架
        main_frame = Frame(login_tab, padx=20, pady=20)
        main_frame.pack(fill=BOTH, expand=True)

        # 标题
        Label(
            main_frame,
            text="校园网自动认证工具",
            font=("Arial", 18, "bold")
        ).pack(pady=(0, 30))

        # 账号密码框架
        cred_frame = Frame(main_frame)
        cred_frame.pack(fill=X, pady=(0, 20))

        # 学号输入
        self.username_var = StringVar()
        self._create_labeled_entry(
            parent=cred_frame,
            label_text="学号:",
            row=0,
            var=self.username_var,
            show=""
        )

        # 密码输入
        self.password_var = StringVar()
        self._create_labeled_entry(
            parent=cred_frame,
            label_text="密码:",
            row=1,
            var=self.password_var,
            show="*"
        )

        # 登录按钮
        self.login_btn = Button(
            main_frame,
            text="一键登录",
            command=self._on_login,
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            width=20,
            height=2
        )
        self.login_btn.pack(pady=10)

        # 最小化到托盘按钮
        Button(
            main_frame,
            text="最小化到托盘",
            command=self._minimize_to_tray,
            font=("Arial", 10),
            bg="#2196F3",
            fg="white",
            width=15,
            height=1
        ).pack(pady=5)

        # 状态信息框架
        status_frame = LabelFrame(
            main_frame,
            text="系统状态",
            font=("Arial", 11),
            padx=15,
            pady=15
        )
        status_frame.pack(fill=X, pady=(10, 0))

        # 状态网格
        status_grid = Frame(status_frame)
        status_grid.pack(fill=X)

        # 网络状态
        self.network_status_label = self._create_status_label(
            parent=status_grid,
            label_text="网络状态:",
            row=0,
            initial_text="未知"
        )

        # 登录状态
        self.login_status_label = self._create_status_label(
            parent=status_grid,
            label_text="登录状态:",
            row=1,
            initial_text="未登录"
        )

        # 最后登录时间
        self.last_login_label = self._create_status_label(
            parent=status_grid,
            label_text="最后登录:",
            row=2,
            initial_text="无",
            is_bold=False
        )

        # 登录次数
        self.login_count_label = self._create_status_label(
            parent=status_grid,
            label_text="登录次数:",
            row=3,
            initial_text="0",
            is_bold=False
        )

        # 网络信息
        info_frame = Frame(status_frame)
        info_frame.pack(fill=X, pady=(10, 0))

        Label(info_frame, text="IP地址:", font=("Arial", 9)).pack(side=LEFT)
        Label(
            info_frame,
            text=self.authenticator.network_info["ip"],
            font=("Arial", 9),
            fg="blue"
        ).pack(side=LEFT, padx=(5, 15))

        Label(info_frame, text="MAC地址:", font=("Arial", 9)).pack(side=LEFT)
        Label(
            info_frame,
            text=self.authenticator.network_info["mac"],
            font=("Arial", 9),
            fg="blue"
        ).pack(side=LEFT, padx=(5, 0))

    def _create_labeled_entry(self, parent, label_text, row, var, show=""):
        """创建带标签的输入框（提取重复逻辑）"""
        Label(parent, text=label_text, font=Constants.DEFAULT_FONT).grid(
            row=row, column=0, sticky=W, pady=10
        )
        entry = Entry(
            parent,
            textvariable=var,
            font=Constants.DEFAULT_FONT,
            width=25,
            show=show
        )
        entry.grid(row=row, column=1, pady=10, padx=(10, 0))
        return entry

    def _create_status_label(self, parent, label_text, row, initial_text, is_bold=True):
        """创建状态标签（提取重复逻辑）"""
        Label(parent, text=label_text, font=Constants.DEFAULT_FONT).grid(
            row=row, column=0, sticky=W, pady=5
        )

        font = ("Arial", 10, "bold") if is_bold else ("Arial", 10)
        label = Label(
            parent,
            text=initial_text,
            fg="gray",
            font=font
        )
        label.grid(row=row, column=1, sticky=W, pady=5, padx=(10, 0))
        return label

    def _create_settings_tab(self):
        """创建设置标签页"""
        settings_tab = Frame(self.notebook)
        self.notebook.add(settings_tab, text="设置")

        # 可滚动框架
        scrollable_frame = ScrollableFrame(settings_tab)
        content_frame = scrollable_frame.scrollable_frame

        # 设置内容框架
        settings_content = Frame(content_frame, padx=20, pady=20)
        settings_content.pack(fill=BOTH, expand=True)

        # 标题
        Label(
            settings_content,
            text="设置选项",
            font=("Arial", 16, "bold")
        ).pack(pady=(0, 20))

        # 启动设置
        self._create_startup_settings(settings_content)

        # 登录设置
        self._create_login_settings(settings_content)

        # 网络设置
        self._create_network_settings(settings_content)

        # 心跳保持设置
        self._create_heartbeat_settings(settings_content)

        # 断线重连设置
        self._create_reconnect_settings(settings_content)

        # 高级设置
        self._create_advanced_settings(settings_content)

        # 操作按钮
        self._create_settings_buttons(settings_content)

    def _create_startup_settings(self, parent):
        """创建启动设置区域"""
        frame = LabelFrame(
            parent,
            text="启动设置",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=15
        )
        frame.pack(fill=X, pady=(0, 15))

        self.startup_var = BooleanVar()
        Checkbutton(
            frame,
            text="开机自启",
            variable=self.startup_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=0, column=0, sticky=W, pady=5)

        self.auto_login_var = BooleanVar()
        Checkbutton(
            frame,
            text="启动时自动登录",
            variable=self.auto_login_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=1, column=0, sticky=W, pady=5)

    def _create_login_settings(self, parent):
        """创建登录设置区域"""
        frame = LabelFrame(
            parent,
            text="登录设置",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=15
        )
        frame.pack(fill=X, pady=(0, 15))

        self.remember_password_var = BooleanVar()
        Checkbutton(
            frame,
            text="记住密码",
            variable=self.remember_password_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=0, column=0, sticky=W, pady=5)

        self.login_success_notify_var = BooleanVar()
        Checkbutton(
            frame,
            text="登录成功提示",
            variable=self.login_success_notify_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=0, column=1, sticky=W, pady=5, padx=(20, 0))

        self.login_fail_notify_var = BooleanVar()
        Checkbutton(
            frame,
            text="登录失败提示",
            variable=self.login_fail_notify_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=1, column=0, sticky=W, pady=5)

    def _create_network_settings(self, parent):
        """创建网络设置区域"""
        frame = LabelFrame(
            parent,
            text="网络设置",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=15
        )
        frame.pack(fill=X, pady=(0, 15))

        self._create_spinbox_setting(
            parent=frame,
            label_text="超时时间 (秒):",
            row=0,
            min_val=5,
            max_val=60,
            default_val=10,
            var_name="timeout_var"
        )

        self._create_spinbox_setting(
            parent=frame,
            label_text="最大重试次数:",
            row=1,
            min_val=1,
            max_val=10,
            default_val=3,
            var_name="max_retries_var"
        )

    def _create_heartbeat_settings(self, parent):
        """创建心跳保持设置区域"""
        frame = LabelFrame(
            parent,
            text="心跳保持设置",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=15
        )
        frame.pack(fill=X, pady=(0, 15))

        self.enable_heartbeat_var = BooleanVar()
        Checkbutton(
            frame,
            text="启用心跳保持",
            variable=self.enable_heartbeat_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=0, column=0, sticky=W, pady=5)

        self._create_spinbox_setting(
            parent=frame,
            label_text="心跳间隔 (秒):",
            row=1,
            min_val=30,
            max_val=600,
            default_val=120,
            var_name="heartbeat_interval_var"
        )

        # 心跳网址
        Label(frame, text="心跳网址:", font=Constants.DEFAULT_FONT).grid(
            row=2, column=0, sticky=W, pady=5
        )
        self.heartbeat_url_var = StringVar()
        Entry(
            frame,
            textvariable=self.heartbeat_url_var,
            width=25,
            font=Constants.DEFAULT_FONT
        ).grid(row=2, column=1, sticky=W, pady=5, padx=(10, 0))

    def _create_reconnect_settings(self, parent):
        """创建断线重连设置区域"""
        frame = LabelFrame(
            parent,
            text="断线重连设置",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=15
        )
        frame.pack(fill=X, pady=(0, 15))

        self.enable_reconnect_var = BooleanVar()
        Checkbutton(
            frame,
            text="启用断线重连",
            variable=self.enable_reconnect_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=0, column=0, sticky=W, pady=5)

        self._create_spinbox_setting(
            parent=frame,
            label_text="检测间隔 (秒):",
            row=1,
            min_val=10,
            max_val=300,
            default_val=30,
            var_name="reconnect_interval_var"
        )

        self._create_spinbox_setting(
            parent=frame,
            label_text="冷却时间 (秒):",
            row=2,
            min_val=10,
            max_val=300,
            default_val=30,
            var_name="reconnect_cooldown_var"
        )

    def _create_advanced_settings(self, parent):
        """创建高级设置区域"""
        frame = LabelFrame(
            parent,
            text="高级设置",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=15
        )
        frame.pack(fill=X, pady=(0, 15))

        self.debug_mode_var = BooleanVar()
        Checkbutton(
            frame,
            text="调试模式",
            variable=self.debug_mode_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=0, column=0, sticky=W, pady=5)

        self.verbose_log_var = BooleanVar()
        Checkbutton(
            frame,
            text="详细日志",
            variable=self.verbose_log_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=0, column=1, sticky=W, pady=5, padx=(20, 0))

        self.auto_clean_log_var = BooleanVar()
        Checkbutton(
            frame,
            text="自动清理日志",
            variable=self.auto_clean_log_var,
            font=Constants.DEFAULT_FONT
        ).grid(row=1, column=0, sticky=W, pady=5)

        Label(frame, text="日志保留 (天):", font=Constants.DEFAULT_FONT).grid(
            row=1, column=1, sticky=W, pady=5, padx=(20, 0)
        )
        self.log_retention_days_var = IntVar()
        Spinbox(
            frame,
            from_=1,
            to=30,
            textvariable=self.log_retention_days_var,
            width=8,
            font=Constants.DEFAULT_FONT
        ).grid(row=1, column=2, sticky=W, pady=5, padx=(10, 0))

    def _create_spinbox_setting(self, parent, label_text, row, min_val, max_val, default_val, var_name):
        """创建Spinbox设置项（提取重复逻辑）"""
        Label(parent, text=label_text, font=Constants.DEFAULT_FONT).grid(
            row=row, column=0, sticky=W, pady=5
        )

        var = IntVar(value=default_val)
        setattr(self, var_name, var)

        spinbox = Spinbox(
            parent,
            from_=min_val,
            to=max_val,
            textvariable=var,
            width=8,
            font=Constants.DEFAULT_FONT
        )
        spinbox.grid(row=row, column=1, sticky=W, pady=5, padx=(10, 0))
        return spinbox

    def _create_settings_buttons(self, parent):
        """创建设置操作按钮"""
        button_frame = Frame(parent)
        button_frame.pack(fill=X, pady=(20, 10))

        Button(
            button_frame,
            text="保存设置",
            command=self._save_config,
            font=Constants.BUTTON_FONT,
            bg="#2196F3",
            fg="white",
            width=15,
            height=2
        ).pack(side=LEFT, padx=(0, 10))

        Button(
            button_frame,
            text="恢复默认",
            command=self._reset_config,
            font=Constants.DEFAULT_FONT,
            width=15,
            height=2
        ).pack(side=LEFT)

    def _create_log_tab(self):
        """创建日志标签页"""
        log_tab = Frame(self.notebook)
        self.notebook.add(log_tab, text="日志")

        main_frame = Frame(log_tab, padx=10, pady=10)
        main_frame.pack(fill=BOTH, expand=True)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=WORD,
            width=80,
            height=25
        )
        self.log_text.pack(fill=BOTH, expand=True, pady=(0, 10))
        self.log_text.config(state=DISABLED)

        # 日志控制按钮
        button_frame = Frame(main_frame)
        button_frame.pack(fill=X)

        Button(
            button_frame,
            text="清空日志",
            command=self._clear_log,
            width=15
        ).pack(side=LEFT, padx=(0, 10))

        Button(
            button_frame,
            text="保存日志",
            command=self._save_log,
            width=15
        ).pack(side=LEFT, padx=(0, 10))

        Button(
            button_frame,
            text="打开日志文件",
            command=self._open_log_file,
            width=15
        ).pack(side=LEFT)

    def _load_config_to_ui(self):
        """加载配置到UI"""
        # 账号信息
        self.username_var.set(self.config.get("username", ""))
        self.password_var.set(self.config.get("password", ""))

        # 启动设置
        self.startup_var.set(self.config.get("startup", False))
        self.auto_login_var.set(self.config.get("auto_login", False))

        # 登录设置
        self.remember_password_var.set(self.config.get("remember_password", True))
        self.login_success_notify_var.set(self.config.get("login_success_notify", True))
        self.login_fail_notify_var.set(self.config.get("login_fail_notify", True))

        # 网络设置
        self.timeout_var.set(self.config.get("timeout", 10))
        self.max_retries_var.set(self.config.get("max_retries", 3))

        # 心跳设置
        self.enable_heartbeat_var.set(self.config.get("enable_heartbeat", True))
        self.heartbeat_interval_var.set(self.config.get("heartbeat_interval", 120))
        self.heartbeat_url_var.set(self.config.get("heartbeat_url", ""))

        # 重连设置
        self.enable_reconnect_var.set(self.config.get("enable_reconnect", True))
        self.reconnect_interval_var.set(self.config.get("reconnect_interval", 30))
        self.reconnect_cooldown_var.set(self.config.get("reconnect_cooldown", 30))

        # 高级设置
        self.debug_mode_var.set(self.config.get("debug_mode", False))
        self.verbose_log_var.set(self.config.get("verbose_log", True))
        self.auto_clean_log_var.set(self.config.get("auto_clean_log", True))
        self.log_retention_days_var.set(self.config.get("log_retention_days", 7))

    def _save_config(self):
        """保存配置"""
        new_config = {
            "username": self.username_var.get(),
            "password": self.password_var.get() if self.remember_password_var.get() else "",
            "startup": self.startup_var.get(),
            "auto_login": self.auto_login_var.get(),
            "remember_password": self.remember_password_var.get(),
            "login_success_notify": self.login_success_notify_var.get(),
            "login_fail_notify": self.login_fail_notify_var.get(),
            "timeout": self.timeout_var.get(),
            "max_retries": self.max_retries_var.get(),
            "enable_heartbeat": self.enable_heartbeat_var.get(),
            "heartbeat_interval": self.heartbeat_interval_var.get(),
            "heartbeat_url": self.heartbeat_url_var.get(),
            "enable_reconnect": self.enable_reconnect_var.get(),
            "reconnect_interval": self.reconnect_interval_var.get(),
            "reconnect_cooldown": self.reconnect_cooldown_var.get(),
            "debug_mode": self.debug_mode_var.get(),
            "verbose_log": self.verbose_log_var.get(),
            "auto_clean_log": self.auto_clean_log_var.get(),
            "log_retention_days": self.log_retention_days_var.get(),
            "mac_address": self.config.get("mac_address", Constants.DEFAULT_CONFIG["mac_address"])
        }

        if self.config_manager.save(new_config):
            self.logger.info("配置已保存")
            self.authenticator.update_config(new_config)
            self.config = new_config

            # 重新配置日志
            setup_logging(new_config.get("debug_mode", False))

            # 应用服务设置
            self._apply_service_settings()
        else:
            self.logger.error("配置保存失败")

    def _reset_config(self):
        """恢复默认配置"""
        if messagebox.askyesno("确认", "确定要恢复默认设置吗？"):
            # 加载默认配置
            default_config = Constants.DEFAULT_CONFIG.copy()

            # 更新UI
            self.username_var.set(default_config["username"])
            self.password_var.set(default_config["password"])
            self.startup_var.set(default_config["startup"])
            self.auto_login_var.set(default_config["auto_login"])
            self.remember_password_var.set(default_config["remember_password"])
            self.login_success_notify_var.set(default_config["login_success_notify"])
            self.login_fail_notify_var.set(default_config["login_fail_notify"])
            self.timeout_var.set(default_config["timeout"])
            self.max_retries_var.set(default_config["max_retries"])
            self.enable_heartbeat_var.set(default_config["enable_heartbeat"])
            self.heartbeat_interval_var.set(default_config["heartbeat_interval"])
            self.heartbeat_url_var.set(default_config["heartbeat_url"])
            self.enable_reconnect_var.set(default_config["enable_reconnect"])
            self.reconnect_interval_var.set(default_config["reconnect_interval"])
            self.reconnect_cooldown_var.set(default_config["reconnect_cooldown"])
            self.debug_mode_var.set(default_config["debug_mode"])
            self.verbose_log_var.set(default_config["verbose_log"])
            self.auto_clean_log_var.set(default_config["auto_clean_log"])
            self.log_retention_days_var.set(default_config["log_retention_days"])

            # 保存默认配置
            self._save_config()
            self.logger.info("已恢复默认设置")
            messagebox.showinfo("成功", "已恢复默认设置")

    def _apply_service_settings(self):
        """应用服务设置"""
        if self.authenticator.is_logged_in:
            self.authenticator.stop_all()

            # 启动心跳保持
            if self.enable_heartbeat_var.get():
                self.authenticator.start_heartbeat()

            # 启动断线重连
            if self.enable_reconnect_var.get():
                self.authenticator.start_reconnect()

    def _on_login(self):
        """登录按钮点击事件"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showwarning("警告", "请输入账号和密码")
            return

        # 禁用按钮
        self.login_btn.config(state=DISABLED, text="登录中...")

        # 后台线程执行登录
        threading.Thread(
            target=self._login_thread,
            args=(username, password),
            name="LoginThread",
            daemon=True
        ).start()

    def _login_thread(self, username, password):
        """登录线程"""
        try:
            success, message = self.authenticator.login(username, password)
            self.root.after(0, self._on_login_finished, success, message)
        except Exception as e:
            self.root.after(0, self._on_login_finished, False, f"登录异常: {str(e)}")

    def _on_login_finished(self, success, message):
        """登录完成回调"""
        # 恢复按钮状态
        self.login_btn.config(state=NORMAL, text="一键登录")

        if success:
            self.logger.info(f"登录成功: {message}")

            # 更新UI状态
            self.last_login_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.login_count_label.config(text=str(int(self.login_count_label.cget("text")) + 1))

            # 启动服务
            self._apply_service_settings()

            # 登录成功提示
            if self.config.get("login_success_notify", True):
                messagebox.showinfo("成功", message)
        else:
            self.logger.error(f"登录失败: {message}")

            # 登录失败提示
            if self.config.get("login_fail_notify", True) and "网络已连通" not in message:
                messagebox.showerror("失败", message)

            # 网络已连通的特殊处理
            if "网络已连通" in message:
                self.authenticator.is_logged_in = True

    def _auto_login(self):
        """自动登录"""
        self.logger.info("执行自动登录")
        self._on_login()

    def _minimize_to_tray(self):
        """最小化到托盘"""
        try:
            self.root.withdraw()
            self.in_tray = True

            # 尝试创建系统托盘
            try:
                import pystray
                from PIL import Image, ImageDraw

                def create_tray_icon():
                    """创建托盘图标"""
                    image = Image.new("RGB", (64, 64), color="#2196F3")
                    dc = ImageDraw.Draw(image)
                    dc.rectangle([16, 16, 48, 48], fill="white")
                    return image

                # 托盘菜单
                menu = (
                    pystray.MenuItem("显示窗口", self._restore_from_tray),
                    pystray.MenuItem("退出", self._quit_from_tray)
                )

                # 创建托盘图标
                self.tray_icon = pystray.Icon(
                    "campus_net",
                    create_tray_icon(),
                    "校园网认证工具",
                    menu
                )

                # 启动托盘（后台线程）
                threading.Thread(
                    target=self.tray_icon.run,
                    name="TrayThread",
                    daemon=True
                ).start()

                self.logger.info("已最小化到系统托盘")

            except ImportError:
                self.logger.warning("pystray未安装，最小化到任务栏")
                self.root.iconify()

        except Exception as e:
            self.logger.error(f"最小化到托盘失败: {e}")
            self.root.deiconify()

    def _restore_from_tray(self):
        """从托盘恢复窗口"""
        try:
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None

            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.in_tray = False
            self.logger.info("已从托盘恢复窗口")

        except Exception as e:
            self.logger.error(f"恢复窗口失败: {e}")

    def _quit_from_tray(self):
        """从托盘退出程序"""
        self._on_closing()

    def _update_status(self):
        """更新系统状态"""
        # 后台线程检测状态
        threading.Thread(
            target=self._check_status_thread,
            name="StatusThread",
            daemon=True
        ).start()

        # 定期更新
        self.root.after(5000, self._update_status)

    def _check_status_thread(self):
        """检查状态线程"""
        try:
            network_ok = self.authenticator.detect_network_status()
            login_ok = self.authenticator.is_logged_in

            # 更新UI
            self.root.after(0, self._update_status_ui, network_ok, login_ok)

        except Exception as e:
            self.logger.error(f"检查状态失败: {e}")

    def _update_status_ui(self, network_ok, login_ok):
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

    def _clear_log(self):
        """清空日志"""
        if messagebox.askyesno("确认", "确定要清空日志吗？"):
            self.log_text.config(state=NORMAL)
            self.log_text.delete(1.0, END)
            self.log_text.config(state=DISABLED)
            self.logger.info("日志已清空")

    def _save_log(self):
        """保存日志"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.log_text.get(1.0, END))
                self.logger.info(f"日志已保存到: {filename}")
                messagebox.showinfo("成功", f"日志已保存到:\n{filename}")
            except Exception as e:
                self.logger.error(f"保存日志失败: {e}")
                messagebox.showerror("错误", f"保存日志失败: {e}")

    def _open_log_file(self):
        """打开日志文件"""
        try:
            if os.path.exists(Constants.LOG_FILE):
                if sys.platform == "win32":
                    os.startfile(Constants.LOG_FILE)
                elif sys.platform == "darwin":
                    os.system(f"open {Constants.LOG_FILE}")
                else:
                    os.system(f"xdg-open {Constants.LOG_FILE}")
            else:
                messagebox.showinfo("提示", "日志文件不存在")
        except Exception as e:
            self.logger.error(f"打开日志文件失败: {e}")
            messagebox.showerror("错误", f"打开日志文件失败: {e}")

    def _on_closing(self):
        """关闭窗口事件"""
        # 保存配置
        self._save_config()

        # 停止所有服务
        self.authenticator.stop_all()

        # 停止托盘图标
        if self.in_tray and self.tray_icon:
            self.tray_icon.stop()

        # 移除日志处理器
        logging.getLogger().removeHandler(self.log_handler)

        # 销毁窗口
        self.root.destroy()


def main():
    """主函数"""
    root = Tk()
    app = CampusNetGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()