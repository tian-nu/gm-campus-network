#!/usr/bin/env python3
"""
校园网认证系统主入口
版本: 2.1
功能:
1. 初始化核心组件
2. 处理跨平台启动
3. 异常安全启动
4. 日志系统配置
"""

import sys
import os
import logging
from pathlib import Path
import platform
from src.interface import LoginGUI


def configure_runtime():
    """配置运行时环境"""
    # 确保工作目录正确
    if getattr(sys, 'frozen', False):  # 打包环境
        os.chdir(sys._MEIPASS)
    else:  # 开发环境
        os.chdir(str(Path(__file__).parent))

    # 初始化日志系统
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("campus_auth.log"),
            logging.StreamHandler()
        ]
    )


def check_singleton():
    """确保单实例运行"""
    if platform.system() == 'Windows':
        from win32event import CreateMutex
        from win32api import GetLastError
        from winerror import ERROR_ALREADY_EXISTS
        mutex = CreateMutex(None, False, "CampusAuthMutex")
        return GetLastError() == ERROR_ALREADY_EXISTS
    else:
        import fcntl
        lock_file = Path(__file__).parent / ".lock"
        try:
            fd = os.open(lock_file, os.O_WRONLY | os.O_CREAT)
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except IOError:
            return True


def main():
    # 单实例检查
    if check_singleton():
        print("程序已在运行中")
        sys.exit(1)

    # 环境配置
    try:
        configure_runtime()
    except Exception as e:
        print(f"环境初始化失败: {str(e)}")
        sys.exit(2)

    # 启动主程序
    try:
        # Windows高DPI支持
        if platform.system() == 'Windows':
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)

        # 创建GUI实例
        app = LoginGUI()

        # 启动消息循环
        app.mainloop()

    except Exception as e:
        logging.critical(f"致命错误: {str(e)}", exc_info=True)
        sys.exit(3)
    finally:
        logging.info("程序已安全退出")


if __name__ == "__main__":
    main()