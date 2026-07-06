# MCP Server Hub 服务端（管理后台）开发文档

> 管理后台开发指南 —— 基于现有客户端基础设施扩展

| 项目 | 内容 |
|------|------|
| **版本** | v1.0（开发中） |
| **依赖** | Python 3.10+ / FastAPI / SQLAlchemy 2.0 async / React 19 + Tailwind |
| **数据库** | PostgreSQL 18.4（生产）/ SQLite（开发）— 四表 JOIN 聚合 |
| **鉴权** | `UserModel.role === "admin"`（字段已存在，加校验逻辑） |
| **测试** | 新增 admin API 测试，目标覆盖率 ≥ 90% |

---

## 一、新增文件结构

```
src/mcp_hub/
├── api/
│   └── routes_admin.py          # 新增 — 管理后台 API（14 端点 + 鉴权）
│
└── web/src/
    ├── App.tsx                   # 修改 — 注册 /admin/* 路由
    ├── components/
    │   └── Layout.tsx            # 修改 — 侧边栏加管理后台入口
    └── pages/
        └── admin/                # 新增目录
            ├── AdminLayout.tsx       # 管理后台独立侧边栏布局
            ├── AdminOverview.tsx     # 平台概览仪表盘
            ├── AdminUsers.tsx        # 用户列表
            ├── AdminUserDetail.tsx   # 用户详情 + 角色修改
            ├── AdminServers.tsx      # Server 管理列表
            ├── AdminServerDetail.tsx # Server 详情分析
            ├── AdminAnalytics.tsx    # 使用趋势分析
            ├── AdminReviews.tsx      # 评价审核
            └── AdminAuditLog.tsx     # 操作审计日志
```

---

## 二、后端 API 详细设计

### 2.1 鉴权装饰器

```python
# routes_admin.py

async def _require_admin(x_user_id: str = Header("anonymous")) -> str:
    """验证管理员身份。非 admin 抛出 McpHubError(403)。"""
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import UserModel
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(UserModel.role).where(UserModel.id == x_user_id)
        )
        row = result.fetchone()
        if not row or row[0] != "admin":
            from mcp_hub.exceptions import McpHubError
            raise McpHubError("需要管理员权限", code="ADMIN_REQUIRED", http_status=403)
    return x_user_id
```

所有 admin 端点签名模式：
```python
@router.get("/admin/xxx")
async def admin_xxx(x_user_id: str = Depends(_require_admin), ...):
    ...
```

### 2.2 端点详细规格

#### `GET /admin/overview` — 平台概览

**数据来源**：四表聚合查询

```sql
-- 总用户数
SELECT COUNT(*) FROM users

-- 总 Server 数
SELECT COUNT(*) FROM servers

-- 总安装次数
SELECT COUNT(*) FROM user_servers

-- 总调用次数 + Token
SELECT COUNT(*), SUM(token_count) FROM usage_stats

-- 7 日活跃用户
SELECT COUNT(DISTINCT user_id) FROM usage_stats
WHERE created_at >= NOW() - INTERVAL '7 days'

-- 每日趋势（30 天）
SELECT DATE(created_at) AS day, COUNT(*), SUM(token_count)
FROM usage_stats
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY day

-- Top 10 Server（按安装数）
SELECT s.id, s.name, COUNT(us.server_id) AS installs
FROM user_servers us JOIN servers s ON us.server_id = s.id
GROUP BY s.id, s.name ORDER BY installs DESC LIMIT 10

-- Top 10 用户（按 7 日调用）
SELECT user_id, COUNT(*) AS calls
FROM usage_stats WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY user_id ORDER BY calls DESC LIMIT 10
```

**响应格式**：
```json
{
  "success": true,
  "data": {
    "stats": {
      "total_users": 156, "total_servers": 983, "total_installs": 2341,
      "total_calls": 125000, "total_tokens": 4500000, "active_users_7d": 43
    },
    "daily_trend": [
      { "date": "2026-06-03", "calls": 520, "tokens": 18200 },
      ...
    ],
    "top_servers": [{ "id": "...", "name": "...", "installs": 89, "calls_7d": 3400 }],
    "top_users": [{ "user_id": "alice", "display_name": "Alice", "calls_7d": 5230 }]
  }
}
```

#### `GET /admin/users` — 用户列表

**查询参数**：`q`（搜索）、`sort`（calls/installs/created，默认 calls）、`page`、`page_size`

**数据来源**：`users` LEFT JOIN `user_servers` + `usage_stats` 子查询聚合

