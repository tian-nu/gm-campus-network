#!/usr/bin/env python3
"""
测试主程序的托盘功能
"""

import sys
sys.path.insert(0, '.')

def test_main_app_tray():
    """测试主应用的托盘功能"""
    from tkinter import Tk
    from campus_net_auth.gui.app import CampusNetApp
    
    print("=" * 60)
    print("测试主程序托盘功能")
    print("=" * 60)
    
    # 创建根窗口
    root = Tk()
    
    print("\n1. 创建 CampusNetApp...")
    try:
        app = CampusNetApp(root)
        print("   ✅ 应用创建成功")
        print(f"   - 托盘可用: {app.tray.is_available}")
        print(f"   - 托盘运行中: {app.tray.is_running}")
        print(f"   - in_tray: {app.in_tray}")
    except Exception as e:
        print(f"   ❌ 应用创建失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n2. 测试最小化到托盘...")
    try:
        # 直接调用最小化方法
        app._minimize_to_tray()
        print(f"   - 调用后 in_tray: {app.in_tray}")
        print(f"   - 托盘运行中: {app.tray.is_running}")
        
        # 等待一下
        import time
        time.sleep(1)
        
        print("\n3. 测试恢复窗口...")
        app._restore_window()
        print(f"   - 恢复后 in_tray: {app.in_tray}")
        print(f"   - 托盘运行中: {app.tray.is_running}")
        
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n4. 关闭应用...")
    try:
        app._on_closing()
        print("   ✅ 应用已关闭")
    except Exception as e:
        print(f"   ❌ 关闭失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_main_app_tray()
