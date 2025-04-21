import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import json
import time
import threading
import pystray
from PIL import Image
import sys
import platform
from .network import NetworkDaemon
from .auth_system import AuthManager
import requests

class SystemTrayApp:
    def __init__(self, master):
        self.master = master
        self.tray_icon = None
        self._create_tray_icon()

        # 窗口关闭时隐藏到托盘
        self.master.protocol('WM_DELETE_WINDOW', self.hide_window)

    def _create_tray_icon(self):
        menu = (
            pystray.MenuItem('显示主界面', self.show_window),
            pystray.MenuItem('退出', self.quit_app)
        )
        image = Image.new('RGB', (64, 64), 'white')
        self.tray_icon = pystray.Icon("campus_login", image, "校园网认证", menu)

        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        self.master.after(0, self.master.deiconify)

    def hide_window(self):
        self.master.withdraw()

    def quit_app(self):
        self.tray_icon.stop()
        self.master.destroy()
        sys.exit(0)


class LoginGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("校园网认证 v2.0")
        self.geometry("600x400")
        self.config_path = Path("config/settings.cfg")
        self.daemon = None
        self.running = True

        # 初始化组件
        self._create_widgets()
        self.load_configuration()
        self.tray = SystemTrayApp(self)

        # 启动后台监控
        self.start_daemon()

    def _create_widgets(self):
        # 输入区域
        input_frame = ttk.Frame(self)
        input_frame.pack(pady=10, fill='x')

        ttk.Label(input_frame, text="学号:").grid(row=0, column=0, padx=5)
        self.usr_entry = ttk.Entry(input_frame)
        self.usr_entry.grid(row=0, column=1, sticky='ew')

        ttk.Label(input_frame, text="密码:").grid(row=1, column=0, padx=5)
        self.pwd_entry = ttk.Entry(input_frame, show="*")
        self.pwd_entry.grid(row=1, column=1, sticky='ew')

        # 控制按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="保存配置", command=self.load_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="立即登录", command=self._manual_login).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="完全退出", command=self.quit_app).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="调试", command=self.show_debug).pack(side=tk.LEFT)

        # 状态指示器
        self.status_frame = ttk.LabelFrame(self, text="系统状态")
        self.status_frame.pack(pady=5, fill='x')

        self.network_status = ttk.Label(self.status_frame, text="网络: 检测中...")
        self.network_status.pack(side=tk.LEFT, padx=5)

        self.auth_status = ttk.Label(self.status_frame, text="认证: 未登录")
        self.auth_status.pack(side=tk.LEFT, padx=5)

        # 日志区域
        self.log = tk.Text(self, height=10, wrap=tk.WORD)
        self.log.pack(pady=5, fill='both', expand=True)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.log)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        self.log.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log.yview)

    def start_daemon(self):
        self.daemon = NetworkDaemon(self._auto_login)
        self.daemon_thread = threading.Thread(target=self.daemon.start, daemon=True)
        self.daemon_thread.start()

        # 启动状态更新
        self._update_status_indicator()

    def _update_status_indicator(self):
        """每5秒更新状态显示"""
        if self.running:
            network_state = "已连接" if self._check_network() else "未连接"
            auth_state = "已认证" if AuthManager().check_online() else "未认证"

            self.network_status.config(text=f"网络: {network_state}",
                                       foreground="green" if network_state == "已连接" else "red")
            self.auth_status.config(text=f"认证: {auth_state}",
                                    foreground="green" if auth_state == "已认证" else "red")

            self.after(5000, self._update_status_indicator)

    def _check_network(self):
        try:
            resp = requests.get("http://connectivitycheck.platform.hicloud.com/generate_204", timeout=3)
            return resp.status_code == 204
        except:
            return False

    def load_configuration(self):
        """安全加载配置（修复重复输入问题）"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                # 清空现有输入
                self.usr_entry.delete(0, tk.END)
                self.pwd_entry.delete(0, tk.END)
                # 插入新值
                self.usr_entry.insert(0, config.get('username', ''))
                self.pwd_entry.insert(0, config.get('password', ''))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._log(f"配置加载失败: {str(e)}")

    def _save_config(self):
        """安全保存配置"""
        config = {
            'username': self.usr_entry.get(),
            'password': self.pwd_entry.get()
        }
        try:
            # 创建配置目录（如果不存在）
            self.config_path.parent.mkdir(exist_ok=True)
            # 原子写入操作
            temp_path = self.config_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(config, f, ensure_ascii=False)
            temp_path.replace(self.config_path)
            self._log("配置已安全保存")
        except Exception as e:
            self._log(f"保存失败: {str(e)}")
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def _manual_login(self):
        self._log("正在尝试手动登录...")
        auth = AuthManager(logger=self._log)
        success = auth.login_flow(self.usr_entry.get(), self.pwd_entry.get())

        if success and auth.check_online():
            messagebox.showinfo("成功", "登录验证通过")
            self._log("手动登录成功")
        else:
            messagebox.showerror("失败", "认证失败，请检查网络和凭证")
            self._log("登录失败")

    def _auto_login(self):
        self._log("检测到网络断开，尝试自动登录...")
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                auth = AuthManager(logger=self._log)
                if auth.login_flow(config['username'], config['password']):
                    self._log("自动登录成功")
        except Exception as e:
            self._log(f"自动登录错误: {str(e)}")

    def _log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log.see(tk.END)

    def quit_app(self):
        self.running = False
        if self.daemon:
            self.daemon.stop()
        self.tray.quit_app()

    def show_debug(self):
        debug_win = tk.Toplevel()
        debug_win.title("调试信息")

        # 显示当前网络状态
        ttk.Label(debug_win, text="当前SSID:").grid(row=0, column=0)
        self.ssid_label = ttk.Label(debug_win, text=self.daemon._get_current_ssid())
        self.ssid_label.grid(row=0, column=1)

        # 显示原始认证参数
        ttk.Button(debug_win, text="获取认证参数", command=self._show_auth_params).grid(row=1, columnspan=2)

    def _show_auth_params(self):
        from .auth_system import AuthManager
        auth = AuthManager()
        try:
            portal_res = auth.session.get("http://2.2.2.2")
            params = auth._decode_params(portal_res.url)
            messagebox.showinfo("调试参数",
                                f"原始URL: {portal_res.url}\n"
                                f"解析参数: {params}\n"
                                f"UserAgent: {auth.session.headers['User-Agent']}"
                                )
        except Exception as e:
            messagebox.showerror("调试错误", str(e))


if __name__ == "__main__":
    if platform.system() == 'Windows':
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)  # 启用高DPI支持

    app = LoginGUI()
    app.mainloop()