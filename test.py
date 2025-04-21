import os
import json
import time
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pystray import Icon, Menu, MenuItem
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import winreg as reg

CONFIG_FILE = "config.json"
CHECK_INTERVAL = 300  # 5分钟检测一次


class CampusAutoLogin:
    def __init__(self):
        self.load_config()
        self.setup_gui()
        self.running = True
        self.driver = None
        self.setup_tray_icon()
        self.setup_auto_start()
        self.start_check_thread()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("校园网自动登录")
        self.root.geometry("350x300")
        self.root.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)

        # GUI布局
        ttk.Label(self.root, text="目标WiFi:").grid(row=0, padx=10, pady=5, sticky="w")
        self.wifi_entry = ttk.Entry(self.root)
        self.wifi_entry.grid(row=0, column=1, padx=10, pady=5)
        self.wifi_entry.insert(0, self.config.get('target_wifi', "东1-living"))

        ttk.Label(self.root, text="学号:").grid(row=1, padx=10, pady=5, sticky="w")
        self.user_entry = ttk.Entry(self.root)
        self.user_entry.grid(row=1, column=1, padx=10, pady=5)
        self.user_entry.insert(0, self.config.get('username', ''))

        ttk.Label(self.root, text="密码:").grid(row=2, padx=10, pady=5, sticky="w")
        self.pass_entry = ttk.Entry(self.root, show="*")
        self.pass_entry.grid(row=2, column=1, padx=10, pady=5)
        self.pass_entry.insert(0, self.config.get('password', ''))

        self.auto_start_var = tk.BooleanVar(value=self.config.get('auto_start', False))
        ttk.Checkbutton(self.root, text="开机启动", variable=self.auto_start_var).grid(row=3, columnspan=2)

        # 新增按钮区域
        btn_frame = ttk.Frame(self.root)
        btn_frame.grid(row=4, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="完全退出", command=self.quit_app).pack(side=tk.LEFT, padx=5)

    def setup_tray_icon(self):
        image = Image.new('RGB', (64, 64), 'white')
        menu = Menu(
            MenuItem("显示窗口", self.show_window),
            MenuItem("完全退出", self.quit_app)
        )
        self.icon = Icon("autologin", image, "校园网自动登录", menu)

    def init_edge_driver(self):
        edge_options = webdriver.EdgeOptions()
        edge_options.use_chromium = True
        edge_options.add_argument("--headless")
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--no-sandbox")

        # 指定Edge驱动路径（需要根据实际路径修改）
        service = webdriver.edge.service.Service(executable_path='msedgedriver.exe')
        self.driver = webdriver.Edge(service=service, options=edge_options)

    def do_login(self):
        try:
            self.init_edge_driver()
            self.driver.get("http://2.2.2.2")

            try:
                # 等待登录按钮出现（最多等待10秒）
                login_btn = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "casAuth"))
                )
                login_btn.click()
                time.sleep(2)
            except:
                print("未找到单点登录按钮，尝试直接登录")

            # 处理CAS认证页面
            if "lyuapServer/login" in self.driver.current_url:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                ).send_keys(self.config['username'])

                self.driver.find_element(By.ID, "password").send_keys(self.config['password'])

                # 查找真正的提交按钮
                submit_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
                )
                submit_btn.click()
                time.sleep(5)

            return "认证成功" in self.driver.page_source
        except Exception as e:
            print(f"登录失败: {str(e)}")
            return False
        finally:
            if self.driver:
                self.driver.quit()

    # 其他方法保持不变...

    def quit_app(self):
        self.running = False
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass
        if hasattr(self, 'icon'):
            self.icon.stop()
        if hasattr(self, 'root'):
            self.root.destroy()
        os._exit(0)


if __name__ == "__main__":
    app = CampusAutoLogin()
    app.root.mainloop()