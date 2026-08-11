# MCP Server Hub 安装与部署指南

本文集中维护 CLI 安装、本地 Gateway 接入、本机 Quickstart、Docker 和生产部署流程。产品概览见仓库根目录的 [README](../README.md)。

## 1. 安装 CLI

当前 `0.2.0` 尚未发布到 PyPI，请从 GitHub 安装。

### 安装 uv

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS / Linux：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 安装 mcp-hub

```bash
uv tool install --force "git+https://github.com/blankbrains/McpServerHub.git@main"
uv tool update-shell
```

重开终端后验证：

```bash
mcp-hub --version
mcp-hub --help
```

`mcp-hub` 必须位于 Agent 进程可见的 `PATH` 中，因为接入后 Agent 会通过 `mcp-hub serve` 启动本地 Gateway。

`uv tool install` 只在当前电脑安装 CLI 和本地 Gateway，不会修改远程 Hub、GitHub 仓库或项目源码。命令在哪个工作目录或磁盘中执行，也不会决定工具的安装位置。

### Windows 安装到 D 盘

如需把 mcp-hub 工具环境、命令入口、缓存和 uv 管理的 Python 放到 D 盘，请先在 PowerShell 中保存用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable("UV_TOOL_DIR", "D:\uv\tools", "User")
[Environment]::SetEnvironmentVariable("UV_TOOL_BIN_DIR", "D:\uv\bin", "User")
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\uv\cache", "User")
[Environment]::SetEnvironmentVariable("UV_PYTHON_INSTALL_DIR", "D:\uv\python", "User")
```

关闭并重新打开终端，再安装和检查路径：

```powershell
uv tool install --force "git+https://github.com/blankbrains/McpServerHub.git@main"
uv tool update-shell

uv tool dir
uv tool dir --bin
uv python dir
where.exe mcp-hub
mcp-hub --version
```

预期主要目录为：

- 工具环境：`D:\uv\tools`
- 命令入口：`D:\uv\bin`
- 下载缓存：`D:\uv\cache`
- uv 管理的 Python：`D:\uv\python`

仅切换到 `D:\` 再执行安装命令不会产生以上效果。环境变量也不会自动搬迁已有安装；已经安装在默认目录时，应先用原目录配置卸载，再切换目录重新安装。uv 可执行文件本身可能仍位于原安装目录，但 mcp-hub 及其主要依赖会存放在上述 D 盘目录。

### 卸载 mcp-hub

先查看 uv 当前识别的安装及路径：

```powershell
uv tool list --show-paths
```

然后卸载 Python 包名 `mcp-hub-cli`：

```powershell
uv tool uninstall mcp-hub-cli
where.exe mcp-hub
```

如果安装时使用了自定义 `UV_TOOL_DIR` 和 `UV_TOOL_BIN_DIR`，卸载时必须继续使用相同设置，否则 uv 会查找默认目录。该命令会删除 mcp-hub 的独立工具环境和命令入口，但不会卸载 uv、清理所有 uv 公共缓存，也不会自动恢复已经写入 Codex、Claude Desktop 等 Agent 的 MCP 配置。不要直接删除整个 `D:\uv`，其中可能还有其他 uv 工具。

## 2. 使用远程 Hub 监控本地 MCP

### 检查网络

Windows PowerShell：

```powershell
$HubUrl = "http://<Hub地址>:3987"
Invoke-RestMethod "$HubUrl/api/v1/health"
```

macOS / Linux：

```bash
export HUB_URL="http://<Hub地址>:3987"
curl "$HUB_URL/api/v1/health"
```

响应中的 `status` 应为 `healthy`。无法访问时先检查服务器地址、VPN、局域网、防火墙和端口。

### 确认 Agent 已有 MCP Server

`agent setup` 迁移现有连接，不创建第一个 MCP Server。目标 Agent 至少要有一个可正常使用的 stdio、Streamable HTTP 或 SSE Server。

| Agent | 常见配置路径 |
|------|-------------|
| Codex | `~/.codex/config.toml` |
| Claude Code | `~/.claude.json`、`~/.claude/mcp.json`、项目 `.mcp.json` |
| Claude Desktop | `Claude/claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| VS Code Copilot | 项目 `.vscode/mcp.json` |
| Trae | `~/.trae/mcp.json` |

网页上传目前只解析根节点为 `mcpServers` 的 JSON。Codex TOML、根节点为 `servers` 的 JSON 以及复杂多 Agent 配置应使用 CLI 迁移。

### 创建设备并接入

1. 在 Hub 网页完成 GitHub 登录。
2. 打开“监控”页面。
3. 为实际使用的 Agent 创建设备。
4. 复制页面显示的一次性接入命令。

示例：

```bash
mcp-hub agent setup \
  --agent codex \
  --hub-url http://<Hub地址>:3987 \
  --telemetry-token mcpht_<设备令牌>
```

CLI 会在确认后：

