# MCP Server Hub 开发文档

> 生产环境开发指南 —— 面向一人开发团队的工程规范

| 项目 | 内容 |
|------|------|
| **版本** | v1.0 (开发中) |
| **Python 版本** | ≥ 3.10 |
| **包管理** | Uv（推荐）/ Poetry |
| **代码风格** | Ruff + mypy strict |
| **测试框架** | pytest + pytest-asyncio |
| **CI/CD** | GitHub Actions |

---

## 一、环境搭建

### 1.1 前置依赖

```bash
# Python 版本确认
python --version   # ≥ 3.10

# 安装 Uv（推荐，比 pip 快 10-100 倍）
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 验证安装
uv --version

# 安装 Node.js ≥ 18（Web Dashboard 用）
node --version
npm --version
```

### 1.2 克隆与初始化

```bash
# 克隆仓库
git clone <repo-url> && cd McpServerHub

# 创建虚拟环境并安装依赖
uv sync

# 安装开发依赖
uv sync --group dev

# 安装 Web Dashboard 依赖
cd src/mcp_hub/web && npm install && cd ../../..

# 初始化数据库
uv run python -m mcp_hub.db.migrations

# 导入预置 Server 索引
uv run python -m mcp_hub.db.seed

# 验证安装
uv run mcp --help
```

### 1.3 开发环境验证

```bash
# 启动开发模式
uv run mcp daemon start --dev

# 预期输出
✅ MCP Server Hub (dev) 已启动
📍 Web Dashboard: http://localhost:3987
🔌 API: http://localhost:3987/api/v1

# 测试基本命令
uv run mcp search --category browser
uv run mcp info @anthropic/web-search
uv run mcp status

# 退出开发模式
uv run mcp daemon stop
```

### 1.4 IDE 配置

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "python.testing.pytestArgs": ["tests"],
  "python.testing.unittestEnabled": false,
  "python.testing.pytestEnabled": true,
  "files.associations": {
    "*.html": "jinja-html"
  }
}
```

```json
// .vscode/extensions.json
{
  "recommendations": [
    "charliermarsh.ruff",
    "ms-python.python",
    "ms-python.mypy-type-checker",
    "bierner.markdown-mermaid",
    "tamasfe.even-better-toml"
  ]
}
```

---

## 二、项目结构与代码约定

### 2.1 目录职责

```
src/mcp_hub/
├── main.py              # FastAPI 入口（启动 / 路由挂载 / 中间件）
│
├── cli/                 # CLI 层 —— 只做参数解析和输出格式化
│   ├── app.py           # click 主入口，注册所有子命令
│   ├── search.py        # search / info / compare 命令
│   ├── install.py       # install / uninstall / list
│   ├── manage.py        # start / stop / restart / status
│   ├── logs.py          # logs
│   ├── update.py        # update / rollback
│   ├── config.py        # config export / import
│   ├── daemon.py        # daemon start / stop / status / enable
│   ├── publish.py       # publish / unpublish / my-servers / stats
│   ├── community.py     # rate / review / favorite
│   ├── trending.py      # trending / top-rated / most-downloaded
│   ├── event.py         # event subscribe / publish / list / history
│   └── auth.py          # login / logout / whoami
│
├── api/                 # API 层 —— HTTP 路由 + 请求/响应 Schema
│   ├── app.py           # FastAPI 应用实例，CORS / 中间件 / 路由注册
│   ├── routes_market.py     # /api/v1/market/*
│   ├── routes_manage.py     # /api/v1/servers/*
│   ├── routes_publish.py    # /api/v1/publish/*
│   ├── routes_community.py  # /api/v1/community/*
│   ├── routes_health.py     # /api/v1/health/*
│   ├── routes_events.py     # /api/v1/events/*
│   ├── routes_auth.py       # /api/v1/auth/*
│   └── schemas.py           # Pydantic 模型（请求/响应）
│
├── core/                # 核心逻辑层 —— 不含 IO 无关的业务逻辑
│   ├── registry.py      # Server 注册与索引（注册、搜索、排序）
│   ├── process_manager.py # 子进程生命周期管理（spawn / kill / monitor）
│   ├── health_check.py  # 三级健康检查
│   ├── installer.py     # 安装执行器（pip / npm / uvx）
│   ├── version_manager.py # 版本管理（更新检查 / 升级 / 回滚）
│   ├── config_manager.py  # 配置管理（增删改查 / 导入导出 / 环境切换）
│   ├── event_bus.py     # 事件总线（发布 / 订阅 / 路由）
│   ├── security_scanner.py # 安全扫描引擎
│   └── auth.py          # OAuth 认证 + JWT
│
├── models/              # 数据模型层 —— 纯数据结构
│   ├── server.py        # ServerMeta, InstallConfig, SecurityInfo
│   ├── review.py        # Review
│   └── user.py          # User
│
├── db/                  # 数据库层
│   ├── database.py      # SQLite 连接 / 会话管理 / 连接池
│   ├── migrations.py    # 数据库迁移（建表 / 改表 / 版本管理）
│   └── seed.py          # 预置 50+ 热门 Server 索引
│
└── web/                 # Web Dashboard（React SPA）
    ├── app.py           # 静态文件服务 + React 路由
    ├── package.json
    ├── tsconfig.json
    ├── src/
    │   ├── App.tsx
    │   ├── pages/
    │   │   ├── Dashboard.tsx       # 总览仪表盘
    │   │   ├── Market.tsx          # 市场搜索 + 分类
    │   │   ├── ServerDetail.tsx    # Server 详情页
    │   │   ├── MyServers.tsx       # 已安装列表
    │   │   ├── Publish.tsx         # 发布 Server
    │   │   └── Login.tsx           # 登录
    │   ├── components/
    │   │   ├── StatusBadge.tsx     # 状态标签组件
    │   │   ├── StarRating.tsx      # 评分组件
    │   │   ├── LogViewer.tsx       # 日志实时查看器
    │   │   ├── ServerCard.tsx      # Server 卡片
    │   │   └── Layout.tsx          # 布局组件
    │   └── api/
    │       └── client.ts           # API 客户端
    └── public/
