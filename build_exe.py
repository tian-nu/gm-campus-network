#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包脚本 - 使用PyInstaller打包为exe
"""

import os
import sys
import subprocess
import shutil


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ['build', 'dist']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            print(f"清理 {dir_name} 目录...")
            shutil.rmtree(dir_name)
    
    # 清理spec文件
    for file in os.listdir('.'):
        if file.endswith('.spec'):
            print(f"删除 {file}...")
            os.remove(file)


def build_exe():
    """打包exe"""
    print("开始打包...")
    
    # PyInstaller参数
    args = [
        'pyinstaller',
        '--name=校园网自动认证工具',
        '--windowed',  # GUI应用，不显示控制台
        '--onefile',   # 打包为单个exe文件
        '--clean',     # 清理临时文件
        '--noconfirm', # 不确认覆盖
        
        # 添加数据文件
        '--add-data', 'campus_net_auth;campus_net_auth',
        
        # 隐藏导入（确保所有模块都被打包）
        '--hidden-import', 'tkinter',
        '--hidden-import', 'requests',
        '--hidden-import', 'PIL',
        '--hidden-import', 'pystray',
        '--hidden-import', 'campus_net_auth',
        '--hidden-import', 'campus_net_auth.core',
        '--hidden-import', 'campus_net_auth.core.authenticator',
        '--hidden-import', 'campus_net_auth.core.network',
        '--hidden-import', 'campus_net_auth.core.constants',
        '--hidden-import', 'campus_net_auth.config',
        '--hidden-import', 'campus_net_auth.config.manager',
        '--hidden-import', 'campus_net_auth.config.defaults',
        '--hidden-import', 'campus_net_auth.gui',
        '--hidden-import', 'campus_net_auth.gui.app',
        '--hidden-import', 'campus_net_auth.gui.tray',
        '--hidden-import', 'campus_net_auth.gui.widgets',
        '--hidden-import', 'campus_net_auth.gui.tabs.login',
        '--hidden-import', 'campus_net_auth.gui.tabs.settings',
        '--hidden-import', 'campus_net_auth.gui.tabs.logs',
        '--hidden-import', 'campus_net_auth.utils',
        '--hidden-import', 'campus_net_auth.utils.logger',
        '--hidden-import', 'campus_net_auth.utils.network_info',
        '--hidden-import', 'campus_net_auth.utils.network_monitor',
        
        # 主入口文件
        'main.py'
    ]
    
    # 如果有图标文件，添加图标
    if os.path.exists('icon.ico'):
        args.extend(['--icon=icon.ico'])
    
    # 执行打包
    result = subprocess.run(args, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ 打包成功！")
        exe_path = os.path.join('dist', '校园网自动认证工具.exe')
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"✓ 生成文件: {exe_path}")
            print(f"✓ 文件大小: {size_mb:.2f} MB")
        return True
    else:
        print("✗ 打包失败！")
        print("错误输出:")
        print(result.stderr)
        return False


def create_version_info():
    """创建版本信息文件"""
    version_info = '''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', ''),
        StringStruct('FileDescription', '校园网自动认证工具'),
        StringStruct('FileVersion', '1.0.0.0'),
        StringStruct('InternalName', 'CampusNetAuth'),
        StringStruct('LegalCopyright', ''),
        StringStruct('OriginalFilename', '校园网自动认证工具.exe'),
        StringStruct('ProductName', '校园网自动认证工具'),
        StringStruct('ProductVersion', '1.0.0.0')])
      ]), 
    VarFileInfo([VarStruct('Translation', [0x409, 1200])])
  ]
)'''
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    print("✓ 创建版本信息文件")


def main():
    """主函数"""
    print("=" * 50)
    print("校园网自动认证工具 - 打包脚本")
    print("=" * 50)
    print()
    
    # 检查pyinstaller是否安装
    try:
        import PyInstaller
        print("✓ PyInstaller 已安装")
    except ImportError:
        print("✗ PyInstaller 未安装，正在安装...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
        print("✓ PyInstaller 安装完成")
    
    print()
    
    # 清理旧构建
    clean_build()
    print()
    
    # 创建版本信息
    create_version_info()
    print()
    
    # 打包
    if build_exe():
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
