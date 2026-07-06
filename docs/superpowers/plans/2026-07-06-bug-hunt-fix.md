# McpServerHub 全量 Bug 修复方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 systematic-bug-hunting 审查发现的 16 Critical + 68 High + 150+ Medium 级别问题

**Architecture:** 按根因分 10 组，每组内依赖顺序修复。先修安全漏洞（认证/Git/注入），再修数据一致性，最后修体验问题。每组完成后独立验证。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 async / PostgreSQL 18.4 / React 19 / Tailwind CSS / Vite / TypeScript

## Global Constraints

- 每处改动必须是最小改动，不顺手重构不相关的代码
- 每组修复后立即验证：类型检查 + 相关测试 + 手动冒烟
- 安全相关的修复优先于功能和体验修复
- 数据库 schema 变更必须先于代码变更
- 前端修复从共享层（client.ts）开始，再到各页面
- 敏感配置绝不硬编码，仅从 .env 或环境变量读取

---

## 修复总览

| 组 | 名称 | 严重度 | 涉及文件 | 预估耗时 |
|----|------|--------|---------|:--------:|
| G1 | Git 安全清理 | CRITICAL | 无代码改动 | 30 min |
| G2 | 认证系统重构 | CRITICAL | auth.py, routes_*.py, client.ts | 3h |
| G3 | 命令注入与路径遍历 | CRITICAL | init_cmd.py, logs.py, routes_realtime.py | 1h |
| G4 | 死代码/空壳功能修复 | CRITICAL | daemon.py, config.py, logging_config.py | 1h |
| G5 | 数据一致性修复 | CRITICAL | repositories.py, 多个 routes | 2h |
| G6 | 错误处理规范化 | HIGH | routes_*.py, core/*.py, db/database.py | 2h |
| G7 | 前端共享层修复 | HIGH | client.ts, Layout.tsx, main.tsx | 1.5h |
| G8 | 后端 Core 层修复 | HIGH | process_manager.py, mcp_gateway.py 等 | 2h |
| G9 | 数据库 Schema 优化 | HIGH | models.py, database.py | 1h |
| G10 | 基础设施加固 | HIGH | Dockerfile, CI, deploy/ | 1h |

---

## G1: Git 安全清理

**根因:** 初始提交中硬编码了真实凭据，虽在 HEAD 中移除但 git 历史永存。

**波及范围:** 任何能访问 GitHub 仓库的人都能提取 OAuth Secret、JWT 密钥、数据库密码。

### Task 1.1: 吊销并更换 GitHub OAuth 凭据

**操作步骤（无代码改动，纯运维操作）:**

- [ ] **Step 1: 吊销旧凭据**

打开 https://github.com/settings/developers → 找到 app `Ov23li9rAd3GLySJaUpC` → 点击 "Generate a new client secret" → 旧 secret 自动失效

- [ ] **Step 2: 更新生产环境 .env**

```bash
ssh djl@172.19.138.78
# 编辑 /home/djl/code/McpServerHub/.env
# 更新 MCP_HUB_GITHUB_CLIENT_ID=新的ID
# 更新 MCP_HUB_GITHUB_CLIENT_SECRET=新的SECRET
sudo systemctl restart mcp-hub
```

- [ ] **Step 3: 验证**

```bash
curl http://172.19.138.78:3987/api/v1/auth/login
# 确认返回的 GitHub 授权 URL 中包含新的 Client ID
```

### Task 1.2: 更换 JWT 密钥

- [ ] **Step 1: 生成新密钥**

```bash
python3 -c "import os; print(os.urandom(32).hex())"
# 输出例如: a1b2c3d4e5f6...（64位十六进制）
```

- [ ] **Step 2: 更新生产环境**

```bash
ssh djl@172.19.138.78
# 编辑 .env: MCP_HUB_SECRET=新密钥
sudo systemctl restart mcp-hub
```

- [ ] **Step 3: 验证** — 所有现有用户需重新登录（旧 token 失效）

### Task 1.3: 从 Git 历史清除敏感文件

- [ ] **Step 1: 安装 BFG Repo-Cleaner**

```bash
# 下载 bfg-1.14.0.jar 到本地
```

- [ ] **Step 2: 创建敏感字符串文件**

```bash
# 创建 passwords.txt:
Ov23li9rAd3GLySJaUpC
f34b991fede4298557345b7ace37c434c0313b33
mcp-hub-prod-secret-key
***REMOVED***
```

- [ ] **Step 3: 运行 BFG**

```bash
git clone --mirror https://github.com/blankbrains/McpServerHub repo-mirror.git
java -jar bfg-1.14.0.jar --replace-text passwords.txt repo-mirror.git
cd repo-mirror.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
```

- [ ] **Step 4: 通知所有协作者** — 强制推送后需重新 clone

### Task 1.4: 移除配置文件中的硬编码密码

- [ ] **Step 1: 修改 `docker-compose.yml`**

```yaml
# docker-compose.yml:8 — 改为:
environment:
  POSTGRES_PASSWORD: ${MCP_HUB_DB_PASSWORD:-change_me}

# docker-compose.yml:24 — 改为:
DATABASE_URL: postgresql+asyncpg://mcp_hub:${MCP_HUB_DB_PASSWORD:-change_me}@db:5432/mcp_hub
```

- [ ] **Step 2: 修改 `.github/workflows/ci.yml`**

```yaml
# ci.yml:17 — 改为:
MCP_HUB_DATABASE_URL: postgresql+asyncpg://postgres:${{ secrets.DB_PASSWORD }}@localhost:5432/mcp_hub_test

# ci.yml:52 — 同样替换
```

- [ ] **Step 3: 修改 `deploy/mcp-hub.service`**

```ini
# 移除 Environment="DATABASE_URL=..." 行
# 添加:
EnvironmentFile=/home/djl/code/McpServerHub/.env
```

- [ ] **Step 4: 提交**

```bash
git add docker-compose.yml .github/workflows/ci.yml deploy/mcp-hub.service
git commit -m "security: remove hardcoded passwords, use env vars"
```

---

## G2: 认证系统重构

**根因:** 整个系统的"认证"建立在不可信的 HTTP Header（`x-user-id`）上，服务端无 JWT 验证，客户端用 localStorage 存身份和 token。

**波及范围:** `auth.py`, `routes_admin.py`, 所有 `routes_*.py` 文件, `client.ts`, `Layout.tsx`

### Task 2.1: 创建 `Depends(get_current_user)` 认证依赖

**Files:**
- Create: `src/mcp_hub/api/dependencies.py`
- Modify: `src/mcp_hub/core/auth.py:166-173`

- [ ] **Step 1: 创建认证依赖模块**

```python
# src/mcp_hub/api/dependencies.py
"""FastAPI 认证/鉴权依赖"""
from typing import Optional
from fastapi import Header, HTTPException, Depends
from mcp_hub.core.auth import AuthService
from mcp_hub.config import get_settings


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
) -> str:
    """
    验证用户身份，返回 user_id。
    优先级: Authorization: Bearer <token> > x-user-id header
    
    注意: x-user-id 仅用于 CLI 工具/内部调用的向后兼容，
    未来版本将移除此 fallback。
    """
    auth_service = AuthService(get_settings())

    # 1. 优先验证 JWT token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = auth_service.verify_token(token)
        if payload:
            return payload["sub"]

    # 2. 向后兼容: x-user-id header（标记为 deprecated）
    if x_user_id and x_user_id not in ("anonymous", "api-user", ""):
        return x_user_id

    raise HTTPException(status_code=401, detail="需要登录")


async def get_admin_user(
    user_id: str = Depends(get_current_user),
) -> str:
    """要求管理员权限。在 get_current_user 之后调用。"""
    from mcp_hub.db.repositories import UserRepository
    from mcp_hub.db.database import async_session_factory

    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
    return user_id
```

- [ ] **Step 2: 修复 `auth.py:verify_token` 不再自动创建用户**

```python
# src/mcp_hub/core/auth.py:166-173 — 改为:
def verify_token(self, token: str) -> dict | None:
    payload = simple_jwt_decode(token, self.settings.SECRET_KEY)
    if not payload:
        return None

    sub = payload.get("sub")
    if not sub:
        return None

    # 只验证，不创建用户（修复 C-4）
    # 用户必须通过 OAuth 流程创建
    return payload
```

- [ ] **Step 3: 修复 `auth.py` OAuth state 验证**

```python
# src/mcp_hub/core/auth.py — 修改 OAuth 流程:
import secrets

# 在 get_login_url 中生成并存储 state:
def get_login_url(self) -> str:
    state = secrets.token_urlsafe(32)
    # 将 state 存入 Redis 或签名 cookie
    # 简单实现: 存入内存 dict（生产应换 Redis）
    self._oauth_states[state] = time.time()
    return f"https://github.com/login/oauth/authorize?client_id={...}&state={state}"

# 在 authenticate_with_github 中验证 state:
def authenticate_with_github(self, code: str, state: str) -> dict:
    # 验证 state 参数（修复 C-5）
    if state not in self._oauth_states:
        return {"success": False, "error": "CSRF 验证失败"}
    del self._oauth_states[state]
    # ... 继续原有流程
```

- [ ] **Step 4: 替换 `routes_admin.py` 中的 `_require_admin`**

```python
# src/mcp_hub/api/routes_admin.py
# 删除旧的 _require_admin 函数
# 在所有 admin 路由上添加依赖:
from mcp_hub.api.dependencies import get_admin_user

@router.get("/admin/overview")
async def admin_overview(admin_user: str = Depends(get_admin_user)):
    # admin_user 是已验证的管理员 user_id
    ...
```

- [ ] **Step 5: 在所有 routes 文件中替换 `Header("anonymous")`**

对每个路由文件（`routes_community.py`, `routes_config.py`, `routes_manage.py`, `routes_market.py`, `routes_notifications.py`, `routes_presets.py`, `routes_publish.py`, `routes_usage.py`, `routes_monitor.py`, `routes_security.py`, `routes_token.py`, `routes_realtime.py`, `routes_export.py`）：

```python
# 旧代码:
async def some_route(x_user_id: str = Header("anonymous")):
    ...

# 新代码:
from mcp_hub.api.dependencies import get_current_user

@router.get("/path")
async def some_route(user_id: str = Depends(get_current_user)):
    ...
```

对于确实允许匿名访问的端点（如市场搜索），使用 Optional 依赖:

```python
from mcp_hub.api.dependencies import get_optional_user

@router.get("/market/search")
async def search(
    q: str = Query(""),
    user_id: Optional[str] = Depends(get_optional_user),
):
    ...
```

- [ ] **Step 6: 更新 `get_optional_user` 依赖**

```python
# src/mcp_hub/api/dependencies.py 追加:

async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
) -> Optional[str]:
    """返回用户 ID 或 None（允许匿名访问）"""
    try:
        return await get_current_user(authorization=authorization, x_user_id=x_user_id)
    except HTTPException:
        return None
```

- [ ] **Step 7: 前端 `client.ts` — 添加 token 到所有请求**

```typescript
// src/mcp_hub/web/src/api/client.ts

function getAuthHeaders(): Record<string, string> {
  const auth = getAuthState();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (auth.token) {
    headers['Authorization'] = `Bearer ${auth.token}`;
  }
  // x-user-id 仅作为 fallback（标记 deprecated）
  if (auth.userId && !auth.token) {
    headers['x-user-id'] = auth.userId;
  }
  return headers;
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString(), {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`API error ${res.status}: ${errBody}`);
  }
  return res.json();
}
```

- [ ] **Step 8: 修复 SSE 连接中的 Token 泄露**

```typescript
// src/mcp_hub/web/src/api/client.ts
// 不再将 token 放在 URL query string 中
// 改用 short-lived ticket exchange:

export function connectLogSSE(serverId: string): EventSource {
  // 方案 A: 如果后端支持 cookie-based session，直接连接
  // 方案 B: 使用 ticket exchange
  const ticket = await fetch(`/api/v1/auth/sse-ticket?server=${serverId}`)
    .then(r => r.json())
    .then(d => d.ticket);
  return new EventSource(`/api/v1/realtime/logs/${serverId}?ticket=${ticket}`);
}
```

- [ ] **Step 9: 验证**

```bash
# 1. 未认证请求应返回 401
curl -s http://localhost:3987/api/v1/admin/overview | python3 -m json.tool
# 预期: {"detail": "需要登录"}

# 2. 普通用户访问 admin 应返回 403
curl -s -H "Authorization: Bearer <普通用户token>" \
  http://localhost:3987/api/v1/admin/overview
# 预期: {"detail": "需要管理员权限"}

# 3. 管理员正常访问
curl -s -H "Authorization: Bearer <管理员token>" \
  http://localhost:3987/api/v1/admin/overview
# 预期: 正常数据

# 4. 前端: 手动清除 localStorage token，访问需要登录的页面
# 预期: 自动跳转登录页
```

- [ ] **Step 10: 提交**

```bash
git add src/mcp_hub/api/dependencies.py \
        src/mcp_hub/core/auth.py \
        src/mcp_hub/api/routes_admin.py \
        src/mcp_hub/api/routes_community.py \
        src/mcp_hub/api/routes_config.py \
        src/mcp_hub/api/routes_manage.py \
        src/mcp_hub/api/routes_market.py \
        src/mcp_hub/api/routes_notifications.py \
        src/mcp_hub/api/routes_presets.py \
        src/mcp_hub/api/routes_publish.py \
        src/mcp_hub/api/routes_usage.py \
        src/mcp_hub/web/src/api/client.ts
git commit -m "security: implement JWT-based authentication, replace fake headers"
```

---

## G3: 命令注入与路径遍历

**根因:** 用户输入直接拼接到 shell 命令或文件路径中。

### Task 3.1: 修复 Shell 注入

**Files:**
- Modify: `src/mcp_hub/cli/init_cmd.py:111-121`

- [ ] **Step 1: 替换 `os.system()` 为安全的 `subprocess`**

```python
# src/mcp_hub/cli/init_cmd.py:111-121 — 改为:
def _setup_crontab():
    """配置 crontab 定期健康检查，使用 subprocess 避免 shell 注入"""
    import subprocess

    python_path = sys.executable
    cwd = os.getcwd()
    mcp_port = os.environ.get("MCP_HUB_PORT", "3987")

    cron_line = f"*/5 * * * * cd {cwd} && {python_path} -m mcp_hub.cli monitor --all"

    try:
        # 获取现有 crontab
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True
        )
        existing = result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        existing = ""

    # 检查是否已存在
    if cron_line in existing:
        console.print("[yellow]Crontab 任务已存在[/yellow]")
        return

    new_crontab = existing.rstrip("\n") + "\n" + cron_line + "\n"

    # 通过 stdin 传入，不经过 shell
    subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        text=True,
        check=True,
    )
    console.print("[green]Crontab 健康检查任务已配置[/green]")