```

### 2.2 分层依赖规则

```
           CLI ←→ API ←→ Core ←→ DB
            │       │       │
            │       │       └── 依赖 Models
            │       └── 依赖 Core + Models
            └── 依赖 Core + API
```

**严格禁止**：
- CLI 层直接调用 DB 层
- Core 层直接依赖 API 层的 schema
- Models 层依赖任何其他层

### 2.3 文件命名约定

| 类型 | 命名 | 示例 |
|------|------|------|
| 源文件 | `snake_case.py` | `process_manager.py` |
| 测试文件 | `test_<module>.py` | `test_process_manager.py` |
| TypeScript 组件 | `PascalCase.tsx` | `ServerCard.tsx` |
| Pydantic Schema | `PascalCase` | `ServerCreate, ServerResponse` |
| 内部函数 | `snake_case` | `_spawn_process()` |
| 常量 | `UPPER_CASE` | `DEFAULT_HEALTH_INTERVAL` |

---

## 三、开发规范

### 3.1 Python 代码风格

```bash
# 统一使用 Ruff 检查
uv run ruff check src/
uv run ruff format --check src/

# 类型检查
uv run mypy src/

# 一键修复
uv run ruff check --fix src/
```

**核心规则**（`pyproject.toml`）：

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "ARG", "C4", "T20"]

[tool.mypy]
strict = true
python_version = "3.10"
disallow_untyped_defs = true
disallow_any_unimported = false
warn_unused_ignores = true
```

### 3.2 类型标注规范

```python
# ✅ 正确：所有函数必须有类型标注
def search_servers(
    query: str,
    category: str | None = None,
    sort_by: SortBy = SortBy.HOT,
    limit: int = 20,
) -> list[ServerInfo]:
    ...

# ✅ 正确：使用 typed dict 代替 dict
class ServerInfo(TypedDict):
    name: str
    version: str
    description: str
    rating: float
    download_count: int

# ❌ 禁止：裸 dict / Any / 未标注
def search(query):          # ❌ 返回类型缺失
    return db.query(...)

# ❌ 禁止：使用 Any 逃避类型检查
def get_config(key: str) -> Any:  # ❌ 应使用具体类型
    ...
```

