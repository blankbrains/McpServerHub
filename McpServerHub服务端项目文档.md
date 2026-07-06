# McpServerHub 服务端（管理后台）项目文档

> 版本：v2.0 | 2026-07-03 | 需求与设计文档

---

## 一、项目定位

McpServerHub 目前没有面向平台运营者的管理后台。本文档定义服务端管理后台需要补全的所有功能。

核心目标：**让管理员能查看、分析、管理平台上的一切——用户、Server、调用数据、Token 消耗。**

---

## 二、可用的数据基础

客户端已经产生了大量数据，管理后台直接复用：

| 数据表 | 关键字段 | 管理后台可用来做什么 |
|--------|---------|-------------------|
| `users` | id, display_name, avatar_url, role, created_at, last_login | 用户列表、角色管理、注册趋势 |
| `servers` | id, name, categories, rating, download_count, security_level | Server 列表、分类统计、安全概览 |
| `user_servers` | user_id, server_id, enabled, agent, group_name | 用户-Server 关联、安装统计 |
| `usage_stats` | server_id, **user_id**, tool_name, duration_ms, **token_count**, created_at | 调用统计、Token 消耗、用户活跃度、每日趋势 |
| `notifications` | user_id, type, title, is_read, created_at | 系统公告推送、操作通知 |
| `reviews` | server_id, user_id, rating, content, parent_id | 评价审核 |
| `install_history` | server_id, **user_id**, action, created_at | 安装历史追踪 |

> `usage_stats.user_id` 和 `token_count` 已由 MCP 网关在每次 tool call 时自动写入，`install_history.user_id` 已在安装时记录。管理后台可直接做用户维度和时间维度的聚合分析。

---

## 三、功能需求

### 3.1 管理员鉴权

- 基于 `UserModel.role === "admin"` 判断（该字段已存在，未被使用）
- 所有 `/api/v1/admin/*` 端点验证调用者身份，非 admin 返回 403
- 管理后台前端入口仅 `role === "admin"` 时可见
- `/admin/*` 路由守卫：非 admin 重定向到首页

### 3.2 平台概览仪表盘

一个页面看完平台核心指标。

**统计卡片（6 个）**：
- 总用户数、总 Server 数、总安装次数、总调用次数、总 Token 消耗、7 日活跃用户数

**每日调用趋势**：最近 30 天 `GROUP BY DATE(created_at)`，调用次数 + Token 总量折线图

**热门排行**：
- Top 10 Server（按安装用户数 + 7 日调用数）
- Top 10 用户（按 7 日调用次数）

### 3.3 用户管理

**用户列表**：
- 表格：头像、用户名、角色、安装 Server 数、7 日调用、7 日 Token、最后活跃时间、注册时间
- 搜索（用户名）、排序、分页
- 点击行 → 用户详情

**用户详情**：
- 基本信息卡片（头像、GitHub ID、邮箱、角色、注册时间、最后登录）
- 安装的 Server 列表（每个含 7 日调用数、Token、启用状态）
- 每日调用 + Token 趋势图（最近 30 天）
- 最常用工具 Top 5
- **管理员可修改用户角色**（user ↔ admin）

### 3.4 Server 分析

**Server 管理列表**：
- 表格：名称、分类、安装用户数、7 日调用、7 日 Token、评分、安全等级
- 搜索 + 分类筛选 + 排序 + 分页
- 点击行 → Server 详情

**Server 详情**：
- 基本信息 + 安全评分 + Token 分析摘要
- 安装此 Server 的用户列表
- 每日调用 + Token 趋势图（最近 30 天）
- 最常调用的工具排行

### 3.5 使用分析

独立的平台数据分析页面：

- 日期范围选择器（7d / 30d / 自定义）
- 每日调用 + Token 双轴趋势图
- 按 Server 分类的调用分布柱状图
- Top 10 工具排行（调用次数 / Token）
- Top 10 用户排行（调用次数 / Token）

### 3.6 内容审核

- **评价管理**：所有评价列表，管理员可直接删除不当评价
- **Server 下架**：管理员可下架违规 Server（状态标记为 blocked）
- **发布审核**（可选）：用户发布的 Server 需审核后才能在市场展示

### 3.7 操作审计

- 记录管理员操作：谁、什么时间、做了什么（修改角色/删除评价/下架 Server）
- 审计日志页面：按时间/操作人/操作类型筛选
- 实现方式：Admin API 中每个写操作写入 `notifications` 表（type=audit），或复用 `EventModel` 表

### 3.8 数据导出

- 用户列表导出 CSV
- Server 分析数据导出 CSV
- 使用统计数据导出 CSV（支持日期范围）

---

## 四、技术方案

### 4.1 后端

新建文件：`src/mcp_hub/api/routes_admin.py`