```

- [ ] **Step 2: 验证**

```bash
mcp init
# 检查 crontab -l 是否正确添加了任务
crontab -l | grep mcp_hub
```

### Task 3.2: 修复路径遍历

**Files:**
- Modify: `src/mcp_hub/cli/logs.py:19`
- Modify: `src/mcp_hub/api/routes_realtime.py:19`

- [ ] **Step 1: 添加路径清理函数**

```python
# src/mcp_hub/cli/logs.py — 添加:
import os
from pathlib import Path

def safe_log_path(log_dir: str, server_id: str) -> Path:
    """返回安全的日志文件路径，防止路径遍历攻击"""
    # 只保留字母数字、下划线和连字符
    safe_name = "".join(c for c in server_id if c.isalnum() or c in "_-")
    if not safe_name:
        raise ValueError(f"无效的 server_id: {server_id}")

    log_file = Path(log_dir).resolve() / f"{safe_name}.log"

    # 确保解析后的路径在日志目录内
    if not str(log_file.resolve()).startswith(str(Path(log_dir).resolve())):
        raise ValueError(f"路径遍历检测: {server_id}")

    return log_file
```

- [ ] **Step 2: 在 logs.py 中使用安全路径**

```python
# src/mcp_hub/cli/logs.py:19 — 改为:
log_file = safe_log_path(str(log_dir), server_id)
```

- [ ] **Step 3: 在 routes_realtime.py 中使用安全路径**

```python
# src/mcp_hub/api/routes_realtime.py:19 — 改为:
from mcp_hub.cli.logs import safe_log_path

