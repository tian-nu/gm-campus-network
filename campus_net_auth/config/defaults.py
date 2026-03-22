"""
默认配置定义
所有配置项的默认值和配置模式
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class AppConfig:
    """应用配置数据类"""

    # 账号信息
    username: str = ""
    password: str = ""

    # 启动设置
    startup: bool = False
    auto_login: bool = False
    remember_password: bool = True
    minimize_startup: bool = False

    # 通知设置
    login_success_notify: bool = True
    login_fail_notify: bool = True
    silent_mode: bool = True  # 静默模式（仅异常通知）
    check_proxy_before_login: bool = True  # 登录前检测代理
    strict_proxy_check: bool = True  # 严格代理检测（检测到代理时阻止登录）

    # 网络设置
    timeout: int = 10
    max_retries: int = 3

    # 心跳设置
    enable_heartbeat: bool = True
    heartbeat_interval: int = 120
    heartbeat_url: str = "http://www.baidu.com/favicon.ico"

    # 重连设置
    enable_reconnect: bool = True
    reconnect_interval: int = 30
    reconnect_cooldown: int = 30

    # 高级设置
    debug_mode: bool = False
    verbose_log: bool = True
    auto_clean_log: bool = True
    log_retention_days: int = 7

    # 网络信息
    mac_address: str = ""
    
    # 封禁处理设置
    enable_auto_retry_after_ban: bool = True
    default_ban_duration: int = 30  # 默认封禁时长（分钟）
    
    # 指数退避设置
    enable_exponential_backoff: bool = True  # 启用指数退避
    min_backoff_seconds: int = 1  # 最小退避时间（秒）
    max_backoff_seconds: int = 30  # 最大退避时间（秒）

    # 网络监听器设置
    enable_network_monitor: bool = True  # 启用网络变化监听
    network_monitor_interval: float = 2.0  # 监听检测间隔（秒）

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典创建配置"""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


# 默认配置字典（用于向后兼容）
DEFAULT_CONFIG = {
    # 账号信息
    "username": "",
    "password": "",

    # 启动设置
    "startup": False,
    "auto_login": False,
    "remember_password": True,
    "minimize_startup": False,

    # 通知设置
    "login_success_notify": True,
    "login_fail_notify": True,
    "silent_mode": True,  # 静默模式（仅异常通知）
    "check_proxy_before_login": True,  # 登录前检测代理
    "strict_proxy_check": True,  # 严格代理检测（检测到代理时阻止登录）

    # 网络设置
    "timeout": 10,
    "max_retries": 3,

    # 心跳设置
    "enable_heartbeat": True,
    "heartbeat_interval": 120,
    "heartbeat_url": "http://www.baidu.com/favicon.ico",

    # 重连设置
    "enable_reconnect": True,
    "reconnect_interval": 30,
    "reconnect_cooldown": 30,

    # 高级设置
    "debug_mode": False,
    "verbose_log": True,
    "auto_clean_log": True,
    "log_retention_days": 7,

    # 网络信息
    "mac_address": "",
    
    # 封禁处理设置
    "enable_auto_retry_after_ban": True,
    "default_ban_duration": 30,  # 默认封禁时长（分钟）
    
    # 指数退避设置
    "enable_exponential_backoff": True,
    "min_backoff_seconds": 1,
    "max_backoff_seconds": 30,

    # 网络监听器设置
    "enable_network_monitor": True,  # 启用网络变化监听
    "network_monitor_interval": 2.0  # 监听检测间隔（秒）
}
