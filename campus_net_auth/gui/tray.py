"""
系统托盘模块
提供最小化到托盘功能
"""

import logging
import threading
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


class SystemTray:
    """系统托盘管理器"""

    # 状态常量
    STATUS_ONLINE = "online"      # 在线
    STATUS_OFFLINE = "offline"    # 断开
    STATUS_RECONNECTING = "reconnecting"  # 重连中

    def __init__(
        self,
        on_show: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
        title: str = "校园网认证工具"
    ):
        """
        初始化系统托盘

        Args:
            on_show: 显示窗口回调
            on_quit: 退出程序回调
            title: 托盘图标标题
        """
        self.logger = logging.getLogger(__name__)
        self.on_show = on_show
        self.on_quit = on_quit
        self.title = title

        self._icon: Optional["pystray.Icon"] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._current_status: str = self.STATUS_OFFLINE  # 当前状态

    @property
    def is_available(self) -> bool:
        """托盘功能是否可用"""
        return TRAY_AVAILABLE

    @property
    def is_running(self) -> bool:
        """托盘是否正在运行"""
        return self._is_running and self._icon is not None

    def _create_icon_image(self, size: int = 64, status: str = None) -> "Image.Image":
        """
        创建托盘图标图像

        Args:
            size: 图标大小
            status: 状态 (online/offline/reconnecting)

        Returns:
            PIL Image 对象
        """
        # 根据状态选择颜色
        colors = {
            self.STATUS_ONLINE: "#4CAF50",      # 绿色
            self.STATUS_OFFLINE: "#F44336",     # 红色
            self.STATUS_RECONNECTING: "#FF9800"  # 黄色
        }
        color = colors.get(status or self._current_status, "#2196F3")

        # 创建图标
        image = Image.new("RGB", (size, size), color)
        draw = ImageDraw.Draw(image)

        # 绘制简单的网络图标
        margin = size // 4
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill="white"
        )
        draw.ellipse(
            [margin + 8, margin + 8, size - margin - 8, size - margin - 8],
            fill=color
        )

        return image

    def _on_show_click(self, icon, item) -> None:
        """显示窗口菜单项点击"""
        if self.on_show:
            self.on_show()

    def _on_quit_click(self, icon, item) -> None:
        """退出菜单项点击"""
        self.stop()
        if self.on_quit:
            self.on_quit()

    def start(self) -> bool:
        """
        启动系统托盘

        Returns:
            是否成功启动
        """
        if not TRAY_AVAILABLE:
            self.logger.warning("pystray 未安装，无法使用系统托盘")
            return False

        if self._is_running:
            return True

        try:
            # 创建菜单
            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", self._on_show_click, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._on_quit_click)
            )

            # 创建图标
            self._icon = pystray.Icon(
                "campus_net_auth",
                self._create_icon_image(),
                self.title,
                menu
            )

            # 在后台线程运行
            self._thread = threading.Thread(
                target=self._icon.run,
                name="TrayThread",
                daemon=True
            )
            self._thread.start()

            self._is_running = True
            self.logger.info("系统托盘已启动")
            return True

        except Exception as e:
            self.logger.error(f"启动系统托盘失败: {e}")
            return False

    def stop(self) -> None:
        """停止系统托盘"""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as e:
                self.logger.debug(f"停止托盘图标: {e}")

        self._icon = None
        self._is_running = False
        self.logger.info("系统托盘已停止")

    def update_title(self, title: str) -> None:
        """
        更新托盘标题

        Args:
            title: 新标题
        """
        self.title = title
        if self._icon is not None:
            try:
                self._icon.title = title
            except Exception:
                pass

    def update_status(self, status: str, tooltip: str = None) -> None:
        """
        更新托盘图标状态

        Args:
            status: 状态 (online/offline/reconnecting)
            tooltip: 可选的状态提示文本
        """
        self._current_status = status
        
        if self._icon is not None:
            try:
                # 更新图标
                self._icon.icon = self._create_icon_image(status=status)
                
                # 更新标题
                status_texts = {
                    self.STATUS_ONLINE: "在线",
                    self.STATUS_OFFLINE: "断开",
                    self.STATUS_RECONNECTING: "重连中"
                }
                status_text = status_texts.get(status, "")
                title = f"{self.title} - {status_text}"
                if tooltip:
                    title += f" ({tooltip})"
                self._icon.title = title
                
                self.logger.debug(f"托盘状态更新: {status_text}")
            except Exception as e:
                self.logger.debug(f"更新托盘状态失败: {e}")

    def show_notification(self, title: str, message: str) -> None:
        """
        显示托盘通知

        Args:
            title: 通知标题
            message: 通知内容
        """
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                self.logger.debug(f"显示通知失败: {e}")
