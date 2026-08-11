# MCP Server Hub AI Agent 安装说明

本文供 AI Agent 执行。目标是安装 CLI 或接入用户指定的 Hub，不得自行创建凭证、猜测服务器地址或启用自托管进程管理。

## 安装 CLI

当前 `0.2.0` 尚未发布到 PyPI。不要执行 `pip install mcp-hub-cli==0.2.0`，使用：

```bash
uv tool install --force "git+https://github.com/blankbrains/McpServerHub.git@main"
uv tool update-shell
mcp-hub --version
```

如果 `uv` 未安装，先让用户确认后按照 uv 官方安装方式安装。安装完成后可能需要重开终端。

安装命令只影响用户电脑上的 CLI 和本地 Gateway，不会修改远程 Hub、GitHub 仓库或项目源码。不要把“在 D 盘目录执行命令”解释为“安装到 D 盘”；uv 的工具位置由环境变量决定。

用户明确要求 Windows 安装到 D 盘时，应先展示并获得确认，再设置：

```powershell
[Environment]::SetEnvironmentVariable("UV_TOOL_DIR", "D:\uv\tools", "User")
[Environment]::SetEnvironmentVariable("UV_TOOL_BIN_DIR", "D:\uv\bin", "User")
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\uv\cache", "User")
[Environment]::SetEnvironmentVariable("UV_PYTHON_INSTALL_DIR", "D:\uv\python", "User")
```

重开终端后再执行安装命令，并使用 `uv tool dir`、`uv tool dir --bin`、`uv python dir` 和 `where.exe mcp-hub` 验证。已有安装不会被环境变量自动搬迁。

只有用户明确要求卸载时才执行：

```powershell
uv tool list --show-paths
uv tool uninstall mcp-hub-cli
```

使用自定义安装目录时，卸载进程必须看到相同的 `UV_TOOL_DIR` 和 `UV_TOOL_BIN_DIR`。卸载 CLI 不等于删除 uv，也不会自动恢复 Agent 的 MCP 配置；不得直接删除整个 uv 目录。

## 接入现有 Hub

必须由用户提供：

- Hub URL
- Agent 类型
- 监控页生成的一次性设备令牌

接入前先验证 Hub 网络和本地基础配置：

```bash
curl "<Hub URL>/api/v1/health"
mcp-hub agent doctor --agent <agent>
```

再执行监控页生成的完整命令，例如：

```bash
mcp-hub agent setup \
  --agent codex \
  --hub-url <Hub URL> \
  --telemetry-token <设备令牌>
```

执行前必须展示迁移预览并获得用户确认。完成后提醒用户完全重启 Agent，并实际调用一次 MCP 工具。

接入后必须运行端到端验证：

```bash
mcp-hub agent verify --agent <agent>
```

自动化读取结果时使用 `--json`，根据 `checks[].code` 区分网络、令牌、撤销、Gateway 心跳、首次调用和队列问题。默认验证只读。只有用户明确同意预览后才可执行 `--fix`；非交互执行必须使用 `--fix --yes`。任何 Agent 配置写入都必须先生成备份，不得自动创建新设备令牌或修复无法确认归属的配置。

## 安全规则

- 不输出、记录或提交设备令牌、API Key、环境变量值或请求头值。
- 不覆盖 Agent 配置；必须保留 CLI 创建的备份。
- 网络不可达时不得声称设备令牌无效。
- 不把“加入追踪”描述为安装或启动本地进程。
- 不声称 Agent 直连 Server 的调用会被监控。
- 不执行 `mcp-hub install/start/stop`，除非用户明确说明这是可信自托管 Hub，且已启用进程管理。
- 不使用本文之外的旧版 `mcp`、npx 或 PyPI 安装命令。

完整人工安装与排障见 [install.md](install.md)。