log_file = safe_log_path(str(log_dir), server_id)
```

- [ ] **Step 4: 验证**

```bash
# 测试路径遍历攻击
curl "http://localhost:3987/api/v1/realtime/logs/..%2F..%2F..%2Fetc%2Fpasswd"
# 预期: 404 或 400 错误，不应返回文件内容
```

- [ ] **Step 5: 提交**

```bash
git add src/mcp_hub/cli/init_cmd.py \
        src/mcp_hub/cli/logs.py \
        src/mcp_hub/api/routes_realtime.py
git commit -m "security: fix shell injection in init_cmd and path traversal in logs"
```

---

## G4: 死代码/空壳功能修复

**根因:** 功能声明但未实现或生效。

### Task 4.1: 修复 daemon 命令

**Files:**
- Modify: `src/mcp_hub/cli/daemon.py`

- [ ] **Step 1: 实现 stop_daemon**

```python
# src/mcp_hub/cli/daemon.py
import os
import signal
from pathlib import Path

PID_FILE = Path.home() / ".config" / "mcp-hub" / "mcp-hub.pid"

@cli.command()
def stop():
    """停止 MCP Hub 守护进程"""
    if not PID_FILE.exists():
        console.print("[yellow]MCP Hub 未在运行[/yellow]")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        console.print("[green]MCP Hub 已停止[/green]")
    except ProcessLookupError:
        PID_FILE.unlink()
        console.print("[yellow]进程已不存在，已清理 PID 文件[/yellow]")
    except Exception as e:
        console.print(f"[red]停止失败: {e}[/red]")
        raise SystemExit(1)
