#!/usr/bin/env python3
"""
测试系统托盘功能
"""

import sys
import time
import threading
from tkinter import Tk, Button, Label

sys.path.insert(0, '.')

from campus_net_auth.gui.tray import SystemTray

def test_tray():
    """测试托盘功能"""
    print("=" * 60)
    print("系统托盘功能测试")
    print("=" * 60)

    # 检查托盘是否可用
    print(f"\n1. 检查托盘可用性:")
    tray = SystemTray()
    print(f"   托盘可用: {tray.is_available}")

    if not tray.is_available:
        print("   ⚠️ pystray 未安装，无法测试托盘功能")
        print("   请运行: pip install pystray Pillow")
        return

    # 创建测试窗口
    root = Tk()
    root.title("托盘测试窗口")
    root.geometry("400x300")

    in_tray = False

    def on_show():
        nonlocal in_tray
        print("   📱 显示窗口回调被调用")
        tray.stop()
        root.deiconify()
        root.lift()
        root.focus_force()
        in_tray = False
        status_label.config(text="状态: 窗口显示中")

    def on_quit():
        print("   👋 退出回调被调用")
        tray.stop()
        root.destroy()

    def minimize_to_tray():
        nonlocal in_tray
        print("   🔽 最小化到托盘")
        if tray.is_available:
            root.withdraw()
            tray.start()
            in_tray = True
            status_label.config(text="状态: 已最小化到托盘")
            print("   ✅ 已最小化到托盘")
        else:
            root.iconify()
            status_label.config(text="状态: 已最小化到任务栏")

    def update_status():
        """循环更新状态"""
        statuses = ["online", "offline", "reconnecting"]
        status_names = ["在线", "断开", "重连中"]
        i = 0
        while True:
            time.sleep(3)
            if in_tray and tray.is_running:
                status = statuses[i % 3]
                tray.update_status(status)
                print(f"   🔄 托盘状态更新为: {status_names[i % 3]}")
                i += 1

    # 更新托盘回调
    tray.on_show = on_show
    tray.on_quit = on_quit

    # GUI控件
    Label(root, text="系统托盘测试", font=("Arial", 16)).pack(pady=20)

    status_label = Label(root, text="状态: 窗口显示中", font=("Arial", 12))
    status_label.pack(pady=10)

    Button(root, text="最小化到托盘", command=minimize_to_tray, font=("Arial", 12)).pack(pady=10)
    Button(root, text="显示通知", command=lambda: tray.show_notification("测试通知", "这是一条测试通知"), font=("Arial", 12)).pack(pady=10)
    Button(root, text="退出", command=on_quit, font=("Arial", 12)).pack(pady=10)

    # 启动状态更新线程
    threading.Thread(target=update_status, daemon=True).start()

    print("\n2. 测试窗口已创建")
    print("   请点击'最小化到托盘'按钮测试功能")
    print("   托盘图标右键可以显示菜单")

    root.mainloop()
    print("\n3. 测试完成")

if __name__ == "__main__":
    test_tray()
