# 校园网自动认证工具 v3.0

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> ⚠️ **注意**：本项目仅供学习和研究使用，请遵守学校网络使用规定。
> 账号密码只保存在本地 `config.json`，不会上传到任何服务器。

## 为什么有 v3.0

2026 年 11 月，学校把整套认证系统换掉了：

| | 旧系统（v2.x 及以前） | 新系统（v3.0） |
|---|---|---|
| 认证网关 | 华为 AC Portal `10.10.21.129` | Panabit RAAS `xskd.gzittc.edu.cn` |
| 认证协议 | `portalScript.do` + CAS 表单 | JSON API + 统一身份认证 OAuth |
| 单点登录 | `cas.gzittc.com` | `oauth.gzittc.edu.cn` |
| 自助中心 | `xykd.gzittc.edu.cn` | `xskd.gzittc.edu.cn/ucenter/` |

旧域名全部下线，v2.x 的 CAS 流程已经跑不通了，所以认证层整体重写。

## 新系统的认证流程

```
┌─────────────┐   ① /sso/authorize      ┌──────────────────────┐
│  本机       │ ──────────────────────▶ │ oauth.gzittc.edu.cn  │
│  IP + MAC   │                         │ 统一身份认证 SSO     │
└─────────────┘                         └──────────┬───────────┘
       ▲                                           │ ② 表单 POST
       │                                           │   学号 / 密码
       │ ⑤ 确认 online=true                         ▼
┌──────┴────────────────────┐             ┌──────────────────────┐
│ xskd.gzittc.edu.cn        │ ◀────────── │ 302 回到 oauth.html  │
│ Panabit RAAS 门户         │  ④ code     │      ?code=xxxx      │
│  /api/public/oauth/       │             └──────────────────────┘
│      query_user_info      │
└──────┬────────────────────┘
       │ ③ RADIUS 放行
       ▼
  真正能上网
```

几个关键点（都是踩过的坑）：

- **MAC 必须带分隔符**。服务端只认 `74-d4-dd-36-15-6c`，写成 `74d4dd36156c`
  会被解析成空，表现成"设备不认识"，非常难查。
- **`account_enable = 0`**。学校把门户上的"账号密码登录"关掉了，只留统一身份认证。
  所以程序优先走 SSO，账号密码直连只作为兜底。
- **SSO 登录页没有验证码**，密码明文走 HTTPS（页面里的 `md5_plain`/`md5_salt`
  是死代码，没绑定到提交上），因此可以完全自动化。
- **认证接口返回 `code:0` 不等于真的能上网**。可能被 2 台设备上限挤掉，
  也可能运营商侧没放通。所以每次认证后都用 `/auth/info` 复核 `online`。
- **虚拟网卡会害死认证**。机器上有 Radmin VPN 时，默认路由可能指向 `26.x`，
  拿着这个 IP 去认证必然失败。v3.0 改成按路由表 metric 选网卡。

## 功能特点

- 自动识别主用网卡（有线 / 无线，自动排除 VPN 与虚拟网卡）
- 统一身份认证 SSO 全自动登录，无验证码
- 账号密码直连兜底（学校开启时才用）
- 运营商代拨账号自动选择（多账号时可指定）
- 认证后复核，避免"接口说成功其实没通"
- 心跳保持 + 断线自动重连 + 指数退避
- 睡眠唤醒重连、网卡切换 / IP 变化自动重连
- 网络名称白名单，只在宿舍网络下才动手
- WLAN 状态提示（WiFi 没开 / 没连会提醒）
- 登录前代理检测，防止账号被封
- 系统托盘常驻，最小化后台静默运行
- 图形界面 / 无界面常驻 / 单次认证三种模式

## 项目结构

```
├── main.py                     # 入口（GUI / --daemon / --once / --status / --setup）
├── requirements.txt
├── campus_net_auth/
│   ├── core/
│   │   ├── authenticator.py    # 认证器（SSO + 账号密码 + 代拨）
│   │   ├── crypto.py           # Panabit 的 AES-128-ECB 加密（纯 Python）
│   │   ├── network.py          # 心跳 / 重连 / 看门狗
│   │   └── constants.py        # 新系统常量
│   ├── config/
│   │   ├── manager.py          # 配置读写
│   │   └── defaults.py         # 默认配置
│   ├── gui/                    # Tkinter 界面 + 托盘
│   └── utils/
│       ├── logger.py
│       └── network_info.py     # 网卡识别（按路由 metric）
└── README.md
```

## 安装

```bash
pip install -r requirements.txt
```

## 使用

### 图形界面

```bash
python main.py
```

首次使用：登录页填学号和密码 → 一键登录 → 设置页配置心跳/自动重连 → 保存。

### 无界面常驻（推荐用于开机自启）

```bash
python main.py --setup      # 交互式写入账号密码（密码不回显）
python main.py --daemon     # 常驻，掉线自动重连
```

开机自启用自带的小工具，**不需要管理员权限**（它只是往启动文件夹放一个 VBS）：

```bash
python tools/autostart.py install     # 安装
python tools/autostart.py status      # 查看
python tools/autostart.py uninstall   # 卸载
```

它会生成 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GMCampusNetAuth.vbs`，
登录 Windows 时用 `pythonw` 静默启动 `main.py --daemon`，不会弹黑窗口。

> 也可以改用任务计划程序，但那个要提权，装不上的人不少。
> 如果坚持用任务计划程序：触发器选「登录时」，操作填
> `pythonw.exe <路径>\main.py --daemon`。

### 其它命令

```bash
python main.py --status     # 查当前在线状态（IP / MAC / 账号 / 时长）
python main.py --once       # 只认证一次
python main.py --interval 60 --daemon   # 自定义检测间隔
```

## 设置说明

| 设置项 | 说明 | 建议值 |
|--------|------|--------|
| 心跳间隔 | 保持连接的请求间隔 | 120 秒 |
| 检测间隔 | 断线检测间隔 | 30 秒 |
| 冷却时间 | 重连失败后等待时间 | 30 秒 |
| 超时时间 | 网络请求超时 | 10 秒 |
| 代拨账号 | 绑了多个运营商宽带时指定用哪个，留空则优先电信 | 留空 |
| 网络白名单 | 只有当前连着的网络名命中白名单才自动认证，避免在别人家网络里乱登录 | 宿舍楼栋名 |

## 常见问题

**Q：提示"没有拿到有效的内网 IP"**
没连上网，或者 DHCP 没拿到地址（`169.254.x.x`）。检查网线/WiFi，
必要时重新插拔或 `ipconfig /release && ipconfig /renew`。

**Q：提示"SSO 登录失败：账号或密码不正确"**
密码错了。注意这是**统一身份认证**的密码，不是宽带账号的密码。

**Q：认证成功但马上又掉线**
账号有 2 台设备上限。先到 `xskd.gzittc.edu.cn/ucenter/` → 在线设备，
把不用的设备踢掉再认证。

**Q：有线插上没反应**
先确认网卡没被禁用：`netsh interface show interface`，
状态是"已禁用"就执行 `netsh interface set interface "以太网" admin=enable`。

**Q：提示检测到代理**
认证时出口 IP 必须和认证 IP 一致。Clash/V2Ray 的 TUN 模式会改路由，
先关掉再认证。

## 日志

日志写入 `campus_net.log`，GUI 里也能在"日志"标签页看。

## 许可证

MIT License