1. 备份原 Agent 配置。
2. 将完整本地连接写入 Agent 独立的 `gateway.json`。
3. 使用 `mcp-hub serve` 替换可安全迁移的直接连接。
4. 保留无法迁移的条目，不静默删除。
5. 上报脱敏清单和运行指标。

设备令牌只显示一次。不要截图、提交到 Git、写入公开文档或发送给他人；泄露后应立即撤销并重新创建。

### 重启和验证

完全退出 Agent 的所有进程后重新打开，然后实际调用一次 MCP 工具。只打开工具列表或普通对话不会产生 `tool_call` 数据。

检查：

- 设备最后在线时间更新。
- Server 调用数增加。
- 延迟、成功率、错误分类或估算 Token 出现数据。
- Agent 配置中没有同名直接连接绕过 Gateway。

诊断：

```bash
mcp-hub agent status --agent codex
mcp-hub agent doctor --agent codex
```

更新网页追踪列表后同步：

```bash
mcp-hub config sync --agent codex --server http://<Hub地址>:3987
```

同步只更新 `gateway.json`，写入前会确认并备份，保留本地环境变量、请求头和工作目录。同步完成后需要重启 Agent。

## 3. 本机 Quickstart

Quickstart 需要前端构建产物。请从源码构建后安装本地包：

```bash
git clone https://github.com/blankbrains/McpServerHub.git
cd McpServerHub

cd src/mcp_hub/web
npm ci
npm run build
cd ../../..

uv tool install --force .
mcp-hub quickstart
# http://localhost:3987
```

Quickstart 使用 SQLite，并将配置保存在 `~/.config/mcp-hub/.env`。它只监听 `127.0.0.1`，适合个人本机验证。

直接通过 `uv tool install "git+https://..."` 安装时，Git 仓库中未跟踪的 `web/static` 不会进入安装包；这种安装适合连接已有 Hub，不用于启动完整 Web 界面。

默认生成的 GitHub OAuth 值是占位值，只能浏览公开页面。需要登录时，在 Quickstart 配置中设置真实的：

```text
MCP_HUB_GITHUB_CLIENT_ID
MCP_HUB_GITHUB_CLIENT_SECRET
MCP_HUB_GITHUB_REDIRECT_URI
```

## 4. Docker 部署

```bash
git clone https://github.com/blankbrains/McpServerHub.git
cd McpServerHub
cp .env.example .env
```

在 `.env` 中至少配置：

```text
POSTGRES_PASSWORD
MCP_HUB_SECRET
MCP_HUB_GITHUB_CLIENT_ID
MCP_HUB_GITHUB_CLIENT_SECRET
MCP_HUB_GITHUB_REDIRECT_URI
```

启动：

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:3987/api/v1/health
```

不要提交 `.env`。公开部署时，OAuth 回调地址和 CORS Origin 必须与实际域名一致。

## 5. systemd 生产部署

仓库提供：

- `deploy/mcp-hub.service`
- `deploy/mcp-hub.env.example`

这些文件是模板。部署前必须根据服务器实际用户、仓库路径和 Python 环境调整 `User`、`Group`、`WorkingDirectory`、`Environment` 与 `ExecStart`。

建议流程：

```bash
sudo install -d -m 0750 /etc/mcp-hub
sudo install -m 0600 deploy/mcp-hub.env.example /etc/mcp-hub/mcp-hub.env
sudo install -m 0644 deploy/mcp-hub.service /etc/systemd/system/mcp-hub.service
```

填写 `/etc/mcp-hub/mcp-hub.env` 后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-hub
sudo systemctl status mcp-hub
sudo journalctl -u mcp-hub -n 100 --no-pager
curl http://localhost:3987/api/v1/health
```

真实凭证只保存在服务器本地环境文件中，权限应为 `0600`。不要把密码、Token、服务器地址或回滚说明提交到仓库。

## 6. 自托管进程管理

中心 Hub 默认只管理市场、配置和遥测。只有可信自托管环境需要集中运行 MCP Server 时，才设置：

```text
MCP_HUB_ALLOW_SERVER_PROCESS_MANAGEMENT=true
```

启用后管理员可使用：

```bash
mcp-hub install <server-id>
mcp-hub start <server-id>
mcp-hub stop <server-id>
mcp-hub status
mcp-hub logs <server-id> -f
```

普通用户的个人追踪、Gateway 状态和本机进程不是同一套状态，不应混用。

## 7. 发布检查

更新服务后至少验证：

```bash
curl http://localhost:3987/api/v1/health
```

并检查：

1. 进程或容器持续运行。
2. 日志没有迁移、认证或数据库错误。
3. 市场和公开页面可访问。
4. 受保护 API 匿名访问被拒绝。
5. 原问题无法复现。

保留上一个可运行提交、镜像或 release 目录作为回滚点，不要使用会覆盖未提交数据的破坏性 Git 操作。
