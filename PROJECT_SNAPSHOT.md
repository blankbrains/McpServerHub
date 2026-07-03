# MCP Server Hub — 项目快照

> 新对话快速恢复上下文的完整项目状态。v2.0（2026-07-03）

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

## 目录结构

```
src/mcp_hub/
├── api/       17 路由模块
├── cli/       24 命令模块 → 46 命令
├── core/      14 模块
├── db/        8 模块
├── web/       React SPA (14 页面)
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
| 🔔 通知中心 | ✅ |
| 🌙 Dark Mode / 🔍 全局搜索 / 🧭 面包屑 / 📱 移动端 | ✅ |
| 🔗 MCP 网关 + 安全评分 + Token分析 | ✅ |

## 待实现

| 功能 | 状态 |
|------|------|
| 🛡️ 管理后台（routes_admin.py + 8 admin 页面） | ❌ 已有项目文档和开发文档 |
| 团队空间 / VS Code 插件 | ❌ 远期 |

## 最近更新（2026-07-02 ~ 07-03）

- **体验闭环**：通知中心 + 版本更新提醒 + MCP Playground + 运行时详情
- **增长引擎**：智能推荐 + 配置方案市场 + 使用统计可视化
- **体验打磨**：Dark Mode + 全局搜索 + 面包屑 + 移动端 + 配置草稿
- **Bug 修复**：累计 100+ bug（经 5 轮 Skill 自查），含 N+1→批量、空catch→错误提示、乐观更新→回滚、覆盖保存→精确DELETE
