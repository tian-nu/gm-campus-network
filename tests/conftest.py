"""pytest 全局 fixtures"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="session")
def root():
    """
    全测试共用的 Tk 根窗口（隐藏）。

    原来每个测试类各自 Tk()/destroy()，在同一进程里反复创建 Tcl 解释器，
    Windows 上会偶发 `TclError: Can't find a usable init.tcl`，
    表现为每次跑都随机挂 0~2 个与功能无关的用例。
    改成整个会话只建一次，测试之间只建 Frame。
    """
    tk = pytest.importorskip("tkinter")
    try:
        win = tk.Tk()
    except tk.TclError:  # 无显示环境（CI/无头）
        pytest.skip("无可用显示环境，跳过 GUI 测试")
    win.withdraw()
    try:
        yield win
    finally:
        win.destroy()


@pytest.fixture(autouse=True)
def _mock_network_detection():
    """默认 mock：避免测试时真实的网络操作"""
    with patch("campus_net_auth.utils.network_info.NetworkInfo.get_network_info",
               return_value={"ip": "10.0.0.1", "mac": "00:00:00:00:00:00", "timestamp": 0}), \
         patch("campus_net_auth.utils.network_info.NetworkInfo.is_valid_ip",
               return_value=True), \
         patch("campus_net_auth.utils.network_info.NetworkInfo.is_valid_mac",
               return_value=True):
        yield
