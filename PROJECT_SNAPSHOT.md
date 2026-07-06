# MCP Server Hub — 项目快照

> 新对话快速恢复上下文的完整项目状态。v2.2（2026-07-06）

## 项目定位

MCP 生态的一站式管理平台。发现 · 安装 · 管理 · 发布 · 社区。

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
认证 GitHub OAuth + 纯 HMAC JWT（FastAPI Depends 注入）

## 目录结构

```
src/mcp_hub/
├── api/       18 路由模块（含 routes_admin + dependencies 认证依赖）
├── cli/       24 命令模块 → 46 命令
├── core/      14 模块
├── db/        8 模块
├── web/       React SPA（23 页面：14 客户端 + 9 管理后台）
```

## 数据库 (13 表)

servers / reviews / users / favorites / health_logs / events / subscriptions / install_history / user_servers / usage_stats / notifications / presets / alembic_version

## 核心功能（客户端已完成）

| 功能 | 状态 |
|------|------|
| 🏪 市场搜索/浏览/对比/推荐 | ✅ |
| ⭐ 收藏/评价 | ✅ |
| 📤 配置上传/匹配/Agent选择 | ✅ |
| 💾 配置草稿 + 方案市场 | ✅ |
| 📦 我的Server（批量/重启/调用数据/更新提醒） | ✅ |
| 📊 监控大屏 | ✅ |
| 👤 个人中心（资料/统计/趋势图） | ✅ |
| 🔔 通知中心 + 通知隔离（user_id 维度） | ✅ |
| 🌙 Dark Mode / 🔍 全局搜索 / 🧭 面包屑 / 📱 移动端 | ✅ |
| 🔗 MCP 网关 + 安全评分 + Token分析 | ✅ |
| 🛡️ 认证系统（GitHub OAuth + JWT + Depends 注入） | ✅ |

## 管理后台（已完成）

| 模块 | 状态 |
|------|------|
| 🛡️ AdminLayout（独立侧边栏 + 角色守卫） | ✅ |
| 📊 AdminOverview（6卡 + 趋势图 + Top10） | ✅ |
| 👥 AdminUsers + AdminUserDetail（角色修改） | ✅ |
| 📦 AdminServers + AdminServerDetail（下架/安全调整） | ✅ |
| 📈 AdminAnalytics（趋势 + 排行 + 日期选择） | ✅ |
| 🛡️ AdminReviews（评价审核 + 删除） | ✅ |
| 📋 AdminAuditLog（操作审计） | ✅ |
| 📥 CSV 导出（用户/Server） | ✅ |
| 🔒 权限双校验（前端角色守卫 + 后端 Depends(get_admin_user)） | ✅ |
| 🔌 入口隐藏（客户端侧边栏不展示，仅 URL 直访 /admin） | ✅ |

## 安全加固（2026-07-06 完成）

| 项目 | 说明 |
|------|------|
| 🔑 认证系统 | 从伪 Header 切换到 JWT Bearer Token + FastAPI Depends(get_current_user) |
| 🛡️ CSRF 防护 | OAuth state 参数验证 |
| 🔒 环境变量白名单 | 子进程仅传递白名单环境变量（防密钥泄露） |
| 🚫 路径遍历 | safe_log_path() 白名单过滤 |
| 💉 Shell 注入 | os.system() → subprocess.run() |
| 🐳 Docker | 非 root 用户 + 健康检查 + 资源限制 |
| 🔍 安全评分 | 维度最低分机制（致命问题不可被正面抵消） |
| 📜 npm 检测 | 精确正则匹配 npm install -g（消除误报） |
| 🔑 Git 安全 | 敏感凭据已从历史记录清除并更换 |

## 质量加固

| 项目 | 说明 |
|------|------|
| 🗃️ 数据一致性 | rate/favorite 双 commit 合并 + 级联删除 + falsy 值修复 |
| 📋 错误处理 | 17 处 `except:pass` → `logger.warning/debug` |
| 🔗 进程管理 | shlex 参数解析 + stderr drain + keepalive 清理 |
| ⚡ 数据库 | 10 个外键索引 + get_reviews 分页修复 |
| 🖥️ 前端 | ErrorBoundary + 搜索 debounce + href 协议验证 |
| 🔧 daemon | stop/enable/disable 真正实现功能 |
| 📝 日志 | configure_logging() 现在被正确调用 |

## 待实现

| 功能 | 状态 |
|------|------|
| 团队空间 / VS Code 插件 | ❌ 远期 |

## 最近更新（2026-07-06）

### systematic-bug-hunting 全量审计修复
- 15 个并行 agent 审查 120+ 文件，发现 16 Critical + 68 High + 150+ Medium
- 按 10 组（G1-G10）并行修复，分 3 波执行
- 新建 `api/dependencies.py`（FastAPI 认证依赖注入）
- 新增 `ErrorBoundary.tsx`（React 错误边界）
- 286 个测试全量通过，TypeScript 0 错误
- Git 历史已通过 `git filter-repo` 清除敏感字符串

### 认证系统重构
- 移除所有 `Header("anonymous")` / `Header("api-user")` 伪认证
- 实现 `Depends(get_current_user)` / `Depends(get_admin_user)` / `Depends(get_optional_user)`
- `verify_token()` 不再自动创建用户（修复账户伪造漏洞）
- 前端 `getAuthHeaders()` 自动附加 `Authorization: Bearer` header
- `/auth/me` 从 DB 查询完整用户信息（avatar_url 等）
