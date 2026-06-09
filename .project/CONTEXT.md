# 上下文信息

> 最后更新：2026-06-09

### 2026-06-09: 校园网认证平台信息
- 类型：服务器/URL
- 内容：
  - CAS 域名: `cas.gzittc.com`
  - Portal IP: `10.10.21.129`
  - Portal 域名: `xykd.gzittc.edu.cn`
  - 认证入口: `http://10.10.21.129/portalScript.do`
  - SSO 入口: `http://10.10.21.129/portalCasAuth.do`
  - 登出页面: `xykd.gzittc.edu.cn/portal/usertemp_computer/gongmao-pc-2025/logout.html`
- 用途：核心认证流程
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
- 内容：校园网每 3 个月强制要求更换密码。过期时 CAS 返回修改密码页面（含"新密码"/"确认密码"表单），而非登录表单。密码要求 10-20 位，含数字和字母。
- 用途：密码过期检测逻辑
- 有效期：永久
- 敏感度：低

### 2026-06-09: 代理规则
- 类型：其他
- 内容：使用代理登录校园网会导致账号被封禁（30 分钟）。需将 `cas.gzittc.com`、`portal.gzittc.edu.cn`、`10.10.21.129` 设为直连。
- 用途：代理检测与 README Q&A
- 有效期：永久
- 敏感度：低