- 前缀 `/api/v1/admin`，所有端点先过 `_require_admin(x_user_id)` 鉴权
- 约 14 个端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/overview` | GET | 平台概览聚合 |
| `/admin/users` | GET | 用户列表（分页+搜索） |
| `/admin/users/{id}` | GET | 用户详情 |
| `/admin/users/{id}/servers` | GET | 用户的 Server 列表 |
| `/admin/users/{id}/usage/daily` | GET | 用户每日趋势 |
| `/admin/users/{id}/role` | PATCH | 修改角色 |
| `/admin/servers` | GET | Server 列表（含统计） |
| `/admin/servers/{id}` | GET | Server 详情（含统计） |
| `/admin/servers/{id}/users` | GET | Server 的安装用户 |
| `/admin/servers/{id}/usage/daily` | GET | Server 每日趋势 |
| `/admin/analytics/daily` | GET | 平台每日趋势 |
| `/admin/analytics/top-servers` | GET | Top Server |
| `/admin/analytics/top-users` | GET | Top 用户 |
| `/admin/reviews` | GET + DELETE | 评价列表 + 删除 |

- 数据来源：四表 JOIN/GROUP BY（`usage_stats` + `user_servers` + `servers` + `users`）
- 趋势查询：`GROUP BY DATE(usage_stats.created_at)` 按天聚合
- 分页参数：`page`（默认 1）、`page_size`（默认 20，最大 100）

### 4.2 前端

新建目录：`src/mcp_hub/web/src/pages/admin/`

| 文件 | 说明 |
|------|------|
| `AdminLayout.tsx` | 管理后台独立侧边栏布局 |
| `AdminOverview.tsx` | 概览仪表盘（6 卡片 + 趋势图 + Top 10） |
| `AdminUsers.tsx` | 用户列表（表格 + 搜索 + 分页） |
| `AdminUserDetail.tsx` | 用户详情（资料 + Server 列表 + 趋势 + 角色修改） |
| `AdminServers.tsx` | Server 管理列表（表格 + 筛选 + 分页） |
| `AdminServerDetail.tsx` | Server 详情（统计 + 用户列表 + 趋势） |
| `AdminAnalytics.tsx` | 使用趋势分析（日期选择 + 趋势图 + 排行） |
| `AdminReviews.tsx` | 评价审核（列表 + 删除） |
| `AdminAuditLog.tsx` | 操作审计日志 |

- 路由：`/admin` 为根，嵌套子路由（`/admin/users`、`/admin/servers` 等）
- AdminLayout 侧边栏导航：概览 / 用户 / Server / 分析 / 审核 / 审计
- 图表方案：CSS 柱状图 + SVG 折线图（不引入重库）
- 侧边栏入口：`role === "admin"` 时显示 "🛡️ 管理后台"

### 4.3 路由注册

App.tsx 新增：
```
/admin → AdminLayout
  /admin/ → AdminOverview
  /admin/users → AdminUsers
  /admin/users/:userId → AdminUserDetail
  /admin/servers → AdminServers
  /admin/servers/:serverId → AdminServerDetail
  /admin/analytics → AdminAnalytics
  /admin/reviews → AdminReviews
  /admin/audit → AdminAuditLog
```

Layout.tsx 侧边栏：在通知铃铛下方增加管理后台入口链接。

---

## 五、实施计划

| 阶段 | 内容 | 产出 |
|------|------|------|
| Phase 1 | Admin API 骨架 + 鉴权 | `routes_admin.py`（`_require_admin` + 前 3 个端点） |
| Phase 2 | 概览端点 + AdminOverview 页面 | 6 卡 + 趋势图 + Top 10 |
| Phase 3 | 用户管理端点 + AdminUsers + AdminUserDetail | 列表/详情/角色修改 |
| Phase 4 | Server 分析端点 + AdminServers + AdminServerDetail | 列表/详情/趋势 |
| Phase 5 | 分析端点 + AdminAnalytics | 趋势图 + 排行 |
| Phase 6 | 审核 + 审计 + 数据导出 | AdminReviews + AdminAuditLog |
| Phase 7 | 导航集成 + 路由守卫 + 部署 | AdminLayout + App.tsx + Layout.tsx |
| Phase 8 | Skill 自查 + 修复 + 上线 | 全面检查 |

---

## 六、设计要点

1. **复用不新建**：`usage_stats.user_id` 已有、`UserModel.role` 已有——管理后台只读/改已有数据，不新建表
2. **权限双校验**：前端 `role === "admin"` + 后端 `_require_admin`，两层防护
3. **路由隔离**：`/admin/*` 与客户端 `/market`、`/profile` 等完全独立
4. **渐进构建**：Phase 1 先出 API 骨架，然后逐页面实现，每个 Phase 可独立验证
5. **轻量图表**：CSS 柱状图 + SVG 折线图，不引入 Chart.js/ECharts
6. **审计即通知**：管理员操作直接写入 `notifications` 表（type=audit），复用已有基础设施