```

- [ ] **Step 2: 实现 enable/disable**

```python
import shutil

SYSTEMD_UNIT_TEMPLATE = """[Unit]
Description=MCP Server Hub
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={cwd}
ExecStart={python} -m uvicorn mcp_hub.main:app --host 0.0.0.0 --port {port}
Restart=on-failure
EnvironmentFile={env_file}

[Install]
WantedBy=default.target
"""

@cli.command()
def enable():
    """配置开机自启（创建 systemd user service）"""
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / "mcp-hub.service"

    unit_content = SYSTEMD_UNIT_TEMPLATE.format(
        user=os.environ.get("USER", "djl"),
        cwd=os.getcwd(),
        python=sys.executable,
        port=os.environ.get("MCP_HUB_PORT", "3987"),
        env_file=Path(os.getcwd()) / ".env",
    )
    unit_path.write_text(unit_content)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "mcp-hub"], check=True)
    console.print(f"[green]已创建并启用 systemd 服务: {unit_path}[/green]")

@cli.command()
def disable():
    """禁用开机自启"""
    unit_path = Path.home() / ".config" / "systemd" / "user" / "mcp-hub.service"
    if unit_path.exists():
        subprocess.run(["systemctl", "--user", "disable", "mcp-hub"], check=True)
        unit_path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        console.print("[green]已禁用开机自启[/green]")
    else:
        console.print("[yellow]未找到 systemd 服务文件[/yellow]")
