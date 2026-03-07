# Design Document: Campus Network Authentication Tool Refactor

## Overview

本设计文档描述校园网自动认证工具的重构方案。重构目标是将原有的单文件应用（1600+ 行）拆分为模块化架构，提升代码可维护性、可测试性和可扩展性，同时保持所有现有功能完全可用。

新架构采用分层设计：
- **Core Layer**: 认证逻辑、网络检测、心跳/重连服务
- **Config Layer**: 配置管理、持久化
- **GUI Layer**: 用户界面（重新设计）
- **Utils Layer**: 日志、网络工具函数

## Architecture

```
campus_net_auth/
├── __init__.py
├── main.py                 # 应用入口
├── core/
│   ├── __init__.py
│   ├── authenticator.py    # CAS 认证核心逻辑
│   ├── network.py          # 网络检测、心跳、重连
│   └── constants.py        # 常量定义
├── config/
│   ├── __init__.py
│   ├── manager.py          # 配置管理器
│   └── defaults.py         # 默认配置
├── gui/
│   ├── __init__.py
│   ├── app.py              # 主窗口
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── login.py        # 登录标签页
│   │   ├── settings.py     # 设置标签页
│   │   └── logs.py         # 日志标签页
│   ├── widgets.py          # 自定义控件
│   └── tray.py             # 系统托盘
├── utils/
│   ├── __init__.py
│   ├── logger.py           # 日志配置
│   └── network_info.py     # IP/MAC 获取
└── tests/
    ├── __init__.py
    ├── test_authenticator.py
    ├── test_config.py
    └── test_network.py

original/                   # 原项目文件备份
├── main.py
├── config.json
├── requirements.txt
└── ...
```

## Components and Interfaces

### 1. Core - Authenticator

```python
class CampusNetAuthenticator:
    """校园网认证器"""
    
    def __init__(self, config: dict):
        """初始化认证器"""
        
    def login(self, username: str, password: str) -> tuple[bool, str]:
        """执行登录认证
        Returns: (success, message)
        """
        
    def detect_network_status(self) -> bool:
        """检测网络连通性"""
        
    def start_heartbeat(self) -> None:
        """启动心跳保持"""
        
    def stop_heartbeat(self) -> None:
        """停止心跳保持"""
        
    def start_reconnect(self) -> None:
        """启动断线重连"""
        
    def stop_reconnect(self) -> None:
        """停止断线重连"""
        
    def stop_all(self) -> None:
        """停止所有后台服务"""
```

### 2. Config - ConfigManager

```python
class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.json"):
        """初始化配置管理器"""
        
    def load(self) -> dict:
        """加载配置，自动合并默认值"""
        
    def save(self, config: dict) -> bool:
        """保存配置到文件"""
        
    def reset(self) -> dict:
        """重置为默认配置"""
        
    def clean_old_logs(self, retention_days: int) -> None:
        """清理过期日志"""
```

### 3. Utils - NetworkInfo

```python
class NetworkInfo:
    """网络信息工具"""
    
    @staticmethod
    def get_ip_address() -> str:
        """获取本机 IP 地址"""
        
    @staticmethod
    def get_mac_address(config: dict) -> str:
        """获取 MAC 地址"""
        
    @classmethod
    def get_network_info(cls, config: dict) -> dict:
        """获取完整网络信息"""
```

### 4. GUI - Main Application

```python
class CampusNetApp:
    """主应用程序"""
    
    def __init__(self, root: Tk):
        """初始化应用"""
        
    def run(self) -> None:
        """运行应用"""
```

## Data Models

### Configuration Schema

```python
@dataclass
class AppConfig:
    # 账号信息
    username: str = ""
    password: str = ""
    
    # 启动设置
    startup: bool = False
    auto_login: bool = False
    remember_password: bool = True
    
    # 通知设置
    login_success_notify: bool = True
    login_fail_notify: bool = True
    
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
    mac_address: str = ""
```

### Authentication Result

```python
@dataclass
class AuthResult:
    success: bool
    message: str
    timestamp: datetime
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Network detection consistency
*For any* network state, if the Authenticator detects the network as connected, then calling login should return early with a "network already connected" message without making authentication requests.
**Validates: Requirements 1.2**

### Property 2: Authentication error messages
*For any* authentication attempt with invalid credentials, the Authenticator should return a tuple (False, message) where message contains a non-empty error description.
**Validates: Requirements 1.3**

### Property 3: Heartbeat interval compliance
*For any* heartbeat configuration with a positive interval, the heartbeat thread should make requests at approximately the configured interval (within reasonable tolerance).
**Validates: Requirements 2.1**

### Property 4: Reconnect cooldown enforcement
*For any* failed reconnect attempt, the next reconnect attempt should not occur until at least the configured cooldown period has elapsed.
**Validates: Requirements 2.4**

### Property 5: Thread graceful shutdown
*For any* running heartbeat or reconnect thread, calling the corresponding stop method should terminate the thread within a reasonable timeout period.
**Validates: Requirements 2.5**

### Property 6: Configuration round-trip
*For any* valid configuration dictionary, saving it to JSON and then loading it back should produce an equivalent configuration (all keys and values preserved).
**Validates: Requirements 3.4, 3.5**

### Property 7: Configuration default merge
*For any* partial configuration (missing some keys), loading it should produce a complete configuration with missing keys filled from defaults.
**Validates: Requirements 3.2**

### Property 8: Log entry format
*For any* logged event, the log entry should contain a timestamp, severity level, and message content.
**Validates: Requirements 6.1**

## Error Handling

### Network Errors
- **Timeout**: 返回 `(False, "连接超时，请检查网络")`
- **Connection Error**: 返回 `(False, "连接错误，请检查网络")`
- **SSL Error**: 返回 `(False, "SSL 证书错误")`

### Authentication Errors
- **Invalid Credentials**: 返回 `(False, "用户名或密码错误")`
- **Missing Token**: 返回 `(False, "无法找到登录令牌")`
- **Unknown Page**: 返回 `(False, "未知的页面状态: {url}")`

### Configuration Errors
- **File Not Found**: 使用默认配置
- **JSON Parse Error**: 使用默认配置并记录警告
- **Permission Error**: 记录错误，返回 False

## Testing Strategy

### Property-Based Testing

使用 **Hypothesis** 库进行属性测试，验证系统的正确性属性。

```python
from hypothesis import given, strategies as st

@given(st.dictionaries(st.text(), st.text() | st.integers() | st.booleans()))
def test_config_round_trip(config):
    """Property 6: Configuration round-trip"""
    manager = ConfigManager("test_config.json")
    manager.save(config)
    loaded = manager.load()
    # Verify all original keys are preserved
    for key, value in config.items():
        assert key in loaded
        assert loaded[key] == value
```

### Unit Testing

使用 **pytest** 进行单元测试：

- 测试 Authenticator 的各个方法
- 测试 ConfigManager 的加载/保存逻辑
- 测试 NetworkInfo 的 IP/MAC 获取
- 测试 GUI 组件的状态变化

### Test Configuration

- Property-based tests: 最少 100 次迭代
- 每个正确性属性对应一个独立的属性测试
- 测试文件位于 `tests/` 目录
