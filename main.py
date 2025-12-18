#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动认证工具 v2.0
模块化重构版本

功能特点：
1. 自动检测网络状态
2. 自动认证校园网 CAS 系统
3. 心跳保持防止掉线
4. 断线自动重连
5. 自动获取 IP 和 MAC 地址
6. 现代化图形界面

使用方法：
    python main.py
"""

import sys
import os

# 确保模块路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tkinter import Tk
from campus_net_auth.gui.app import CampusNetApp


def main():
    """主函数"""
    # 创建根窗口
    root = Tk()

    # 设置窗口图标（如果存在）
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    # 创建并运行应用
    app = CampusNetApp(root)
    app.run()


if __name__ == "__main__":
    main()