```sql
SELECT u.id, u.display_name, u.avatar_url, u.role, u.created_at, u.last_login,
       COUNT(DISTINCT us.server_id) AS server_count,
       COALESCE(stats.calls_7d, 0) AS calls_7d,
       COALESCE(stats.tokens_7d, 0) AS tokens_7d,
       COALESCE(stats.last_active, u.last_login) AS last_active
FROM users u
LEFT JOIN user_servers us ON u.id = us.user_id
LEFT JOIN (
    SELECT user_id, COUNT(*) AS calls_7d, SUM(token_count) AS tokens_7d,
           MAX(created_at) AS last_active
    FROM usage_stats WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY user_id
) stats ON u.id = stats.user_id
WHERE (:q = '' OR u.id ILIKE '%' || :q || '%' OR u.display_name ILIKE '%' || :q || '%')
GROUP BY u.id, stats.calls_7d, stats.tokens_7d, stats.last_active
ORDER BY ... LIMIT :page_size OFFSET :offset
```

**响应格式**：
```json
{
  "success": true,
  "data": [
    { "user_id": "alice", "display_name": "Alice", "avatar_url": "...",
      "role": "user", "server_count": 5, "calls_7d": 340, "tokens_7d": 12800,
      "last_active": "2026-07-03T10:30:00", "created_at": "2026-06-01T08:00:00" }
  ],
  "meta": { "total": 156, "page": 1, "page_size": 20 }
}
```

#### `GET /admin/users/{user_id}` — 用户详情

**数据来源**：`users` + `user_servers` + `usage_stats` 聚合

```json
{
  "success": true,
  "data": {
    "profile": { "id": "alice", "display_name": "Alice", "avatar_url": "...",
                 "email": "...", "role": "user", "created_at": "...", "last_login": "..." },
    "stats": { "server_count": 5, "total_calls": 12340, "total_tokens": 450000,
               "favorite_count": 3 },
    "servers": [
      { "server_id": "@org/foo", "name": "foo", "calls_7d": 340, "tokens_7d": 12800, "enabled": true }
    ],
    "daily_trend": [
      { "date": "2026-07-01", "calls": 45, "tokens": 1600 }
    ],
    "top_tools": [
      { "tool_name": "search", "count": 230 }
    ]
  }
}
```

#### `PATCH /admin/users/{user_id}/role` — 修改角色

**请求体**：`{"role": "admin"}` 或 `{"role": "user"}`

**逻辑**：
1. 验证目标用户存在
2. `UPDATE users SET role = :role WHERE id = :user_id`
3. 写入审计日志（notifications 表，type=audit）

#### `GET /admin/servers` — Server 管理列表

**查询参数**：`q`、`category`、`sort`（installs/calls/rating，默认 installs）、`page`、`page_size`

**数据来源**：`servers` LEFT JOIN `user_servers` + `usage_stats`

```json
{
  "data": [
    { "server_id": "@org/foo", "name": "foo", "categories": ["browser"],
      "install_count": 89, "calls_7d": 3400, "tokens_7d": 120000,
      "rating": 4.5, "security_level": "reviewed" }
  ],
  "meta": { "total": 983, "page": 1, "page_size": 20 }
}
```

#### `GET /admin/servers/{server_id}` — Server 详情

与 `/admin/users/{user_id}` 对称，含 Server 基本信息 + 安装用户列表 + 每日趋势 + 工具排行。

#### `GET /admin/analytics/daily` — 平台每日趋势

**查询参数**：`days`（默认 30）

```sql
SELECT DATE(created_at) AS day, COUNT(*), SUM(token_count),
       COUNT(DISTINCT user_id) AS active_users,
       COUNT(DISTINCT server_id) AS active_servers
FROM usage_stats
WHERE created_at >= NOW() - INTERVAL ':days days'
GROUP BY DATE(created_at) ORDER BY day
```

#### `GET /admin/analytics/top-servers` — Top Server

**查询参数**：`metric`（calls/tokens/installs，默认 calls）、`days`（默认 7）、`limit`（默认 10）

#### `GET /admin/analytics/top-users` — Top 用户

同上，按用户维度聚合。

#### `GET /admin/reviews` — 评价列表

**查询参数**：`page`、`page_size`

**数据来源**：`reviews` JOIN `servers`

```json
{
  "data": [
    { "id": 1, "server_id": "@org/foo", "user_id": "alice", "rating": 5,
      "content": "...", "created_at": "..." }
  ],
  "meta": { "total": 520, "page": 1, "page_size": 20 }
}
```

