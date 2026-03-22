#!/usr/bin/env python3
"""
简单的托盘功能测试
"""

import sys
import time
from tkinter import Tk, Button, Label

sys.path.insert(0, '.')

def test_tray():
    """测试托盘功能"""
    from campus_net_auth.gui.tray import SystemTray, TRAY_AVAILABLE
    
    print("=" * 60)
    print("系统托盘功能测试")
    print("=" * 60)
    
    print(f"\n托盘可用: {TRAY_AVAILABLE}")
    
    if not TRAY_AVAILABLE:
        print("请先安装 pystray: pip install pystray Pillow")
        return
    
    # 创建主窗口
    root = Tk()
    root.title("校园网认证工具")
    root.geometry("400x300")
    
    in_tray = False
    
    def on_show():
        """从托盘恢复窗口"""
        nonlocal in_tray
        print("📱 显示窗口")
        tray.stop()
        root.deiconify()  # 显示窗口
        root.lift()
        root.focus_force()
        in_tray = False
        status_label.config(text="状态: 窗口显示中")
    
    def on_quit():
        """退出程序"""
        print("👋 退出程序")
        tray.stop()
        root.destroy()
    
    def minimize_to_tray():
        """最小化到托盘"""
        nonlocal in_tray
        print("🔽 最小化到托盘")
        
        if not tray.is_available:
            print("⚠️ 托盘不可用")
            return
        
        # 隐藏窗口
        root.withdraw()
        
        # 启动托盘
        success = tray.start()
        if success:
            in_tray = True
            status_label.config(text="状态: 已最小化到托盘")
            print("✅ 已最小化到托盘，窗口已隐藏")
            print("   请查看系统托盘区域（任务栏右侧）")
        else:
            # 托盘启动失败，恢复窗口
            root.deiconify()
            status_label.config(text="状态: 托盘启动失败")
            print("❌ 托盘启动失败")
    
    # 创建托盘
    tray = SystemTray(on_show=on_show, on_quit=on_quit)
    
    # GUI控件
    Label(root, text="校园网认证工具", font=("Microsoft YaHei UI", 16, "bold")).pack(pady=20)
    
    status_label = Label(root, text="状态: 窗口显示中", font=("Microsoft YaHei UI", 12))
    status_label.pack(pady=10)
    
    Button(root, text="🔽 最小化到托盘", command=minimize_to_tray, 
           font=("Microsoft YaHei UI", 12), width=15).pack(pady=10)
    
    Button(root, text="❌ 退出程序", command=on_quit, 
           font=("Microsoft YaHei UI", 12), width=15).pack(pady=10)
    
    info_label = Label(root, text="点击'最小化到托盘'后，\n窗口会隐藏，图标会出现在系统托盘", 
                       font=("Microsoft YaHei UI", 10), fg="gray")
    info_label.pack(pady=20)
    
    print("\n窗口已创建")
    print("请点击'最小化到托盘'按钮测试")
    
    root.mainloop()
    print("\n测试结束")

if __name__ == "__main__":
    test_tray()
