"""
系统常量定义
统一管理所有硬编码值，便于维护和配置

2026-11 更新：学校把认证系统整体换掉了。
    旧：华为 AC Portal（10.10.21.129 / portalScript.do）+ CAS（cas.gzittc.com）
    新：Panabit RAAS 认证计费（xskd.gzittc.edu.cn）+ 统一身份认证（oauth.gzittc.edu.cn）

旧域名已全部下线，v3.0 只保留新系统的常量。
"""


class Constants:
    """系统常量"""

    # ==================== 门户（Panabit RAAS） ====================
    # 认证页与接口都在这个域名下，HTTP 不通，只服务 HTTPS
    PORTAL_BASE = "https://xskd.gzittc.edu.cn"
    API_BASE = PORTAL_BASE + "/api/public"

    # 统一身份认证（SSO）
    SSO_BASE = "https://oauth.gzittc.edu.cn"
    OAUTH_CLIENT_ID = "panabit_raas"
    OAUTH_REDIRECT_PAGE = "/oauth.html"     # SSO 回调落到门户的这个页面
    OAUTH_STATE = "OAUTH"

    # ==================== 接口路径 ====================
    EP_STATUS = "/auth/info"                # 查当前 IP/MAC 的在线状态
    EP_CONF = "/index/conf"                 # 拉门户配置（判断哪些登录方式开着）
    EP_LOGIN = "/auth/login"                # 账号密码认证
    EP_RADIUS_PROXY = "/auth/radius_proxy"  # 代拨（运营商宽带账号）
    EP_PORTAL_PROXY = "/auth/portal_proxy"  # 代拨（运营商直连）
    EP_OAUTH_USER = "/oauth/query_user_info"  # 用 SSO 的 code 换认证
    EP_OAUTH_REAUTH = "/oauth/reauth"       # 账号密码重新认证（改密后/兜底用）

    # 接口返回码
    CODE_OK = 0             # 认证成功
    CODE_FAIL = 1           # 失败（用户名不存在 / 密码错误 / 次数过多）
    CODE_NEED_PROXY = 2     # 需要选择代拨账号（radius 模式）
    CODE_NEED_ISP = 7       # 需要选择运营商（portal 模式）
    CODE_NEED_PWD_CHANGE = 3  # 首次登录必须改密码
    CODE_NO_PACKAGE = 8     # 账号没有可用套餐

    # ==================== 网络检测 URL ====================
    # generate_204 正常响应是 204，不是 200，判断时要一起认
    TEST_URLS = [
        "http://connectivitycheck.gstatic.com/generate_204",
        "http://www.baidu.com/favicon.ico",
        "http://www.qq.com/favicon.ico",
    ]

    # ==================== HTTP 请求头 ====================
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Referer": PORTAL_BASE + "/",
    }

    # SSO 登录页是服务端渲染的传统表单，走的是浏览器那一套请求头
    SSO_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Upgrade-Insecure-Requests": "1",
    }

    # ==================== 日志配置 ====================
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"
    LOG_FILE = "campus_net.log"

    # ==================== GUI 相关 ====================
    WINDOW_TITLE = "校园网自动认证工具 v3.0"
    WINDOW_SIZE = "675x975"
    MIN_WINDOW_SIZE = (600, 825)

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

    # ==================== 心跳和重连 ====================
    # 服务端的空闲超时中位约 24 分钟，心跳压在 120 秒足够
    DEFAULT_HEARTBEAT_INTERVAL = 120
    DEFAULT_RECONNECT_INTERVAL = 30
    DEFAULT_RECONNECT_COOLDOWN = 30
    DEFAULT_HEARTBEAT_URL = "http://www.baidu.com/favicon.ico"

    # ==================== 虚拟网卡过滤 ====================
    # 这些名字的网卡不能当主链路，否则会拿到 26.x / 172.31.x 这类假 IP
    VIRTUAL_ADAPTER_KEYWORDS = (
        "radmin", "tap", "tun", "wireguard", "openvpn", "zerotier",
        "tailscale", "vmware", "virtualbox", "hyper-v", "vethernet",
        "loopback", "bluetooth", "蓝牙", "wsl", "docker",
    )
