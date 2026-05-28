# 校园网自动认证工具 v1.0

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

模块化重构版本，代码结构清晰，易于维护和扩展。

> ⚠️ **注意**：本项目仅供学习和研究使用，请遵守学校网络使用规定。

## 功能特点

- ✅ 自动检测网络状态
- ✅ 自动认证校园网 CAS 系统
- ✅ 心跳保持防止掉线
- ✅ 断线自动重连
- ✅ 自动获取 IP 和 MAC 地址
- ✅ 现代化图形界面
- ✅ 系统托盘支持
- ✅ 配置持久化

## 项目结构

```
├── main.py                     # 应用入口
├── requirements.txt            # 依赖列表
├── campus_net_auth/            # 主模块
│   ├── core/                   # 核心功能
│   │   ├── authenticator.py    # CAS 认证器
│   │   ├── network.py          # 心跳/重连服务
│   │   └── constants.py        # 常量定义
│   ├── config/                 # 配置管理
│   │   ├── manager.py          # 配置管理器
│   │   └── defaults.py         # 默认配置
│   ├── gui/                    # 图形界面
│   │   ├── app.py              # 主应用
│   │   ├── widgets.py          # 自定义控件
│   │   ├── tray.py             # 系统托盘
│   │   └── tabs/               # 标签页
│   │       ├── login.py        # 登录页
│   │       ├── settings.py     # 设置页
│   │       └── logs.py         # 日志页
│   └── utils/                  # 工具模块
│       ├── logger.py           # 日志配置
│       └── network_info.py     # 网络信息
└── tests/                      # 测试模块
    ├── test_authenticator.py   # 认证器测试
    ├── test_config.py          # 配置管理测试
    ├── test_network.py         # 网络功能测试
    └── ...                     # 其他测试文件
```

## 安装

1. 确保已安装 Python 3.8 或更高版本

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

运行程序：
```bash
python main.py
```

### 首次使用

1. 在"登录"标签页输入学号和密码
2. 点击"一键登录"开始认证
3. 在"设置"标签页配置心跳间隔、自动登录等选项
4. 点击"保存设置"

### 设置说明

| 设置项 | 说明 | 建议值 |
|--------|------|--------|
| 心跳间隔 | 保持连接的请求间隔 | 120-300 秒 |
| 检测间隔 | 断线检测间隔 | 30 秒 |
| 冷却时间 | 重连失败后等待时间 | 30 秒 |
| 超时时间 | 网络请求超时 | 10 秒 |

## 配置文件

配置保存在 `config.json`，包含：
- 账号密码（可选记住）
- 启动设置
- 网络设置
- 心跳/重连设置
- 高级设置

## 日志

日志保存在 `campus_net.log`，可在"日志"标签页查看。

## 许可证

MIT License