```

### Task 4.2: 修复 config import

**Files:**
- Modify: `src/mcp_hub/cli/config.py:72-76`

- [ ] **Step 1: 让 import_config 真正存储配置**

```python
# src/mcp_hub/cli/config.py:72-76 — 改为:
@cli.command()
def import_config(path: str):
    """导入配置文件"""
    import_path = Path(path)
    if not import_path.exists():
        console.print(f"[red]文件不存在: {path}[/red]")
        return

    try:
        with open(import_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON 格式错误: {e}[/red]")
        return

    cm = ConfigManager()
    # 实际保存配置
    success = cm.save_config("imported", data)
    if success:
        console.print(f"[green]已导入配置文件: {import_path}[/green]")
    else:
        console.print("[red]配置保存失败[/red]")
```

### Task 4.3: 确保 logging 配置被调用

**Files:**
- Modify: `src/mcp_hub/main.py`

- [ ] **Step 1: 在 create_app 中调用 configure_logging**

```python
# src/mcp_hub/main.py:12 — 在 create_app() 开头添加:
from mcp_hub.logging_config import configure_logging

def create_app(dev: bool = False):
    configure_logging()  # 修复 C-16: 之前从未调用
    # ... 原有代码
```

---

## G5: 数据一致性修复

**根因:** 多个 `commit()` 分布在事务的不同阶段。

### Task 5.1: 合并 rate() 的双 commit

**Files:**
- Modify: `src/mcp_hub/db/repositories.py:240-270`

- [ ] **Step 1: 移除中间的 commit**

```python
# src/mcp_hub/db/repositories.py — rate 方法:
async def rate(self, server_id: str, user_id: str, rating: int) -> dict:
    # ... 查找或创建 review ...

    # ❌ 旧代码: await self.session.commit()  # 第一个 commit
    # ❌ 旧代码: 然后做 rating 聚合更新
    # ❌ 旧代码: await self.session.commit()  # 第二个 commit

    # ✅ 新代码: 先做所有修改，最后一次性 commit
    self.session.add(review)

    # 计算并更新 server 聚合评分（同一事务内）
    result = await self.session.execute(
        select(func.avg(ReviewModel.rating), func.count(ReviewModel.id))
        .where(ReviewModel.server_id == server_id)
    )
    avg_rating, review_count = result.one()

    server = await self.session.get(ServerModel, server_id)
    if server:
        server.rating = round(float(avg_rating or 0), 1)
        server.review_count = review_count

    # 只 commit 一次
    await self.session.commit()
    return {"rating": rating, "avg_rating": server.rating if server else 0, "review_count": review_count}
```

### Task 5.2: 合并 favorite() 的双 commit

**Files:**
- Modify: `src/mcp_hub/db/repositories.py:380-415`

- [ ] **Step 1: 同样合并为单次 commit**

```python
# src/mcp_hub/db/repositories.py — favorite 方法:
async def favorite(self, server_id: str, user_id: str) -> dict:
    existing = await self.session.execute(
        select(FavoriteModel).where(
            FavoriteModel.server_id == server_id,
            FavoriteModel.user_id == user_id,
        )
    )
    existing = existing.scalar_one_or_none()

    if existing:
        await self.session.delete(existing)
        action = "removed"
    else:
        fav = FavoriteModel(server_id=server_id, user_id=user_id)
        self.session.add(fav)
        action = "added"

    # 计算 favorite 数量
    result = await self.session.execute(
        select(func.count(FavoriteModel.id)).where(
            FavoriteModel.server_id == server_id
        )
    )
    count = result.scalar()

    server = await self.session.get(ServerModel, server_id)
    if server:
        server.favorite_count = count

    # 只 commit 一次（修复 C-10）
    await self.session.commit()
    return {"action": action, "favorite_count": count}
```

### Task 5.3: 所有 route 文件统一使用 `get_session()` context manager

- [ ] **Step 1: 搜索并替换所有 `async with async_session_factory() as session:` 为 `async with get_session() as session:`**

```bash
grep -r "async_session_factory()" src/mcp_hub/api/ src/mcp_hub/cli/
# 逐个替换，确保 get_session 提供自动 commit/rollback
```

### Task 5.4: 修复 register_server 中的 falsy 值问题

**Files:**
- Modify: `src/mcp_hub/db/repositories.py:181-185`

- [ ] **Step 1: 改用 `key in data` 判断**

```python
# src/mcp_hub/db/repositories.py:181-185 — 改为:
else:
    # 创建新 Server
    server = ServerModel()
    for key, value in data.items():
        if hasattr(server, key) and key in data:  # 修复: 用 key in data 而非 value is not None
            setattr(server, key, value)
    session.add(server)
```

---

## G6: 错误处理规范化

**根因:** 多处 `except Exception: pass` 吞错、网络请求无 `res.ok` 检查。

### Task 6.1: 后台 Python 代码 — 消除空 except

- [ ] **Step 1: 批量修复 `database.py` 中 10+ 处空 except**

```python
# src/mcp_hub/db/database.py — 每个 except Exception: pass 改为:
import logging
logger = logging.getLogger(__name__)

# 迁移失败时:
except Exception:
    logger.warning("迁移 %s 失败，跳过", column_name, exc_info=True)
```

- [ ] **Step 2: 修复 routes 中的空 except**

```bash
# 搜索模式:
grep -rn "except Exception:" src/mcp_hub/api/routes_*.py | grep "pass"

# 对每处: 添加 logger.warning(...)
```

对以下文件逐一修复:
- `routes_community.py:53` — 通知失败
- `routes_manage.py:93-94, 106-107` — 安装历史/通知失败
- `routes_monitor.py:43-44, 106-107` — 查询失败
- `routes_usage.py:89-90` — 通知失败
- `routes_notifications.py:136-137` — 创建通知失败
- `routes_export.py:34-40` — 导出失败

- [ ] **Step 3: 修复 core 层空 except**

```python
# security_scanner.py:331-332, 397-398 — 改为:
except Exception:
    logger.warning("安全检查 %s 失败", check_name, exc_info=True)
    findings.append(ScanFinding(
        severity="info",
        title=f"{check_name}: 检查无法完成",
        description="请手动审查此包",
        score_impact=0,
    ))

# version_manager.py:68-69 — 改为:
except Exception:
    logger.debug("版本检查 %s 失败", server_id, exc_info=True)
    return None

# health_check.py:285 — 改为:
try:
    from mcp_hub.core.monitor import Monitor
except ImportError:
    logger.warning("Monitor 模块未安装，跳过可靠性计算")
    return
```

### Task 6.2: 前端 — 消除空 catch + 添加 `res.ok` 检查

- [ ] **Step 1: 创建前端通用 fetch wrapper（已在 G2 Task 2.7 完成）**

确保 `client.ts` 中的 `apiGet` 和 `apiPost` 都检查 `res.ok`

- [ ] **Step 2: 批量修复 — 将所有 `fetch(...).then(r => r.json())` 替换为 `apiGet`**

```bash
# 逐文件替换:
# AdminAnalytics.tsx, AdminAuditLog.tsx, AdminLayout.tsx, AdminOverview.tsx
# AdminReviews.tsx, AdminServerDetail.tsx, AdminServers.tsx
# AdminUserDetail.tsx, AdminUsers.tsx
# Builder.tsx, ComparePage.tsx, ConfigPage.tsx, Dashboard.tsx
# LocalDiscovery.tsx, Market.tsx, MonitorDashboard.tsx
# MyConfig.tsx, MyServers.tsx, NotificationsPage.tsx
# PresetMarket.tsx, ProfilePage.tsx, Publish.tsx, ServerDetail.tsx

# 示例替换 (Dashboard.tsx):
# 旧: fetch('/api/v1/health').then(r => r.json())
# 新: apiGet('/api/v1/health')
```

- [ ] **Step 3: 为所有空 `.catch(() => {})` 添加错误处理**

```typescript
// 旧代码:
fetch(...).then(r => r.json()).catch(() => {})

// 新代码:
fetch(...)
  .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
  .catch(e => {
    console.error('API call failed:', e);
    setError(e instanceof Error ? e.message : '请求失败');
  })
```

---

## G7: 前端共享层修复

### Task 7.1: main.tsx — 添加 Error Boundary

**Files:**
- Create: `src/mcp_hub/web/src/components/ErrorBoundary.tsx`
- Modify: `src/mcp_hub/web/src/main.tsx`

- [ ] **Step 1: 创建 ErrorBoundary**

```tsx
// src/mcp_hub/web/src/components/ErrorBoundary.tsx
import React from 'react';

interface Props { children: React.ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('App error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900">
          <div className="text-center p-8">
            <h1 className="text-2xl font-bold text-red-600 mb-4">应用出错了</h1>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              {this.state.error?.message || '未知错误'}
            </p>
            <button
              onClick={() => { this.setState({ hasError: false }); window.location.reload(); }}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              重新加载
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: 在 main.tsx 中使用**

```tsx
// src/mcp_hub/web/src/main.tsx
import { ErrorBoundary } from './components/ErrorBoundary';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
```

### Task 7.2: 修复 Layout.tsx — Token 管理和登录流程

**Files:**
- Modify: `src/mcp_hub/web/src/components/Layout.tsx`

- [ ] **Step 1: 移除 `getAuthState()` 在 render body 中调用，改为 useEffect 中调用**

```tsx
// Layout.tsx — 不要这样:
// const { userId } = getAuthState();  // 在 render body

// 改为在 useEffect 或 event handler 中调用:
useEffect(() => {
  const { userId } = getAuthState();
  if (userId) {
    poll();  // 开始轮询通知
  }
}, []);
```

- [ ] **Step 2: 修复通知轮询使用 apiGet**

```tsx
// Layout.tsx:82-84 — 改为:
const poll = async () => {
  try {
    const data = await apiGet<{ count: number }>('/notifications/unread-count');
    setUnreadNotif(data?.count ?? 0);
  } catch (e) {
    console.error('通知轮询失败:', e);
  }
};
```

- [ ] **Step 3: 移除 localStorage 密钥检查的冗余轮询**

```tsx
// 移除 setInterval(getAuthState 检查)，替换为 storage 事件监听
// token 过期由服务端 401 响应驱动，不在前端轮询
```

### Task 7.3: 修复 Token 存储

- [ ] **Step 1: `client.ts` 中的 `connectLogSSE` — 移除 URL 中的 token**

已在 G2 Task 2.8 中修复。

---

## G8: 后端 Core 层修复

### Task 8.1: process_manager.py — 进程生命周期修复

**Files:**
- Modify: `src/mcp_hub/core/process_manager.py`

- [ ] **Step 1: 修复 `command.split()` → `shlex.split()`**

```python
# process_manager.py:68 — 改为:
import shlex
args = shlex.split(command)
```

- [ ] **Step 2: 启动失败时清理僵尸进程**

```python
# process_manager.py:100-109 — 改为:
await asyncio.sleep(0.5)
if proc.returncode is not None:
    # 进程已死亡，清理资源
    os.close(log_fd)
    self._processes.pop(server_id, None)
    stderr_output = ""
    try:
        stderr_output = await proc.stderr.read()
    except Exception:
        pass
    raise ProcessStartupError(
        server_id,
        reason=stderr_output.decode()[:500] if stderr_output else "进程启动后立即退出",
    )
```

- [ ] **Step 3: 限制子进程环境变量**

```python
# process_manager.py:78 — 改为:
ALLOWED_ENV = {"PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL", "VIRTUAL_ENV", "CONDA_PREFIX"}

safe_env = {k: v for k, v in os.environ.items() if k in ALLOWED_ENV}
# 只传递白名单中的环境变量
proc = await asyncio.create_subprocess_exec(
    *args,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    env=safe_env,
)
```

- [ ] **Step 4: kill 时取消 keepalive task**

```python
# process_manager.py:157 — 在 kill() 方法中添加:
async def kill(self, server_id: str):
    async with self._lock:
        proc = self._processes.get(server_id)
        if not proc:
            return

        # 取消 keepalive 任务
        task = self._keepalive_tasks.pop(server_id, None)
        if task:
            task.cancel()

        # ... 原有 kill 逻辑
```

- [ ] **Step 5: 初始化 `_keepalive_tasks`**

```python
# process_manager.py:__init__ — 添加:
self._keepalive_tasks: dict[str, asyncio.Task] = {}
```

### Task 8.2: mcp_gateway.py — 关键修复

**Files:**
- Modify: `src/mcp_hub/core/mcp_gateway.py`

- [ ] **Step 1: 读取 stderr（防止子进程挂起）**

```python
# mcp_gateway.py — 在创建子进程后添加:
async def _drain_stderr(proc, server_id):
    """持续读取 stderr 防止管道缓冲区满导致子进程挂起"""
    try:
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            logger.debug("mcp.stderr.%s: %s", server_id, line.decode().rstrip())
    except Exception:
        pass

# 在 spawn 之后:
asyncio.create_task(_drain_stderr(proc, server_id))
```

- [ ] **Step 2: 修复 Server ID 前缀冲突**

```python
# mcp_gateway.py:357 — 改为使用 URL-safe base64 编码:
import base64

def _make_prefix(server_id: str) -> str:
    """生成唯一且可逆的 server ID 前缀"""
    return base64.urlsafe_b64encode(server_id.encode()).decode().rstrip("=")

def _parse_prefix(prefix: str) -> str:
    """从前缀还原 server ID"""
    # 补齐 padding
    padding = 4 - len(prefix) % 4
    if padding != 4:
        prefix += "=" * padding
    return base64.urlsafe_b64decode(prefix.encode()).decode()
```

- [ ] **Step 3: 子进程环境变量限制**

```python
# mcp_gateway.py:285 — 改为:
# 与 process_manager.py 使用相同的白名单
safe_env = {k: v for k, v in os.environ.items() if k in ALLOWED_ENV}
proc = await asyncio.create_subprocess_exec(*args, env=safe_env, ...)
```

### Task 8.3: security_scanner.py — 评分逻辑修复

**Files:**
- Modify: `src/mcp_hub/core/security_scanner.py`

- [ ] **Step 1: 防止正面评分抵消致命问题**

```python
# security_scanner.py:626-631 — 改为:
# 各维度独立评分，任一维度低于阈值则整体降级
DIMENSION_FLOORS = {
    "command_safety": 25,   # 若命令安全分 < 25，总分上限 40
    "package_reputation": 10,
    "publisher_trust": 5,
    "code_patterns": 5,
}

for dim, floor in DIMENSION_FLOORS.items():
    if dimension_scores.get(dim, 0) < floor:
        total = min(total, 40)  # capped at "blocked" level
        break
```

- [ ] **Step 2: npm global install 检测修正**

```python
# security_scanner.py:175-183 — 改为:
import re
# 只标记带 -g 或 --global 的 npm install
if re.search(r'\bnpm\s+(i|install)\b.*\b(-g|--global)\b', install_command):
    findings.append(ScanFinding(
        severity="medium",
        title="全局安装检测",
        description="检测到 npm 全局安装标志 (-g/--global)",
        score_impact=-10,
    ))
```

- [ ] **Step 3: 代码模式检测用词边界**

```python
# security_scanner.py:474 — 改为:
import re
# 使用 \b 词边界匹配
if re.search(r'\bread\b', f.description, re.IGNORECASE):
    ...
```

### Task 8.4: version_manager.py — 修复

- [ ] **Step 1: rollback 真正执行安装**

```python
# version_manager.py:96-115 — 改为:
async def rollback_server(self, server_id: str, target_version: str):
    server = await self.registry.get_by_id(server_id)
    if not server:
        return {"success": False, "error": "Server 不存在"}

    install_cmd = server.get("install_command", "")
    if not install_cmd:
        return {"success": False, "error": "无安装命令"}

    # 实际执行安装（修复: 之前只改 DB 不安装）
    installer = get_installer()
    result = await installer.install(server_id, install_cmd + f"=={target_version}")

    if result["success"]:
        await self._update_db_version(server_id, target_version)
        await self._record_action(server_id, "rollback", target_version)

    return result
```

---

## G9: 数据库 Schema 优化

### Task 9.1: 添加缺失的外键索引

**Files:**
- Modify: `src/mcp_hub/db/models.py`

- [ ] **Step 1: 为所有外键列添加索引**

```python
# models.py — 在以下列上添加 index=True:

class ReviewModel(Base):
    # ...
    server_id = Column(String(255), ForeignKey("servers.id"), index=True, nullable=False)
    user_id = Column(String(255), ForeignKey("users.id"), index=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("reviews.id"), index=True, nullable=True)

class HealthLogModel(Base):
    server_id = Column(String(255), ForeignKey("servers.id"), index=True, nullable=False)

class InstallHistoryModel(Base):
    server_id = Column(String(255), ForeignKey("servers.id"), index=True, nullable=False)

class SubscriptionModel(Base):
    server_id = Column(String(255), ForeignKey("servers.id"), index=True, nullable=False)

class UserServerModel(Base):
    server_id = Column(String(255), ForeignKey("servers.id"), index=True, nullable=False)

class EventModel(Base):
    topic = Column(String(100), index=True, nullable=False)
    created_at = Column(DateTime, index=True, nullable=False)
```

- [ ] **Step 2: 创建 Alembic 迁移**

```bash
cd src/mcp_hub
python -m mcp_hub.db.migrations revision --autogenerate -m "add_fk_indexes"
python -m mcp_hub.db.migrations upgrade head
```

### Task 9.2: 修复 categories/tags 列类型

**Files:**
- Modify: `src/mcp_hub/db/models.py:36-37`

- [ ] **Step 1: 将 Text 改为 JSON**

```python
# models.py:36-37 — 改为:
from sqlalchemy import JSON

categories = Column(JSON, default=list, nullable=False, comment="JSON 数组")
tags = Column(JSON, default=list, nullable=False, comment="JSON 数组")
```

- [ ] **Step 2: 更新所有 ILIKE 查询改为 JSON 查询**

```python
# repositories.py — category 过滤:
# 旧: ServerModel.categories.ilike(f"%{category}%")
# 新 (PostgreSQL):
ServerModel.categories.contains([category])
# 新 (SQLite — 需要额外处理，或保持文本搜索):
```

---

## G10: 基础设施加固

### Task 10.1: Dockerfile 安全加固

**Files:**
- Modify: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: 创建 `.dockerignore`**

```
.venv/
.git/
.gitignore
node_modules/
*.md
!README.md
.env
.env.example
.pytest_cache/
.ruff_cache/
__pycache__/
*.pyc
dist/
```

- [ ] **Step 2: 修复 Dockerfile — 非 root 用户 + 层缓存优化**

```dockerfile
# Dockerfile
FROM python:3.10-slim AS builder
WORKDIR /app

# 先复制依赖文件以利用层缓存
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY src/ src/

# 前端构建
RUN cd src/mcp_hub/web && npm ci && npm run build

# 运行阶段
FROM python:3.10-slim
WORKDIR /app

COPY --from=builder /app /app

# 创建非 root 用户
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 3987
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3987/api/v1/health')" || exit 1

CMD ["python", "-m", "uvicorn", "mcp_hub.main:app", "--host", "0.0.0.0", "--port", "3987"]
```

- [ ] **Step 3: 添加 docker-compose 资源限制和健康检查**

```yaml
# docker-compose.yml — hub 服务:
hub:
  # ... 原有配置 ...
  deploy:
    resources:
      limits:
        memory: 512M
        cpus: '1.0'
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3987/api/v1/health"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 15s
```

### Task 10.2: CI 加固

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 扩展 CI 步骤**

```yaml
# .github/workflows/ci.yml — 新增:
jobs:
  ci:
    # ... 原有步骤后添加:

    - name: Secret scanning
      uses: gitleaks/gitleaks-action@v2
      with:
        config-path: .gitleaks.toml

    - name: SAST scan
      run: |
        pip install bandit
        bandit -r src/mcp_hub/ -f json -o bandit-report.json

    - name: Dependency audit
      run: |
        pip install pip-audit
        pip-audit

    - name: Type check (full scope)
      run: |
        mypy src/mcp_hub/ --ignore-missing-imports
```

### Task 10.3: 从 .gitignore 移除 uv.lock

- [ ] **Step 1: 编辑 `.gitignore`**

```bash
# .gitignore — 删除或注释掉:
# uv.lock
```

- [ ] **Step 2: 提交锁文件**

```bash
git add uv.lock .gitignore
git commit -m "build: track uv.lock for reproducible builds"
```

---

## 修复执行顺序

```
G1 (Git 安全) ──────────────────────────────────────────────────────────┐
G2 (认证系统) ──────────────────────────────────────────────────────────┤
G3 (注入/路径) ─────────────────────────────────────────────────────────┤ 第一批
G4 (死代码)   ──────────────────────────────────────────────────────────┤ (并行)
G5 (数据一致性) ────────────────────────────────────────────────────────┘
                                    │
G6 (错误处理) ──────────────────────┤ 第二批
G8 (Core层)   ──────────────────────┤ (G5 完成后)
                                    │
G9 (DB Schema) ─────────────────────┤ 第三批
                                    │
G7 (前端修复) ──────────────────────┤ 第四批
                                    │
G10 (基础设施) ─────────────────────┘ 第五批
```

---

## 收尾验证

全部修复完成后，运行以下验证:

```bash
# 1. 后端类型检查
mypy src/mcp_hub/ --ignore-missing-imports

# 2. Lint
ruff check src/mcp_hub/

# 3. 全量测试
pytest tests/ -v --tb=short

# 4. 构建前端
cd src/mcp_hub/web && npm run build

# 5. 安全扫描
bandit -r src/mcp_hub/ -ll
gitleaks detect --source .

# 6. 启动应用冒烟
python -m uvicorn mcp_hub.main:app --host 0.0.0.0 --port 3987 &
# 等待 3 秒
curl -s http://localhost:3987/api/v1/health | python3 -m json.tool
# 验证认证:
curl -s http://localhost:3987/api/v1/admin/overview
# 预期: 401

# 7. 前端冒烟
# 打开浏览器 http://localhost:3987
# 验证: 市场搜索、Server 详情、登录流程、管理后台
```

---

## 未处理项

以下问题按计划不在此轮修复（记录到 issue tracker）:

| 问题 | 原因 |
|------|------|
| 前端全部改用 TypeScript 严格类型（替换 `any`）| 工作量大，需分阶段 |
| 所有页面添加完整的 a11y 支持 | 非功能阻塞，单独排期 |
| 虚拟滚动/分页替换大列表 | 性能优化，单独排期 |
| VS Code 插件 / 团队空间 | 远期目标 |
| ServerModel 主键从字符串改为整数 | Schema 迁移风险大 |
