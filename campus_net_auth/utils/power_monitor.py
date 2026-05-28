"""
Windows 电源事件监听器
通过子类化 Tkinter 窗口的 WndProc 拦截 WM_POWERBROADCAST 消息，
精准检测系统睡眠/休眠/唤醒事件，无需轮询。
"""

import logging
import sys
from typing import Callable, Optional

# 仅在 Windows 上可用
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    # Windows 消息常量
    WM_POWERBROADCAST = 0x0218

    # 电源事件类型
    PBT_APMSUSPEND = 0x0004              # 系统即将进入睡眠
    PBT_APMRESUMEAUTOMATIC = 0x0012      # 系统自动唤醒（也可能伴随 PBT_APMRESUMESUSPEND）
    PBT_APMRESUMESUSPEND = 0x0007        # 系统因用户操作唤醒
    PBT_POWERSETTINGCHANGE = 0x8013      # 电源设置变化

    # SetWindowLongPtr 在 32/64 位下名称不同
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        SetWindowLongPtr = ctypes.windll.user32.SetWindowLongPtrW
        GetWindowLongPtr = ctypes.windll.user32.GetWindowLongPtrW
        GWLP_WNDPROC = -4
    else:
        SetWindowLongPtr = ctypes.windll.user32.SetWindowLongW
        GetWindowLongPtr = ctypes.windll.user32.GetWindowLongW
        GWL_WNDPROC = -4

    CallWindowProc = ctypes.windll.user32.CallWindowProcW

    # WndProc 类型
    WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_long,   # LRESULT
        ctypes.c_void_p, # HWND
        ctypes.c_uint,   # MSG
        ctypes.c_void_p, # WPARAM
        ctypes.c_void_p, # LPARAM
    )


class PowerMonitor:
    """
    Windows 电源事件监听器

    通过子类化 Tkinter 窗口的 WndProc，拦截 WM_POWERBROADCAST 消息，
    在系统睡眠/唤醒时触发回调，无需轮询，零延迟零误判。

    用法：
        monitor = PowerMonitor(tk_root, on_resume=callback, on_suspend=callback)
        monitor.start()
        # ... 退出时
        monitor.stop()
    """

    def __init__(
        self,
        root,
        on_resume: Optional[Callable[[], None]] = None,
        on_suspend: Optional[Callable[[], None]] = None,
    ):
        """
        初始化电源监听器

        Args:
            root: Tkinter 根窗口
            on_resume: 系统唤醒回调
            on_suspend: 系统睡眠回调
        """
        self.logger = logging.getLogger(__name__)
        self.root = root
        self.on_resume = on_resume
        self.on_suspend = on_suspend
        self._is_monitoring = False
        self._original_wndproc = None
        self._new_wndproc = None

    @property
    def is_running(self) -> bool:
        """是否正在监听"""
        return self._is_monitoring and self._original_wndproc is not None

    def start(self) -> None:
        """启动电源事件监听"""
        if sys.platform != "win32":
            self.logger.debug("非 Windows 平台，跳过电源监听")
            return

        if self._is_monitoring:
            self.logger.warning("电源监听已在运行")
            return

        try:
            hwnd = self.root.winfo_id()
            if not hwnd:
                self.logger.error("无法获取 Tkinter 窗口句柄")
                return

            # 保存原始 WndProc
            self._original_wndproc = GetWindowLongPtr(hwnd, GWLP_WNDPROC if ctypes.sizeof(ctypes.c_void_p) == 4 else -4)
            if not self._original_wndproc:
                self.logger.error("无法获取原始 WndProc")
                return

            # 创建新的 WndProc 回调
            original = self._original_wndproc

            def _wnd_proc(hwnd, msg, wparam, lparam):
                """自定义 WndProc：拦截电源消息，其余交给原始处理器"""
                if msg == WM_POWERBROADCAST:
                    event_type = wparam
                    if event_type in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                        self.logger.info(f"检测到系统唤醒事件 (0x{event_type:04X})")
                        if self.on_resume:
                            try:
                                self.on_resume()
                            except Exception as e:
                                self.logger.error(f"唤醒回调异常: {e}")
                    elif event_type == PBT_APMSUSPEND:
                        self.logger.info("检测到系统进入睡眠")
                        if self.on_suspend:
                            try:
                                self.on_suspend()
                            except Exception as e:
                                self.logger.error(f"睡眠回调异常: {e}")
                    # 返回 TRUE 表示已处理
                    return 1

                # 其他消息交给原始 WndProc
                return CallWindowProc(original, hwnd, msg, wparam, lparam)

            self._new_wndproc = WNDPROC(_wnd_proc)

            # 替换 WndProc
            result = SetWindowLongPtr(
                hwnd,
                GWLP_WNDPROC if ctypes.sizeof(ctypes.c_void_p) == 4 else -4,
                ctypes.cast(self._new_wndproc, ctypes.c_void_p).value,
            )

            if not result:
                self.logger.error("SetWindowLongPtr 失败")
                self._original_wndproc = None
                self._new_wndproc = None
                return

            self._is_monitoring = True
            self.logger.info("电源事件监听已启动")

        except Exception as e:
            self.logger.error(f"启动电源监听失败: {e}")
            self._original_wndproc = None
            self._new_wndproc = None

    def stop(self) -> None:
        """停止电源事件监听，恢复原始 WndProc"""
        if not self._is_monitoring or not self._original_wndproc:
            return

        try:
            hwnd = self.root.winfo_id()
            if hwnd:
                SetWindowLongPtr(
                    hwnd,
                    GWLP_WNDPROC if ctypes.sizeof(ctypes.c_void_p) == 4 else -4,
                    self._original_wndproc,
                )
        except Exception as e:
            self.logger.error(f"恢复 WndProc 失败: {e}")

        self._is_monitoring = False
        self._original_wndproc = None
        self._new_wndproc = None
        self.logger.info("电源事件监听已停止")