### 3.3 错误处理规范

```python
# ✅ 使用自定义异常体系
class McpHubError(Exception):
    """基类异常"""
    def __init__(self, message: str, code: str, details: dict | None = None):
        self.code = code
        self.details = details
        super().__init__(message)

class ServerNotFoundError(McpHubError):
    def __init__(self, server_id: str):
        super().__init__(
            message=f"Server '{server_id}' 未找到",
            code="SERVER_NOT_FOUND",
            details={"server_id": server_id}
        )

class InstallError(McpHubError):
    def __init__(self, server_id: str, reason: str):
        super().__init__(
            message=f"安装 {server_id} 失败: {reason}",
            code="INSTALL_FAILED",
            details={"server_id": server_id, "reason": reason}
        )

# ✅ 统一处理
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(McpHubError)
async def mcp_hub_error_handler(request: Request, exc: McpHubError):
    return JSONResponse(
        status_code=400 if "NOT_FOUND" not in exc.code else 404,
        content={
            "error": exc.code,
            "message": str(exc),
            "details": exc.details,
        }
    )

# ❌ 禁止：裸 raise Exception / 捕获全部异常
try:
    ...
except Exception:  # ❌ 应捕获具体异常类型
    pass
```

### 3.4 日志规范

```python
import structlog

logger = structlog.get_logger()

# ✅ 结构化日志（JSON 格式，便于日志系统分析）
logger.info("server.installed",
    server_id="@anthropic/web-search",
    version="2.1.0",
    duration_ms=1234,
)

logger.error("server.crash",
    server_id="@community/db-query",
    error="Connection timeout after 30s",
    restart_count=3,
    pid=12345,
)

# ❌ 禁止：f-string 拼凑日志
logger.info(f"Server {server_id} installed")  # ❌ 无法被日志系统索引
```

### 3.5 异步规范

```python
# ✅ 使用 async/await + asyncio
async def install_server(server_id: str) -> InstallResult:
    async with async_timeout.timeout(120):
        meta = await registry.fetch_metadata(server_id)
        result = await installer.install(meta)
        return result

# ✅ 长时间运行的任务使用 asyncio.create_task
async def start_health_monitor():
    """后台健康检查循环"""
    while True:
        results = await health_check.run_all()
        for server_id, status in results.items():
            if status == HealthStatus.ERROR:
                await auto_restart(server_id)
        await asyncio.sleep(5)  # 每 5 秒检查一次

# ❌ 禁止：在异步函数中调用同步阻塞操作
async def get_server_info(server_id: str) -> ServerInfo:
    time.sleep(1)  # ❌ 应使用 asyncio.sleep()
    data = requests.get(...)  # ❌ 应使用 httpx.AsyncClient
```

---

## 四、核心模块实现指南

### 4.1 注册中心（registry.py）—— 核心数据结构

```python
"""MCP Server 注册与索引管理。"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SecurityLevel = Literal["verified", "reviewed", "unreviewed", "blocked"]
ServerStatus = Literal["not_installed", "running", "stopped", "error"]
InstallType = Literal["pip", "npm", "uvx", "docker"]


@dataclass
class InstallConfig:
    type: InstallType
    package: str
    command: str
    auto_config: bool = True


@dataclass
class SecurityInfo:
    level: SecurityLevel = "unreviewed"
    last_audit: str | None = None
    network_access: bool = False
    file_access: bool = False


@dataclass
class ServerMeta:
    """Server 元数据 —— 核心数据结构，贯穿全系统。"""

    name: str                         # @org/server-name
    version: str                      # semver
    description: str
    author: str
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    install: InstallConfig | None = None
    dependencies: dict[str, str] = field(default_factory=dict)
    security: SecurityInfo = field(default_factory=SecurityInfo)
    rating: float = 0.0
    review_count: int = 0
    download_count: int = 0
    homepage: str = ""
    license: str = "MIT"
    status: ServerStatus = "not_installed"

    @property
    def display_name(self) -> str:
        return self.name.split("/")[-1]

    @property
    def is_official(self) -> bool:
        return self.author in {"anthropic", "openai", "google"}
```

