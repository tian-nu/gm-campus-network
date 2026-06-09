# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Project\\python\\自动登录工贸校园网\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\Project\\python\\自动登录工贸校园网\\icon.ico', '.')],
    hiddenimports=['requests', 'campus_net_auth'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'hypothesis', 'coverage', 'pytest_cov', 'setuptools', 'pip', 'wheel', 'Pygments', 'pygments', 'IPython', 'notebook', 'tkinter.test', 'unittest', 'xmlrpc', 'pydoc', 'doctest', 'lib2to3', 'curses', 'idlelib', 'pywin32-ctypes'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='校园网自动认证工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='D:\\Project\\python\\自动登录工贸校园网\\version_info.txt',
    icon=['D:\\Project\\python\\自动登录工贸校园网\\icon.ico'],
)
