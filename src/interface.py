import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import json
import time
import os


class LoginGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("校园网认证")
        self.geometry("400x350")
        self.config_path = Path("config/settings.cfg")

        # 初始化组件
        self._create_widgets()
        self._load_config()

    def _create_widgets(self):
        # 输入区域
        ttk.Label(self, text="学号/账号:").grid(row=0, column=0, padx=10, pady=5)
        self.usr_entry = ttk.Entry(self)
        self.usr_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(self, text="密码:").grid(row=1, column=0, padx=10, pady=5)
        self.pwd_entry = ttk.Entry(self, show="*")
        self.pwd_entry.grid(row=1, column=1, padx=5, pady=5)

        # 控制按钮
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="保存配置", command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="立即登录", command=self._manual_login).pack(side=tk.LEFT, padx=5)

        # 状态显示
        self.status_var = tk.StringVar(value="状态: 等待操作")
        ttk.Label(self, textvariable=self.status_var).grid(row=3, column=0, columnspan=2)

        # 日志区域
        self.log = tk.Text(self, height=8, width=45)
        self.log.grid(row=4, column=0, columnspan=2, padx=10)

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.usr_entry.insert(0, config['username'])
                self.pwd_entry.insert(0, config['password'])
        except FileNotFoundError:
            pass

    def _save_config(self):
        config = {
            'username': self.usr_entry.get(),
            'password': self.pwd_entry.get()
        }
        # 确保配置文件所在目录存在
        config_dir = os.path.dirname(self.config_path)
        if config_dir:  # 避免目录名为空的情况（例如当前目录）
            os.makedirs(config_dir, exist_ok=True)

        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        self._update_status("配置已保存")

    def _update_status(self, message: str):
        self.status_var.set(f"状态: {message}")
        self.log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log.see(tk.END)

    def _manual_login(self):
        from .auth_system import AuthManager
        auth = AuthManager()
        success = auth.login_flow(self.usr_entry.get(), self.pwd_entry.get())
        if success:
            messagebox.showinfo("成功", "登录成功！")
            self._update_status("手动登录成功")
        else:
            messagebox.showerror("失败", "登录失败，请检查信息")
            self._update_status("登录失败")

    def run_daemon(self):
        from .network import NetworkDaemon
        self.daemon = NetworkDaemon(self._auto_login)
        self.daemon.start()

    def _auto_login(self):
        from .auth_system import AuthManager
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                auth = AuthManager()
                if auth.login_flow(config['username'], config['password']):
                    self._update_status("自动登录成功")
        except Exception as e:
            self._update_status(f"自动登录错误: {str(e)}")


if __name__ == "__main__":
    app = LoginGUI()
    app.run_daemon()
    app.mainloop()