### 4.2 进程管理器（process_manager.py）——关键逻辑

```python
"""子进程生命周期管理 —— 最核心也最容易出错的部分。"""

from __future__ import annotations

import asyncio
import os
import signal
import psutil
from dataclasses import dataclass, field


@dataclass
class ManagedProcess:
    server_id: str
    pid: int | None = None
    process: asyncio.subprocess.Process | None = None
    started_at: float | None = None
    restart_count: int = 0
    log_buffer: list[str] = field(default_factory=list)


class ProcessManager:
    """
    进程管理器职责：
    1. 启动 Server 子进程（隔离环境）
    2. 监控进程状态
    3. 优雅关闭（SIGTERM → 等待 → SIGKILL）
    4. 自动重启（最多 3 次）
    """

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self._processes: dict[str, ManagedProcess] = {}
        self._lock = asyncio.Lock()

    async def spawn(
        self,
        server_id: str,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> ManagedProcess:
        """
        启动 Server 子进程。

        实现要点：
        - 每个 Server 在独立子进程中运行
        - 通过 asyncio.create_subprocess_exec 启动
        - 标准输出重定向到日志文件
        - 设置进程组以便关闭时杀掉整个进程树
        """
        async with self._lock:
            if server_id in self._processes:
                proc = self._processes[server_id]
                if proc.process and proc.process.returncode is None:
                    raise RuntimeError(f"Server {server_id} 已在运行")

            log_file = self.log_dir / f"{server_id.replace('/', '_')}.log"
            log_fd = open(log_file, "a")

            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdout=log_fd,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, **(env or {})},
                cwd=str(cwd) if cwd else None,
                preexec_fn=os.setsid,  # 创建新进程组
            )

            managed = ManagedProcess(
                server_id=server_id,
                pid=process.pid,
                process=process,
                started_at=asyncio.get_event_loop().time(),
                restart_count=0,
            )
            self._processes[server_id] = managed
            return managed

    async def graceful_shutdown(self, server_id: str, timeout: float = 5.0) -> None:
        """
        优雅关闭流程：
        1. 发送 SIGTERM（允许进程清理）
        2. 等待 timeout 秒
        3. 如果还在运行，发送 SIGKILL
        """
        proc = self._processes.get(server_id)
        if not proc or not proc.process:
            return

        pid = proc.process.pid
        if pid is None:
            return

        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            # 先发 SIGTERM 给整个进程组
            os.killpg(os.getpgid(pid), signal.SIGTERM)

            # 等待超时
            try:
                await asyncio.wait_for(proc.process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                # 超时后强制杀
                for child in children:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
        except psutil.NoSuchProcess:
            pass
        finally:
            self._processes.pop(server_id, None)
```

### 4.3 健康检查（health_check.py）

