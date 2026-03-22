#!/usr/bin/env python3
"""
调试托盘功能
"""

import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, '.')

def main():
    from campus_net_auth.gui.tray import SystemTray, TRAY_AVAILABLE
    
    print("=" * 60)
    print("托盘功能调试")
    print("=" * 60)
    print(f"\nTRAY_AVAILABLE: {TRAY_AVAILABLE}")
    
    # 创建主窗口
    root = tk.Tk()
    root.title("调试窗口")
    root.geometry("500x400")
    
    # 状态标签
    status_var = tk.StringVar(value="状态: 窗口显示中")
    status_label = tk.Label(root, textvariable=status_var, font=("Arial", 14))
    status_label.pack(pady=20)
    
    # 日志文本框
    log_text = tk.Text(root, height=10, width=50)
    log_text.pack(pady=10)
    
    def log(msg):
        """添加日志"""
        print(msg)
        log_text.insert("end", msg + "\n")
        log_text.see("end")
    
    def on_show():
        """显示窗口回调"""
        log("📱 on_show 被调用")
        log("   停止托盘...")
        tray.stop()
        log("   调用 deiconify() 显示窗口...")
        root.deiconify()
        log("   调用 lift()...")
        root.lift()
        log("   调用 focus_force()...")
        root.focus_force()
        status_var.set("状态: 窗口显示中")
        log("✅ 窗口已恢复")
    
    def on_quit():
        """退出回调"""
        log("👋 on_quit 被调用")
        tray.stop()
        root.destroy()
    
    def minimize_to_tray():
        """最小化到托盘"""
        log("\n🔽 minimize_to_tray 被调用")
        
        if not TRAY_AVAILABLE:
            log("❌ TRAY_AVAILABLE = False")
            return
        
        if not tray.is_available:
            log("❌ tray.is_available = False")
            return
        
        log("✅ 托盘可用")
        log("   调用 withdraw() 隐藏窗口...")
        root.withdraw()
        log("   窗口已隐藏")
        
        log("   启动托盘...")
        success = tray.start()
        log(f"   托盘启动结果: {success}")
        
        if success:
            status_var.set("状态: 已最小化到托盘")
            log("✅ 已最小化到托盘")
            log("   请查看系统托盘区域（任务栏右侧小箭头）")
        else:
            log("❌ 托盘启动失败，恢复窗口")
            root.deiconify()
            status_var.set("状态: 托盘启动失败")
    
    # 创建托盘
    log("创建 SystemTray 实例...")
    tray = SystemTray(on_show=on_show, on_quit=on_quit)
    log(f"托盘实例创建完成")
    log(f"  - is_available: {tray.is_available}")
    log(f"  - is_running: {tray.is_running}")
    
    # 按钮
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=20)
    
    tk.Button(btn_frame, text="🔽 最小化到托盘", command=minimize_to_tray,
              font=("Arial", 12), width=20).pack(side=tk.LEFT, padx=5)
    
    tk.Button(btn_frame, text="❌ 退出", command=on_quit,
              font=("Arial", 12), width=15).pack(side=tk.LEFT, padx=5)
    
    # 说明
    info = tk.Label(root, text="点击'最小化到托盘'后，窗口应该完全消失\n"
                               "只在系统托盘区域显示图标",
                    font=("Arial", 10), fg="gray")
    info.pack(pady=20)
    
    log("\n窗口已创建，请点击按钮测试")
    
    root.mainloop()
    log("\n程序结束")

if __name__ == "__main__":
    main()
