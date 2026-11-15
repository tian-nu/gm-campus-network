#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开机自启管理

用「启动文件夹 + VBS 静默启动」的方式，不需要管理员权限，
也不需要动任务计划程序（那个要提权，很多同学装不上）。

用法：
    python tools/autostart.py install     安装
    python tools/autostart.py uninstall   卸载
    python tools/autostart.py status      查看状态
"""

import os
import subprocess
import sys

TASK_NAME = "GMCampusNetAuth.vbs"


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def startup_dir() -> str:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("找不到 APPDATA 环境变量")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def _can_import(python_exe: str) -> bool:
    """确认这个解释器装了 requests，否则开机后会静默失败"""
    try:
        result = subprocess.run(
            [python_exe, "-c", "import requests"],
            capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except Exception:
        return False


def find_pythonw() -> str:
    """
    找一个「有 pythonw 且装了 requests」的解释器。

    优先项目自己的 venv，其次 PATH 里的 pythonw，
    最后退化成当前解释器（会有黑窗口，但至少能跑）。
    """
    root = project_root()
    candidates = []

    # 1. 项目自己的 venv
    for venv in (os.path.join(root, ".venv"),
                 os.path.join(os.path.dirname(root), ".venv")):
        for exe in ("pythonw.exe", "python.exe"):
            path = os.path.join(venv, "Scripts", exe)
            if os.path.exists(path):
                candidates.append(path)

    # 2. PATH 里的 pythonw / python
    for name in ("pythonw", "python"):
        try:
            out = subprocess.run(["where", name], capture_output=True, timeout=5).stdout
            for line in out.decode("gbk", "replace").splitlines():
                line = line.strip()
                if line and os.path.exists(line):
                    candidates.append(line)
        except Exception:
            pass

    # 3. 当前解释器
    candidates.append(sys.executable)

    seen = set()
    for path in candidates:
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        if _can_import(path):
            return path

    return sys.executable


def build_vbs(pythonw: str, main_py: str) -> str:
    """
    生成 VBS。用 WScript.Shell.Run 的第二个参数 0 = 隐藏窗口，
    第三个参数 False = 不等待，这样登录时不会卡住桌面。

    路径里可能有空格，所以要用引号包起来。这里用 Chr(34) 拼引号而不是
    写 \\"\\"，VBScript 里双引号的转义规则很绕（"" 表示一个字面引号），
    拼起来容易出错，用 Chr(34) 一眼就能看懂。
    """
    return (
        "' 校园网自动认证 - 开机静默启动（由 tools/autostart.py 生成）\r\n"
        "Set shell = CreateObject(\"WScript.Shell\")\r\n"
        "q = Chr(34)\r\n"
        "cmd = q & \"%s\" & q & \" \" & q & \"%s\" & q & \" --daemon\"\r\n"
        "shell.Run cmd, 0, False\r\n" % (pythonw, main_py)
    )


def install() -> int:
    root = project_root()
    main_py = os.path.join(root, "main.py")
    if not os.path.exists(main_py):
        print("找不到 main.py，请在项目目录内运行")
        return 1

    pythonw = find_pythonw()
    target = os.path.join(startup_dir(), TASK_NAME)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="gbk", newline="") as f:
        f.write(build_vbs(pythonw, main_py))

    print("已安装开机自启")
    print("  启动项 : %s" % target)
    print("  解释器 : %s" % pythonw)
    print("  命令   : main.py --daemon")
    print()
    print("下次登录 Windows 时会自动在后台运行。想立刻生效可以手动双击这个 vbs。")
    return 0


def uninstall() -> int:
    target = os.path.join(startup_dir(), TASK_NAME)
    if not os.path.exists(target):
        print("没有安装开机自启，无需卸载")
        return 0
    os.remove(target)
    print("已移除启动项：%s" % target)
    return 0


def status() -> int:
    target = os.path.join(startup_dir(), TASK_NAME)
    if os.path.exists(target):
        print("开机自启：已安装")
        print("  路径: %s" % target)
        with open(target, "r", encoding="gbk", errors="replace") as f:
            for line in f:
                if line.startswith("cmd ="):
                    print("  命令: %s" % line.strip())
        return 0
    print("开机自启：未安装")
    return 1


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    handlers = {"install": install, "uninstall": uninstall, "status": status}
    handler = handlers.get(action)
    if not handler:
        print(__doc__)
        return 2
    return handler()


if __name__ == "__main__":
    sys.exit(main())