```python
"""三级健康检查引擎。"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass


@dataclass
class HealthResult:
    server_id: str
    level: int  # 1, 2, 3
    passed: bool
    response_time_ms: int
    message: str = ""


class HealthChecker:
    """
    三级检查策略：
    L1 (每 5 秒): 进程是否存活（kill -0）
    L2 (每 30 秒): stdio/SSE 连接是否正常
    L3 (每 5 分钟): 调用一个简单 tool 确认功能正常
    """

    def __init__(self):
        self._checkers: dict[int, list[asyncio.Task]] = {
            1: [],
            2: [],
            3: [],
        }

    async def check_l1(self, server_id: str, pid: int) -> HealthResult:
        """进程级检查 — 最轻量，只查进程是否存在。"""
        start = asyncio.get_event_loop().time()
        try:
            os.kill(pid, 0)  # 不发送信号，只检查进程存在
            passed = True
            msg = "进程存活"
        except OSError:
            passed = False
            msg = "进程不存在"
        elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
        return HealthResult(server_id, 1, passed, elapsed, msg)

    async def check_l2(
        self, server_id: str, stdin, timeout: float = 5.0
    ) -> HealthResult:
        """
        连接级检查 — 尝试建立 JSON-RPC 连接。

        MCP 使用 JSON-RPC 2.0 协议：
        → 发送 {"jsonrpc":"2.0","id":1,"method":"ping"}
        ← 期望 {"jsonrpc":"2.0","id":1,"result":{}}
        """
        start = asyncio.get_event_loop().time()
        try:
            async with asyncio.timeout(timeout):
                # 发送 ping 请求
                stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
                await stdin.drain()
                # 检查是否写入成功
                passed = True
                msg = "连接正常"
        except asyncio.TimeoutError:
            passed = False
            msg = "连接超时"
        elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
        return HealthResult(server_id, 2, passed, elapsed, msg)
```

### 4.4 安装器（installer.py）

```python
"""MCP Server 安装执行器。"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Literal

from mcp_hub.models.server import ServerMeta


class Installer:
    """
    安装执行器职责：
    1. 按 install_type 选择安装方式
    2. 执行安装命令
    3. 自动写入 mcp.json 配置
    4. 处理安装错误和回滚
    """

    SUPPORTED_TYPES: set[Literal["pip", "npm", "uvx"]] = {"pip", "npm", "uvx"}

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir

    async def install(self, meta: ServerMeta) -> dict:
        """安装 Server，返回安装结果。"""
        if meta.install.type not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"不支持的安装类型: {meta.install.type}，"
                f"当前仅支持: {', '.join(self.SUPPORTED_TYPES)}"
            )

        # Step 1: 执行安装
        result = await self._execute_install(meta)
        if not result["success"]:
            return result

        # Step 2: 自动配置
        config_written = await self._write_config(meta)

        return {
            "success": True,
            "server_id": meta.name,
            "version": meta.version,
            "config_written": config_written,
            "install_command": meta.install.command,
            "detail": result.get("detail", ""),
        }

    async def _execute_install(self, meta: ServerMeta) -> dict:
        """执行安装命令。"""
        try:
            proc = await asyncio.create_subprocess_exec(
                *meta.install.command.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )
            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": f"安装失败 (code={proc.returncode}): {stderr.decode()[:500]}",
                }
            return {"success": True, "detail": stdout.decode()[:200]}
        except asyncio.TimeoutError:
            return {"success": False, "error": "安装超时（超过 120 秒）"}
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"命令未找到: {meta.install.command}",
            }

    async def _write_config(self, meta: ServerMeta) -> bool:
        """自动写入 claude_desktop_config.json 或 mcp.json。"""
        config_path = self._find_config_path()
        if not config_path:
            return False

        config: dict = {}
        if config_path.exists():
            config = json.loads(config_path.read_text())

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        config["mcpServers"][meta.display_name] = {
            "command": meta.install.command.split()[0],
            "args": meta.install.command.split()[1:],
        }

        config_path.write_text(json.dumps(config, indent=2))
        return True
```

---

## 五、API 开发规范

### 5.1 FastAPI 路由风格

```python
# ✅ 正确：路径参数 + 查询参数 + 请求体分离清晰
@router.get("/api/v1/market/search", response_model=SearchResponse)
async def search_servers(
    q: str = Query("", description="搜索关键词"),
    category: str | None = Query(None, description="分类筛选"),
    sort: SortBy = Query(SortBy.HOT, description="排序方式"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    ...

# ✅ 正确：路径参数直接传入
@router.get("/api/v1/servers/{server_id}/status")
async def get_server_status(server_id: str = Path(..., description="Server ID")):
    ...

# ✅ 正确：PATCH 用于部分更新
@router.patch("/api/v1/servers/{server_id}/config")
async def update_server_config(
    server_id: str,
    config: ConfigUpdate = Body(..., description="要更新的配置项"),
):
    ...
```

