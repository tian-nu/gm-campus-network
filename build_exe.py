#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包脚本 - 使用 PyInstaller 在 .venv 环境中打包为 exe
优化：排除测试/开发依赖，精简导入，支持 UPX 压缩
"""

import os
import sys
import subprocess
import shutil

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# .venv Python 路径
VENV_PYTHON = os.path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')


def resolve_python():
    """
    选打包用的解释器：有项目内 .venv 就优先用它，没有就退回当前解释器。

    原来这里硬编码 .venv 且找不到就 exit(1)，而仓库里根本没有这个目录，
    脚本等于完全跑不起来。现在两种环境都能打。
    """
    if os.path.isfile(VENV_PYTHON):
        return VENV_PYTHON
    print(f"[--] 未找到 .venv（{VENV_PYTHON}），改用当前解释器")
    return sys.executable


def _installed_packages(python_exe):
    """取已安装包名集合（小写），用于判断依赖是否齐"""
    result = subprocess.run(
        [python_exe, '-m', 'pip', 'list', '--format=freeze'],
        capture_output=True, text=True
    )
    names = set()
    for line in result.stdout.splitlines():
        if '==' in line:
            names.add(line.split('==', 1)[0].strip().lower())
    return names


def check_deps(python_exe):
    """检查并补齐打包所需的依赖（运行时依赖 + PyInstaller）"""
    required = ['requests', 'pystray', 'pillow', 'pyinstaller']
    installed = _installed_packages(python_exe)
    missing = [pkg for pkg in required if pkg not in installed]
    if missing:
        print(f"[!!] 缺少依赖: {', '.join(missing)}")
        print("正在安装...")
        subprocess.run(
            [python_exe, '-m', 'pip', 'install'] + missing,
            check=True
        )
        print("[OK] 依赖安装完成")
    else:
        print("[OK] 依赖检查通过")


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ['build', 'dist']
    for dir_name in dirs_to_remove:
        dir_path = os.path.join(PROJECT_ROOT, dir_name)
        if os.path.exists(dir_path):
            print(f"清理 {dir_name} 目录...")
            shutil.rmtree(dir_path)

    # 清理 spec 文件
    for file in os.listdir(PROJECT_ROOT):
        if file.endswith('.spec'):
            print(f"删除 {file}...")
            os.remove(os.path.join(PROJECT_ROOT, file))


def build_exe(python_exe):
    """打包 exe"""
    print("开始打包...")

    # 运行时真正需要的第三方包：requests, PIL, pystray
    # tkinter 是标准库，PyInstaller 自动处理
    # 项目内部模块通过 __init__.py 链式导入，只需指定顶层包

    args = [
        python_exe, '-m', 'PyInstaller',

        '--name=校园网自动认证工具',
        '--windowed',   # GUI 应用，不显示控制台
        '--onefile',    # 打包为单个 exe
        '--clean',
        '--noconfirm',

        '--hidden-import', 'requests',
        '--hidden-import', 'campus_net_auth',
        # pystray 的后端是运行时动态导入的，PyInstaller 静态分析抓不到
        '--hidden-import', 'pystray._win32',
        '--hidden-import', 'PIL._tkinter_finder',

        # 排除不需要的大型模块（减小体积）
        '--exclude-module', 'pytest',
        '--exclude-module', 'hypothesis',
        '--exclude-module', 'coverage',
        '--exclude-module', 'pytest_cov',
        '--exclude-module', 'setuptools',
        '--exclude-module', 'pip',
        '--exclude-module', 'wheel',
        '--exclude-module', 'Pygments',
        '--exclude-module', 'pygments',
        '--exclude-module', 'IPython',
        '--exclude-module', 'notebook',
        '--exclude-module', 'tkinter.test',
        '--exclude-module', 'unittest',
        '--exclude-module', 'xmlrpc',
        '--exclude-module', 'pydoc',
        '--exclude-module', 'doctest',
        '--exclude-module', 'lib2to3',
        '--exclude-module', 'curses',
        '--exclude-module', 'idlelib',
        '--exclude-module', 'pywin32-ctypes',

        # 主入口文件
        os.path.join(PROJECT_ROOT, 'main.py')
    ]

    # 图标（作为 exe 图标 + 运行时托盘图标）
    icon_path = os.path.join(PROJECT_ROOT, 'icon.ico')
    if os.path.exists(icon_path):
        args.extend([f'--icon={icon_path}'])
        # 将 icon.ico 打包进 exe，运行时从 sys._MEIPASS 读取
        args.extend([f'--add-data={icon_path};.'])

    # 版本信息
    version_file = os.path.join(PROJECT_ROOT, '.project', 'docs', 'version_info.txt')
    if os.path.exists(version_file):
        args.extend([f'--version-file={version_file}'])

    # UPX 压缩（如果可用）
    upx_dir = os.path.join(PROJECT_ROOT, 'upx')
    if os.path.isdir(upx_dir):
        args.extend([f'--upx-dir={upx_dir}'])
        print("[OK] 检测到 UPX，将启用压缩")

    # 执行打包
    print("PyInstaller 命令:")
    print(' '.join(args))
    print()

    result = subprocess.run(args, capture_output=True, text=True,
                            cwd=PROJECT_ROOT)

    if result.returncode == 0:
        print("[OK] 打包成功！")
        exe_path = os.path.join(PROJECT_ROOT, 'dist', '校园网自动认证工具.exe')
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"[OK] 生成文件: {exe_path}")
            print(f"[OK] 文件大小: {size_mb:.2f} MB")
        return True
    else:
        print("[FAIL] 打包失败！")
        print("错误输出:")
        print(result.stderr[-3000:] if len(result.stderr) > 3000 else result.stderr)
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("校园网自动认证工具 - 打包脚本")
    print("=" * 50)
    print()

    # 1. 选定解释器
    python_exe = resolve_python()
    print(f"[OK] 使用解释器: {python_exe}")
    print()

    # 2. 检查依赖
    check_deps(python_exe)
    print()

    # 3. 清理旧构建
    clean_build()
    print()

    # 4. 打包
    if build_exe(python_exe):
        print()
        print("=" * 50)
        print("打包完成！")
        print("=" * 50)
        print()
        print("输出文件: dist/校园网自动认证工具.exe")
        print()
        print("提示:")
        print("- 首次运行可能需要几秒钟启动")
        print("- 如果被杀毒软件拦截，请添加信任")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
