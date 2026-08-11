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

## 接入现有 Hub

必须由用户提供：

- Hub URL
- Agent 类型
- 监控页生成的一次性设备令牌

先验证：

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

## 安全规则

- 不输出、记录或提交设备令牌、API Key、环境变量值或请求头值。
- 不覆盖 Agent 配置；必须保留 CLI 创建的备份。
- 不把“加入追踪”描述为安装或启动本地进程。
- 不声称 Agent 直连 Server 的调用会被监控。
- 不执行 `mcp-hub install/start/stop`，除非用户明确说明这是可信自托管 Hub，且已启用进程管理。
- 不使用本文之外的旧版 `mcp`、npx 或 PyPI 安装命令。

完整人工安装与排障见 [install.md](install.md)。