### 5.2 响应格式统一

```python
# ✅ 成功响应
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 142
  }
}

# ✅ 错误响应
{
  "success": false,
  "error": {
    "code": "SERVER_NOT_FOUND",
    "message": "Server '@example/xxx' 未找到",
    "details": { "server_id": "@example/xxx" }
  }
}

# ✅ Pydantic Schema 定义
from pydantic import BaseModel

class ApiResponse(BaseModel):
    success: bool = True

class ApiDataResponse(ApiResponse):
    data: dict | list

class ApiErrorResponse(ApiResponse):
    success: bool = False
    error: ErrorDetail

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None
```

### 5.3 数据库操作

```python
# ✅ 使用 Context Manager 管理连接
from contextlib import contextmanager

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 启用 WAL 模式
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ✅ 查询封装
class ServerRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def search(self, query: str, category: str | None, limit: int = 20) -> list[dict]:
        sql = "SELECT * FROM servers WHERE (name LIKE ? OR description LIKE ?)"
        params = [f"%{query}%", f"%{query}%"]

        if category:
            sql += " AND categories LIKE ?"
            params.append(f"%{category}%")

        sql += " ORDER BY download_count DESC LIMIT ?"
        params.append(limit)

        return [dict(row) for row in self.db.execute(sql, params).fetchall()]

    def get_by_id(self, server_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM servers WHERE id = ?", (server_id,)
        ).fetchone()
        return dict(row) if row else None
```

---

## 六、测试规范

### 6.1 测试结构

```
tests/
├── __init__.py
├── conftest.py               # 全局 fixture（数据库、cli runner、async client）
├── fixtures/
│   ├── server_meta.json      # 测试用 Server 元数据
│   └── seed_data.json        # 预置测试数据
│
├── unit/                      # 单元测试 —— 不需要外部依赖
│   ├── test_registry.py
│   ├── test_health_check.py
│   └── test_installer.py
│
├── integration/               # 集成测试 —— 需要数据库或文件系统
│   ├── test_process_manager.py
│   ├── test_security_scanner.py
│   └── test_event_bus.py
│
├── api/                       # API 测试 —— 需要 FastAPI TestClient
│   ├── test_market_api.py
│   ├── test_manage_api.py
│   └── test_publish_api.py
│
└── cli/                       # CLI 测试 —— 需要 Click CliRunner
    ├── test_search.py
    ├── test_install.py
    └── test_manage.py
```

### 6.2 Fixture 示例

```python
# conftest.py
from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from click.testing import CliRunner
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

from mcp_hub.main import create_app
from mcp_hub.db.database import get_db, init_db


@pytest.fixture
def temp_dir():
    """临时目录，每次测试自动清理。"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def cli_runner():
    """Click CLI 测试工具。"""
    return CliRunner()


@pytest.fixture
async def async_client(temp_dir: Path):
    """FastAPI 异步测试客户端。"""
    # 使用临时数据库
    db_path = temp_dir / "test.db"

    app = create_app(db_path=str(db_path))

    transport = ASGITransport(app=app)
    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def seed_data():
    """预置测试数据。"""
    return [
        {
            "id": "@anthropic/web-search",
            "name": "web-search",
            "description": "搜索网页",
            "author": "anthropic",
            "categories": json.dumps(["browser"]),
            "rating": 4.8,
            "download_count": 12000,
        },
        {
            "id": "@community/sql-query",
            "name": "sql-query",
            "description": "数据库查询",
            "author": "community",
            "categories": json.dumps(["database"]),
            "rating": 4.2,
            "download_count": 8000,
        },
    ]
```

### 6.3 测试写法的坑与规范

