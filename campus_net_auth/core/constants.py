"""
系统常量定义
统一管理所有硬编码值，便于维护和配置
"""


class Constants:
    """系统常量"""

    # ==================== 网络认证相关 ====================
    PORTAL_IP = "10.10.21.129"
    CAS_DOMAIN = "cas.gzittc.com"
    PORTAL_DOMAIN = "xykd.gzittc.edu.cn"
    LOGOUT_PAGE = "xykd.gzittc.edu.cn/portal/usertemp_computer/gongmao-pc-2025/logout.html"
    WLAN_AC_NAME = "Ne8000-M14"

    # ==================== 网络检测 URL ====================
    TEST_URLS = [
        "http://connectivitycheck.gstatic.com/generate_204",
        "http://www.baidu.com/favicon.ico",
        "http://www.qq.com/favicon.ico",
    ]

    # ==================== HTTP 请求头 ====================
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # ==================== 日志配置 ====================
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"
    LOG_FILE = "campus_net.log"

    # ==================== GUI 相关 ====================
    WINDOW_TITLE = "校园网自动认证工具 v2.0"
    WINDOW_SIZE = "450x650"
    MIN_WINDOW_SIZE = (400, 550)

    # 字体配置
    FONT_FAMILY = "Microsoft YaHei UI"
    FONT_SIZE_NORMAL = 10
    FONT_SIZE_LARGE = 12
    FONT_SIZE_TITLE = 18

    # 颜色配置
    COLOR_PRIMARY = "#2196F3"
    COLOR_SUCCESS = "#4CAF50"
    COLOR_ERROR = "#F44336"
    COLOR_WARNING = "#FF9800"
    COLOR_TEXT = "#333333"
    COLOR_TEXT_SECONDARY = "#666666"
    COLOR_BACKGROUND = "#FFFFFF"
    COLOR_BORDER = "#E0E0E0"

    # ==================== 超时和重试 ====================
    DEFAULT_TIMEOUT = 10
    DEFAULT_MAX_RETRIES = 3
    MAX_REDIRECTS = 10

    # ==================== 心跳和重连 ====================
    DEFAULT_HEARTBEAT_INTERVAL = 120
    DEFAULT_RECONNECT_INTERVAL = 30
    DEFAULT_RECONNECT_COOLDOWN = 30
    DEFAULT_HEARTBEAT_URL = "http://www.baidu.com/favicon.ico"