#### `DELETE /admin/reviews/{review_id}` — 删除评价

调用已有的 `ReviewRepository.delete_review()`，管理员角色硬编码为 `"admin"`。

### 2.3 API 注册

在 `app.py` 中：
```python
from mcp_hub.api.routes_admin import router as admin_router
app.include_router(admin_router, prefix="/api/v1")
```

---

## 三、前端组件详细设计

### 3.1 AdminLayout.tsx

独立的管理后台侧边栏布局，与普通用户 Layout 隔离。

```tsx
// 侧边栏导航项
const adminNavItems = [
  { path: '/admin', label: '概览', icon: '📊', end: true },
  { path: '/admin/users', label: '用户', icon: '👥' },
  { path: '/admin/servers', label: 'Server', icon: '📦' },
  { path: '/admin/analytics', label: '分析', icon: '📈' },
  { path: '/admin/reviews', label: '审核', icon: '🛡️' },
  { path: '/admin/audit', label: '审计', icon: '📋' },
]
```

**关键逻辑**：
- 进入 `/admin/*` 时检查 `role === "admin"`，非 admin 重定向到 `/`
- 侧边栏风格与主 Layout 一致（可折叠、dark mode 兼容）
- 左上角 "← 返回 Hub" 链接回到 `/`

### 3.2 AdminOverview.tsx

**布局**：6 个统计卡片（2 行 × 3 列）+ 趋势图 + Top 10（左右两栏）

**统计卡片**：复用 `StatCard` 组件（Dashboard 已有相同模式），数据来自 `/admin/overview`

**趋势图**：CSS 柱状图（与 ProfilePage 趋势图同方案）— 每个柱子 = 一天的调用量，颜色深浅代表 Token 量

**Top 10**：两列——左列 Top Server（名称 + 安装数 + 7 日调用），右列 Top 用户（头像 + 用户名 + 7 日调用）

### 3.3 AdminUsers.tsx

**表格列**：头像、用户名、角色标签、Server 数、7 日调用、7 日 Token、最后活跃、注册时间

**搜索**：输入框 + 防抖 300ms → 调用 `/admin/users?q=xxx`

**排序**：点击表头切换（按活跃度 / 安装数 / 注册时间）

**分页**：底部分页栏（与 Market 页面相同模式）

**行点击**：跳转 `/admin/users/:userId`

### 3.4 AdminUserDetail.tsx

**布局**：
- 用户信息卡片（头像、ID、角色、注册时间、最后登录） + 修改角色按钮
- 统计摘要行（Server 数、总调用、总 Token、收藏数）
- "安装的 Server" 表格（含每个 Server 的 7 日调用和 Token）
- 每日调用趋势图（CSS 柱状图）
- Top 5 工具排行

**角色修改**：下拉选择 user/admin → 确认弹窗 → `PATCH /admin/users/{id}/role`

### 3.5 AdminServers.tsx

与 `AdminUsers.tsx` 结构对称：表格 + 搜索 + 分类筛选 + 排序 + 分页。

**表格列**：名称、分类标签、安装用户数、7 日调用、7 日 Token、评分、安全等级。

### 3.6 AdminServerDetail.tsx

与 `AdminUserDetail.tsx` 结构对称：Server 信息 + 统计 + 安装用户列表 + 趋势图 + 工具排行。

### 3.7 AdminAnalytics.tsx

**布局**：
- 日期范围选择器（7d / 30d / 自定义）
- 每日调用 + Token 双数据柱状图
- Top 10 工具表格（工具名、调用次数、Token 消耗）
- Top 10 用户表格（用户名、调用次数、Token 消耗）

### 3.8 AdminReviews.tsx

**表格列**：评价 ID、Server、用户、评分、内容（截断 100 字）、时间、操作（删除按钮）。

**删除**：确认弹窗 → `DELETE /admin/reviews/{id}` → 刷新列表

### 3.9 AdminAuditLog.tsx

**数据来源**：`notifications` 表，`type = 'audit'`

**表格列**：时间、操作人、操作类型、目标对象、详情。支持按操作类型筛选。

---

## 四、数据库规范

### 已有可用表（无需新建）

| 表 | 用途 |
|----|------|
| `users` | 用户列表、角色管理 |
| `servers` | Server 列表、分类筛选 |
| `user_servers` | 安装数统计 |
| `usage_stats` | 调用数/Token 聚合（含 user_id + token_count） |
| `notifications` | 审计日志（type=audit） |
| `reviews` | 评价审核 |

