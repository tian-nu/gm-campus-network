# 变更日志

## 2026-11-16 — v3.0 适配新认证系统

学校把整套认证系统换掉了，旧协议全部失效，认证层整体重写。界面、托盘、
心跳/重连框架沿用 v1.1.0。

| | 旧（v2.x） | 新（v3.0） |
|---|---|---|
| 认证网关 | 华为 AC Portal `10.10.21.129` | Panabit RAAS `xskd.gzittc.edu.cn` |
| 认证协议 | `portalScript.do` + CAS 表单 | JSON API + 统一身份认证 OAuth |
| 单点登录 | `cas.gzittc.com` | `oauth.gzittc.edu.cn` |

### 新增
- **`core/crypto.py`**：纯 Python 实现的 AES-128-ECB + ZeroPadding，
  对应服务端 `pa_aes_encode()`。零依赖，避开 pycryptodome 的安装问题，
  已用 NIST FIPS-197 向量验证。
- **统一身份认证 SSO 登录**：`/sso/authorize` → SSO 表单 POST → 回调 `code`
  → `/oauth/query_user_info` 换认证。SSO 登录页没有验证码，可全自动。
- **认证后复核**：接口返回 `code:0` 不算成功，必须 `/auth/info` 查到 `online=true`，
  避免"接口说成功其实没通"。
- **代拨账号自动选择**：返回 `code=2/7` 时按配置或优先电信挑一个账号再认证。
- **命令行模式**：`--daemon` / `--once` / `--status` / `--setup`，
  无界面常驻适合开机自启。
- **`tools/autostart.py`**：免提权开机自启，往启动文件夹放一个 VBS，
  用 `pythonw` 静默拉起 `main.py --daemon`。
- **网络白名单 / 代理检测 / WLAN 提示** 在 CLI 模式下也生效。

### 修复
- **虚拟网卡抢主链路**：机器上有 Radmin VPN 时，旧的 `uuid.getnode()` 和
  "连 114.114.114.114 看源地址"会抓到 `26.142.177.124` / `172.31.16.1`，
  拿这些 IP 去认证必然失败。改为读默认路由表按 **metric 最小** 匹配物理网卡
  （有线 25 vs Radmin 9257），并排除 `tap/tun/vEthernet/WSL` 等虚拟网卡。
- **`_run_subprocess` 解码非幂等**：同一结果对象被二次处理时 `str.decode`
  抛 `AttributeError`，导致 netsh 输出被静默丢弃、网络名返回空集。
  抽出 `_decode_output()`，已是 `str` 直接返回。

### 已知限制
- 账号有 **2 台设备上限**。认证日志证明 11 次"新设备上线"全部与旧设备下线
  同秒发生——所以被挤掉后必须重新认证，程序已能自动恢复（实测 5 秒内）。

## 2026-06-09

### 新增
- **密码过期检测**：CAS 返回修改密码页面时，提示"密码已过期（校园网每3个月需更换密码），请手动访问认证平台修改密码后重新登录"
- **重连服务密码过期处理**：密码过期时停止自动重试，登录成功后自动重置
- **WLAN 状态提示**：首页显示 WLAN 未连接/WLAN 已关闭的提示
- `WlanStatus` 枚举和 `get_wlan_status()` 方法

### 修复
- **自启动配置丢失**：`ConfigManager.__init__` 改为自动计算绝对路径，PyInstaller exe 使用 `sys.executable` 所在目录
- **设备名不同步**：`_update_status_ui()` 中新增异步更新 IP/MAC/设备名
- **代理提示文本**：去掉多余的"登录"二字

### 项目管理
- 建立 `.project/` 目录体系，迁移所有管理文件
- `AI必看.md`、`CLAUDE.md`、`RELEASE_NOTES.md` 等迁移至 `.project/`
- `.gitignore` 更新：`*.html`、`_*.py` 通配

## 2026-05-23

### v1.0 发布 — 10 项修复 + 3 项新功能

修复：启动白屏、保存卡死、首次登录慢、CMD闪现、Canvas不对齐、netsh乱码、网络名返回空、网络检测误判、托盘颜色固定、托盘模式无法重连

新增：网络白名单、登录页显示网名、登录进度反馈

## 2026-03-22

### 初始版本 v1.0.0 发布
