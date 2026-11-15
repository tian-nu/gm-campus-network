#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动认证工具 v3.0

2026-11 学校把认证系统换成了 Panabit RAAS + 统一身份认证，
v3.0 重写了认证层，图形界面和服务框架沿用。

用法：
    python main.py                 打开图形界面
    python main.py --daemon        无界面常驻，掉线自动重连（适合开机自启）
    python main.py --once          只认证一次，打印结果后退出
    python main.py --status        只查当前在线状态
"""

import argparse
import os
import signal
import sys
import time

# Windows 高 DPI 支持（必须在创建 Tk 实例之前）
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        pass

# 确保模块路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load():
    """加载配置 + 日志 + 认证器"""
    from campus_net_auth.config.manager import ConfigManager
    from campus_net_auth.core.authenticator import CampusNetAuthenticator
    from campus_net_auth.core.constants import Constants
    from campus_net_auth.utils.logger import setup_logging

    config = ConfigManager().load()
    logger = setup_logging(
        debug_mode=config.get("debug_mode", False),
        log_file=Constants.LOG_FILE,
    )
    return config, logger, CampusNetAuthenticator(config)


def cmd_status() -> int:
    """打印当前认证状态"""
    config, logger, auth = _load()
    info = auth.get_status_summary()

    print("网卡   : %s" % (info["adapter"] or "未识别"))
    print("IP     : %s" % (info["ip"] or "-"))
    print("MAC    : %s" % (info["mac"] or "-"))

    if info["online"]:
        print("状态   : 已在线")
        print("账号   : %s" % (info["username"] or "-"))
        print("时长   : %s" % (info["session_time"] or "-"))
        return 0

    print("状态   : 未认证（需要登录）")
    return 1


def cmd_once() -> int:
    """认证一次"""
    config, logger, auth = _load()
    username = (config.get("username") or "").strip()
    password = (config.get("password") or "").strip()
    if not username or not password:
        print("配置里没有账号或密码，请先运行 python main.py 在界面里填一次。")
        return 2

    ok, msg = auth.login(username, password)
    print(("[成功] " if ok else "[失败] ") + msg)
    return 0 if ok else 1


def cmd_daemon(interval: int = None) -> int:
    """
    无界面常驻：掉线就重新认证。

    开机自启时网卡可能还没起来，所以启动阶段用短间隔重试，
    连续失败再逐步拉长，避免把账号认证次数打满。
    """
    config, logger, auth = _load()
    username = (config.get("username") or "").strip()
    password = (config.get("password") or "").strip()
    if not username or not password:
        logger.error("配置里没有账号或密码，daemon 无法启动")
        print("配置里没有账号或密码，请先运行 python main.py 在界面里填一次。")
        return 2

    check_interval = interval or int(config.get("reconnect_interval", 30))
    cooldown = int(config.get("reconnect_cooldown", 30))

    stopping = {"flag": False}

    def _stop(signum, frame):
        stopping["flag"] = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info("daemon 启动：用户 %s，检测间隔 %ds", username, check_interval)

    failures = 0
    last_attempt = 0.0
    next_check = time.time()

    while not stopping["flag"]:
        now = time.time()
        if now < next_check:
            time.sleep(min(1.0, next_check - now))
            continue

        try:
            if auth.detect_network_status():
                if failures:
                    logger.info("网络已恢复")
                failures = 0
                next_check = now + check_interval
                continue

            # 需要认证：失败后退避，别把账号认证次数刷爆
            wait = min(cooldown * (2 ** min(failures, 4)), 600)
            if now - last_attempt < wait:
                next_check = last_attempt + wait
                continue

            last_attempt = now
            logger.info("检测到未认证，开始登录（连续失败 %d 次）", failures)
            ok, msg = auth.login(username, password)
            if ok:
                logger.info("登录成功：%s", msg)
                failures = 0
                next_check = time.time() + check_interval
            else:
                failures += 1
                logger.warning("登录失败：%s", msg)
                next_check = time.time() + min(cooldown * (2 ** min(failures, 4)), 600)

        except Exception as e:
            logger.exception("daemon 循环异常：%s", e)
            next_check = time.time() + 60

    logger.info("daemon 退出")
    return 0


def cmd_setup() -> int:
    """交互式写入账号密码（无界面环境用）"""
    import getpass
    from campus_net_auth.config.manager import ConfigManager

    manager = ConfigManager()
    config = manager.load()

    current = (config.get("username") or "").strip()
    prompt = "学号%s: " % ("[%s]" % current if current else "")
    username = input(prompt).strip() or current
    if not username:
        print("学号不能为空")
        return 2

    password = getpass.getpass("密码（输入时不显示）: ").strip()
    if not password:
        print("密码不能为空")
        return 2

    config["username"] = username
    config["password"] = password
    config["auto_login"] = True
    if manager.save(config):
        print("已保存到 %s" % manager.config_file)
        return 0

    print("保存失败")
    return 1


def cmd_gui() -> int:
    """打开图形界面"""
    from tkinter import Tk
    from campus_net_auth.gui.app import CampusNetApp

    root = Tk()
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    CampusNetApp(root).run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="校园网自动认证工具 v3.0")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--daemon", action="store_true", help="无界面常驻，掉线自动重连")
    group.add_argument("--once", action="store_true", help="只认证一次")
    group.add_argument("--status", action="store_true", help="只查在线状态")
    group.add_argument("--setup", action="store_true", help="交互式写入账号密码")
    parser.add_argument("--interval", type=int, default=None, help="daemon 检测间隔（秒）")
    args = parser.parse_args()

    if args.status:
        return cmd_status()
    if args.setup:
        return cmd_setup()
    if args.once:
        return cmd_once()
    if args.daemon:
        return cmd_daemon(args.interval)
    return cmd_gui()


if __name__ == "__main__":
    sys.exit(main())