### 关键查询模式

```python
# 聚合模式 1：用户维度统计
SELECT u.*,
       COUNT(DISTINCT us.server_id) AS server_count,
       COALESCE(s.calls_7d, 0) AS calls_7d,
       COALESCE(s.tokens_7d, 0) AS tokens_7d
FROM users u
LEFT JOIN user_servers us ON u.id = us.user_id
LEFT JOIN (
    SELECT user_id, COUNT(*) AS calls_7d, SUM(token_count) AS tokens_7d
    FROM usage_stats WHERE created_at >= :since
    GROUP BY user_id
) s ON u.id = s.user_id
GROUP BY u.id, s.calls_7d, s.tokens_7d

# 聚合模式 2：每日趋势
SELECT DATE(created_at) AS day,
       COUNT(*) AS calls,
       SUM(token_count) AS tokens,
       COUNT(DISTINCT user_id) AS users,
       COUNT(DISTINCT server_id) AS servers
FROM usage_stats
WHERE created_at >= :since
GROUP BY DATE(created_at)
ORDER BY day

# 聚合模式 3：Top 排行
SELECT server_id, COUNT(*) AS calls, SUM(token_count) AS tokens
FROM usage_stats WHERE created_at >= :since
GROUP BY server_id
ORDER BY calls DESC LIMIT :limit
```

### SQLite 兼容

所有时间函数需要双写：
```python
if "postgresql" in str(session.get_bind().url):
    time_filter = text(f"created_at >= NOW() - INTERVAL '{days} days'")
else:
    time_filter = text(f"created_at >= datetime('now', '-{days} days')")
```

---

## 五、实施顺序与依赖

```
Phase 1: routes_admin.py 骨架 + _require_admin + overview 端点
    ↓
Phase 2: AdminLayout + AdminOverview（第一个可验证的页面）
    ↓
Phase 3: users 端点 + AdminUsers + AdminUserDetail
    ↓
Phase 4: servers 端点 + AdminServers + AdminServerDetail
    ↓
Phase 5: analytics 端点 + AdminAnalytics
    ↓
Phase 6: reviews 端点 + audit 端点 + AdminReviews + AdminAuditLog
    ↓
Phase 7: App.tsx 路由 + Layout.tsx 入口 + 角色守卫
    ↓
Phase 8: 测试 + Skill 自查 + 部署
```

每个 Phase 完成后可独立验证（curl API / 访问页面）。后续 Phase 不阻塞前面。

---

## 六、测试策略

### 新增测试文件

```
tests/
└── admin/
    └── test_admin_api.py    # Admin API 端点测试（~20 个用例）
```

### 测试用例

```python
# 鉴权测试
async def test_admin_endpoint_rejects_non_admin(async_client):
    """非 admin 用户访问 admin 端点返回 403。"""
    ...

async def test_admin_endpoint_allows_admin(async_client, admin_user):
    """admin 用户正常访问。"""
    ...

# 概览测试
async def test_overview_returns_all_stats(async_client):
    """概览端点返回 6 个统计指标 + 趋势 + Top 10。"""
    ...

# 用户管理测试
async def test_admin_users_list_paginated(async_client):
    """用户列表支持分页和搜索。"""
    ...

async def test_admin_can_change_user_role(async_client):
    """管理员可以修改用户角色。"""
    ...

# Server 分析测试
async def test_admin_servers_list(async_client):
    """Server 列表包含安装数和调用统计。"""
    ...

# 数据验证
async def test_usage_stats_aggregation(async_client, seed_usage_data):
    """调用统计聚合数据准确。"""
    ...
```

---

## 七、开发注意事项

1. **鉴权在每个端点开头执行**：不要漏掉任何一个 admin 端点
2. **分页默认值**：page=1, page_size=20, max_page_size=100
3. **时间范围默认 7 天**：趋势类端点默认 7 天，支持传 days 参数扩展到 30 天
4. **SQL 注入防护**：所有用户输入用参数化查询，不用字符串拼接
5. **响应格式统一**：`{success, data, meta}` 或 `{success, error}`
6. **前端路由守卫**：`AdminLayout` 的 `useEffect` 中检查 `role`，非 admin 立即 `navigate('/')`
7. **图表不引入重库**：CSS 柱状图 + SVG 折线图，参考 `ProfilePage.tsx` 的已有实现
8. **审计日志即通知**：管理员操作写入 `notifications` 表（type='audit'，user_id=操作人），复用已有 API
