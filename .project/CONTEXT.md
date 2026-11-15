# 上下文信息

> 最后更新：2026-11-16（v3.0 换新认证系统）

### 2026-11-16: 校园网认证平台信息（新系统）
- 类型：服务器/URL
- 内容：
  - 门户（Panabit RAAS）: `https://xskd.gzittc.edu.cn`，只服务 HTTPS
  - 接口前缀: `https://xskd.gzittc.edu.cn/api/public`
  - 统一身份认证 SSO: `https://oauth.gzittc.edu.cn`
  - OAuth client_id: `panabit_raas`
  - 自助中心（查在线设备/踢人）: `https://xskd.gzittc.edu.cn/ucenter/`
- 关键接口：
  - `GET  /auth/info?ip=&mac=` → `{online, username, session_time, tx, rx, ucenter_token}`
  - `GET  /index/conf` → 门户配置，`account_enable` / `oauth_enable` 决定可用登录方式
  - `POST /auth/login` → 账号密码认证（username/password 走 AES）
  - `GET  /oauth/query_user_info?code=&state=&ip=&mac=&domain=` → 用 SSO 的 code 换认证
  - `POST /auth/logout` → 设备下线
- 用途：核心认证流程
- 有效期：永久（学校再换系统则失效）
- 敏感度：低

### 2026-11-16: 旧系统已全部下线
- 类型：其他
- 内容：华为 AC Portal `10.10.21.129` + `portalScript.do`、CAS `cas.gzittc.com`、
  `xykd.gzittc.edu.cn` 均已停用，v2.x 的认证流程跑不通。`Constants` 里已删掉
  相关常量（`PORTAL_IP` / `CAS_DOMAIN` / `PORTAL_DOMAIN` / `WLAN_AC_NAME` /
  `LOGOUT_PAGE` / `MAX_REDIRECTS`）。
- 用途：避免误用旧协议排查
- 有效期：永久
- 敏感度：低

### 2026-11-16: AES 加密细节
- 类型：其他
- 内容：门户用 CryptoJS `AES.encrypt(text, key, {mode: ECB, padding: ZeroPadding})`，
  key = `Panabit@1024_key`，输出**小写 hex**。`core/crypto.py` 是纯 Python 等价实现。
  注意 ZeroPadding 不是 PKCS#7——正好 16 字节时不会多补一块。
- 用途：账号密码直连认证
- 有效期：永久
- 敏感度：低

### 2026-11-16: MAC 格式要求
- 类型：其他
- 内容：服务端只认 `74-d4-dd-36-15-6c` 这种带分隔符的小写写法。
  写成 `74d4dd36156c` 会被解析成空，表现为"设备不认识"，非常难查。
  `_normalize_mac()` 强制规范化。
- 用途：认证参数构造
- 有效期：永久
- 敏感度：低

### 2026-11-16: 设备数上限与掉线规律
- 类型：其他
- 内容：账号同时在线设备上限 **2 台**。认证日志里 11 次"新设备上线"全部与旧设备
  下线同秒发生，说明是硬性挤占而非超时。被挤掉后必须重新认证，daemon 实测 5 秒内恢复。
- 用途：解释"认证成功又掉线"的根因
- 有效期：永久
- 敏感度：低

### 2026-06-09: GitHub 仓库
- 类型：其他
- 内容：`https://github.com/tian-nu/gm-campus-network.git`
- 用途：代码托管与 Release 发布
- 有效期：永久
- 敏感度：低

### 2026-06-09: 密码过期规则
- 类型：其他
- 内容：校园网每 3 个月强制要求更换密码。新系统下密码过期由统一身份认证侧
  （`oauth.gzittc.edu.cn`）拦截，返回提示文案而非登录表单。
- 用途：密码过期检测逻辑
- 有效期：永久
- 敏感度：低

### 2026-06-09: 代理规则
- 类型：其他
- 内容：使用代理登录校园网会导致账号被封禁（30 分钟）。需将
  `xskd.gzittc.edu.cn`、`oauth.gzittc.edu.cn` 设为直连（旧域名已失效）。
- 用途：代理检测与 README Q&A
- 有效期：永久
- 敏感度：低