```python
# ✅ 正确：测试一个函数/模块，不是测试整个系统
async def test_registry_search_by_keyword(registry, seed_data):
    """搜索应能按关键词匹配 Server 名称和描述。"""
    await registry.load(seed_data)

    results = await registry.search("web")

    assert len(results) >= 1
    assert results[0]["id"] == "@anthropic/web-search"


# ✅ 正确：测试边界条件
async def test_registry_search_empty_query(registry, seed_data):
    """空搜索应返回所有结果（按热度排序）。"""
    await registry.load(seed_data)
    results = await registry.search("")
    assert len(results) == len(seed_data)


# ✅ 正确：测试错误路径
async def test_install_invalid_type(installer, server_meta):
    """不支持的安装类型应抛出明确的错误。"""
    server_meta["install"]["type"] = "brew"  # 不支持的类型

    with pytest.raises(ValueError, match="不支持.*brew"):
        await installer.install(server_meta)


# ✅ 正确：API 集成测试
async def test_market_search_api(async_client, seed_data):
    """搜索 API 应返回结构化的响应。"""
    response = await async_client.get(
        "/api/v1/market/search",
        params={"q": "web", "category": "browser"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1
    assert data["meta"]["total"] >= 1


# ❌ 避免：测试实现细节而非行为
def test_registry_internal_cache():
    """❌ 不要测试私有方法/内部实现。"""
    ...


# ❌ 避免：过于耦合的断言
def test_search_results():
    """❌ 不要断言排序的具体值，应断言排序的规则。"""
    ...


# ❌ 避免：需要网络的外部依赖
async def test_install_real_server():
    """❌ 不要在单元/集成测试中安装真实的 Server。
       需要使用 mock 模拟安装过程。"""
    ...
```

### 6.4 运行测试

```bash
# 运行全部测试
uv run pytest

# 运行特定分类
uv run pytest tests/unit/
uv run pytest tests/api/
uv run pytest tests/cli/

# 运行带覆盖率的测试
uv run pytest --cov=src/mcp_hub --cov-report=html

# 并行运行
uv run pytest -n auto

# 快速失败（开发时）
uv run pytest -x --maxfail=1
```

### 6.5 测试覆盖率目标

| 模块 | 目标覆盖率 | 说明 |
|------|-----------|------|
| `core/*` | ≥ 95% | 核心逻辑，最关键 |
| `api/*` | ≥ 90% | 接口层 |
| `cli/*` | ≥ 85% | CLI 命令 |
| `db/*` | ≥ 85% | 数据访问 |
| `models/*` | 100% | 数据结构简单 |

---

## 七、Git 工作流

### 7.1 分支策略

```
main             生产就绪代码
  └─ develop     开发主线
       ├─ feature/market-search       市场搜索功能
       ├─ feature/installer           安装引擎
       ├─ feature/process-manager     进程管理
       ├─ feature/web-dashboard       Web 界面
       └─ fix/xxx                     修复
```

### 7.2 提交规范

```bash
# 格式: <type>(<scope>): <description>

feat(core): 实现三级健康检查引擎
feat(cli): 添加 mcp search 命令
feat(api): 添加市场搜索 API 端点
feat(web): 实现 Server 详情页

fix(installer): 修复 pip 安装后配置写入失败
fix(process): 修复 daemon 模式下的 SIGTERM 处理

refactor(registry): 提取搜索排序逻辑为独立函数

test(health): 添加 L1/L2/L3 健康检查测试

docs: 更新 README 安装说明

chore: 更新依赖到最新版本
```

### 7.3 提交前检查

```bash
# 每次提交前执行
uv run ruff check src/           # 代码风格
uv run mypy src/                 # 类型检查
uv run pytest                    # 运行测试
```

在项目根目录添加 pre-commit hook：

```bash
# .hooks/pre-commit
#!/bin/bash
set -e

echo "🔍 Running Ruff..."
uv run ruff check src/

echo "🔍 Running mypy..."
uv run mypy src/

echo "🔍 Running pytest..."
uv run pytest -x --tb=short

echo "✅ All checks passed!"
```

---

## 八、构建与发布

### 8.1 构建 Python 包

```toml
# pyproject.toml
[project]
name = "mcp-hub"
version = "0.1.0"
description = "MCP Server 的一站式管理平台"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "fastapi>=0.110",
    "uvicorn[standard]",
    "httpx>=0.27",
    "psutil>=5.9",
    "pydantic>=2.0",
    "structlog>=24.0",
    "typer>=0.12",
]

[project.scripts]
mcp = "mcp_hub.cli.app:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```bash
# 构建
uv build

