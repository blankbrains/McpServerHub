# MCP Server Hub — 项目快照

> 新对话快速恢复上下文的完整项目状态。

## 项目定位

MCP 生态的一站式管理平台。发现 · 安装 · 管理 · 发布 · 社区。
983+ Server · 46 CLI · 16 API 模块 · 14 Core · 12 前端页面。

## 部署信息

- **服务器**: `gpu-server` (172.19.138.78), 用户 `djl`
- **代码路径**: 服务器 `/home/djl/code/McpServerHub` / 本地 `e:\硕士方向\...\McpServerHub`
- **服务地址**: `http://172.19.138.78:3987/` → Cloudflare Tunnel
- **运行时**: uvicorn + FastAPI, workers=1, conda env `McpServerHub`
- **数据库**: PostgreSQL 18.4, 库 `mcp_hub`
- **GitHub**: `https://github.com/blankbrains/McpServerHub`
- **PyPI**: `pip install mcp-hub-cli`

## 技术栈

后端 Python 3.10+ / FastAPI / SQLAlchemy 2.0 async
前端 React 19 + Tailwind CSS + Vite
数据库 PostgreSQL (生产) / SQLite (quickstart)

## 目录结构

```
src/mcp_hub/
├── api/       16 路由模块 (market/manage/community/health/auth/realtime/config/search/export/security/token/builder/monitor/publish + app.py)
├── cli/       24 命令模块 → 46 命令
├── core/      14 模块 (registry/installer/process_manager/health_check/event_bus/mcp_gateway/auth/security_scanner/token_analyzer/server_builder/monitor/config_manager/version_manager/local_discovery/dependency_analyzer)
├── db/        8 模块 (database/models/repositories/seed/auto_categorize/enrich_servers/migrations)
├── web/       React SPA (12 页面: Dashboard/Market/ServerDetail/MyServers/ConfigPage/Builder/MyConfig/Login/Publish/MonitorDashboard/LocalDiscovery)
```

## 核心功能

| 功能 | 状态 |
|------|------|
| 🛡️ 安全评分 | 四维引擎(40+25+20+15), blocked<50 阻止 |
| 📊 Token 分析 | tiktoken 精确计数 + 优化建议 |
| 🛠️ Server Builder | 8 模板, CLI + Web 下载 ZIP |
| 📈 质量监控 | 可靠性(24h×40%+7d×30%+响应×20%+1h×10%) |
| 🔘 启用/禁用 | 直接写 DB, 即时生效 |
| 🔍 本地发现 | 自动扫描 8 种 Agent 的 MCP 配置 |
| 📦 配置管理 | 备份/恢复/快照/差异对比/上传预览确认 |
| 🗂 分组管理 | user_servers.group_name + 批量启用/禁用 |
| 🔎 日志搜索 | 跨 Server 关键词搜索含上下文 |
| ✅ 安装预检 | Python版本/工具/磁盘自动检查 |
| 🔗 MCP 网关 | 完整打通 — Agent 调用自动记录到 usage_stats |

## 数据库 (10 表)

servers / reviews / users / favorites / health_logs / events / subscriptions / install_history / user_servers / usage_stats

user_servers 关键列: user_id, server_id, matched, enabled, agent, group_name

## 关键 API (本轮新增/修复)

| 端点 | 方法 | 说明 |
|------|------|------|
| /config/user-servers/toggle | POST | 单 Server 启用/禁用 |
| /config/user-servers/{id} | DELETE | 删除单个追踪 |
| /local/discover | GET | 本地 Agent 发现 |
| /local/compare | GET | 跨 Agent 对比 |
| /local/conflicts | GET | 配置冲突检测 |
| /config/diff | GET | 本地 vs Hub 差异 |
| /config/backup | POST | 配置备份 |
| /config/backups | GET | 备份列表 |
| /config/restore/{file} | POST | 恢复备份 |
| /servers/pre-check | POST | 安装预检 |
| /servers/dependency-analyze | POST | 依赖分析 |
| /config/groups | GET/POST | 分组管理 |
| /logs/search | GET | 跨 Server 日志搜索 |

## 关键设计决策

1. 上传 mcp.json → 自动匹配市场 → 状态设为 stopped（视为已安装，不再"追踪中"）
2. 市场添加/删除始终写 DB（不依赖 localStorage）
3. enable/disable 直接 toggle 一行（不加载全部再覆盖全部）
4. 一键安装改为添加配置（不在服务器上执行 npm/pip）
5. x-user-id 必须从 Header 读取（`Header("anonymous")`），不是普通默认值
6. 所有时间戳统一用 `time.time()`（Unix 时间），不用 `asyncio.get_event_loop().time()`
7. MCP 网关用后台 reader 按 req_id 分发响应，避免 stdout 竞态

## 已知问题

- Cloudflare Tunnel 临时域名，重启会变
- gpu-server 用 `python3` 非 `python`
- Token 数据来自工具定义估算，真实调用数据需通过 Gateway 中转
- 监控仪表盘运行中=0 因为 Hub 上未启动进程（需通过 Gateway 中转才有数据）
- 前端需 Ctrl+Shift+R 强制刷新（浏览器缓存问题）

---

## 会话记录 — 2026-07-01 全面修复与功能增强

### Bug 修复（30+ 项）
- P0: 健康检查自动重启链打通、npx 真实安装、ConfigManager.set_config 实现
- P1: EventBus DB 持久化、SPA 挂载去重、本地配置发现补全 8 Agent、Trae 支持
- 安全: JWT 迁移 Authorization 头、SSE 认证、全局异常处理器、移除速率限制
- 前端: 10+ handler 加 try/catch、竞态保护、错误退避
- DB: user_servers GET 补全 enabled/agent/group_name 字段、save 补全 group_name
- 数据链路: market +/- 始终写 DB、save_user_servers 用 Header 读取用户

### 新增功能（8 项）
1. 本地 Agent 发现 — 8 种 Agent 自动扫描 + 跨 Agent 对比 + 冲突检测
2. 配置备份/恢复/快照
3. 配置差异对比（本地 vs Hub）
4. 安装前预检（Python 版本/工具/磁盘）
5. MCP Server 依赖分析（运行时 + 环境变量 + 系统工具）
6. Server 分组管理（group_name 列 + CRUD + 批量启用/禁用）
7. 跨 Server 日志搜索
8. 离线模式 localStorage 缓存

### MCP 网关完整打通
- ManagedMCP 后台 reader 线程，按 req_id 分发响应
- start_all_managed 过滤已禁用 Server
- tools/call 计时 + 自动记录 usage_stats
- CLI serve 命令完善提示

### 前端重构
- ConfigPage: 3 步流程（上传预览确认/取消 → 选择 Agent → 复制网关配置）
- MyServers: Tab 切换（已安装/追踪中/收藏）+ 序号 + 删除确认
- Dashboard: 错误状态 + 日志搜索框 + 追踪 Server 虚线卡片
- ServerDetail: 收藏状态切换 + 已追踪显示"安装到本地" + securityLabels 补 blocked
- Login: 单头像条件渲染
- 全局: aria-current/skip-to-link/role=log/radiogroup 等 a11y 修复

### 关键 Bug 修复 (Code Review 发现)
- Login.tsx: useState 在 if 块内 → React Hooks 违规 → 页面崩溃
- Market.tsx: localStorage 覆盖丢失 command/enabled 字段
- routes_manage.py: CfgErr 别名未定义 → NameError
- LocalDiscovery: Promise.all 单点失败影响全部
- 运行时长 20521d: asyncio event loop time vs Unix time 不匹配

### 测试
286 全部通过。服务器正常运行。