# 本地安装测试
uv pip install dist/mcp_hub-0.1.0-py3-none-any.whl

# 发布到 PyPI（后续）
uv publish
```

### 8.2 构建 Web Dashboard

```bash
cd src/mcp_hub/web

# 构建生产版本
npm run build

# 构建产物输出到 web/static/
# FastAPI 自动从 static/ 目录服务静态文件
```

### 8.3 Docker 镜像

```dockerfile
# Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir .

COPY src/ src/
RUN pip install .

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app/src/mcp_hub/web/static /app/static

EXPOSE 3987
CMD ["mcp", "daemon", "start", "--host", "0.0.0.0", "--port", "3987"]
```

---

## 九、开发注意事项（踩坑指南）

### 9.1 进程管理

```python
# ⚠️ Windows 兼容性
# asyncio.create_subprocess_exec 在 Windows 上行为不同
# preexec_fn (setsid) 在 Windows 上不支持

import sys

if sys.platform == "win32":
    # Windows 上使用 CREATE_NEW_PROCESS_GROUP
    process = await asyncio.create_subprocess_exec(
        command, *args,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
else:
    # Unix 上使用 preexec_fn
    process = await asyncio.create_subprocess_exec(
        command, *args,
        preexec_fn=os.setsid,
    )
```

### 9.2 数据库并发

```python
# ⚠️ SQLite 并发写入
# SQLite 默认只允许一个写入者，多个写入会报 "database is locked"

# 解决方法 1: WAL 模式（推荐）
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")  # 等待 5 秒而不是立即报错

# 解决方法 2: 使用连接池
# 生产环境建议迁移到 PostgreSQL
```

### 9.3 跨平台路径

```python
# ⚠️ 不要硬编码路径分隔符
config_path = os.path.expanduser("~/.config/mcp-hub/servers.db")  # ✅
config_path = "C:\\Users\\xxx\\.config\\mcp-hub\\servers.db"       # ❌

# 使用 pathlib
from pathlib import Path
config_dir = Path.home() / ".config" / "mcp-hub"                 # ✅
```

### 9.4 JSON-RPC 通信

```python
# ⚠️ MCP 协议使用换行分隔的 JSON
# 每条 JSON-RPC 消息必须以 \n 结尾
# 不能发送多个 \n，不能发送不带 \n 的消息

# 发送
stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "ping", "arguments": {}}
}) + "\n")

# 接收（逐行读取）
line = await stdout.readline()
response = json.loads(line)
```

---

## 十、本地开发速查

### 启动开发环境

```bash
# 一键启动（开发模式）
uv run mcp daemon start --dev

# 启动 + 热重载
uv run uvicorn mcp_hub.api.app:app --reload --port 3987
# 在另一个终端启动 CLI（无守护进程模式）
uv run mcp search --api http://localhost:3987
```

### 常用命令

```bash
# 代码检查
uv run ruff check src/             # Lint
uv run ruff format --check src/    # 格式检查
uv run mypy src/                   # 类型检查

# 测试
uv run pytest -x --tb=short        # 快速测试
uv run pytest --cov=src/mcp_hub    # 覆盖度

# 数据库
uv run python -m mcp_hub.db.migrations   # 迁移
uv run python -m mcp_hub.db.seed         # 导入数据

# 构建
uv build                               # Python 包
cd src/mcp_hub/web && npm run build     # Web Dashboard
```

### Git 工作流

```bash
# 开始新功能
git checkout -b feature/market-search develop

# 开发完成后
uv run ruff check src/ && uv run mypy src/ && uv run pytest -x
git add -A
git commit -m "feat(market): 实现市场搜索功能"

# 合并回 develop
git checkout develop
git merge feature/market-search
```

---

<p align="center">
  <sub>2026 年 6 月 · MCP Server Hub 开发文档 · 面向生产环境</sub>
</p>
