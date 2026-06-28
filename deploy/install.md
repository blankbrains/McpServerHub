# 🔵 MCP Hub 安装指南

> 一行命令安装 MCP Hub，然后直接安装你需要的 MCP Server。

## 快速安装

### 方法一：一键脚本（推荐）

```bash
# 仅安装 MCP Hub
curl -fsSL https://mcphub.cn/install.sh | bash

# 安装 MCP Hub + 指定 Server
curl -fsSL https://mcphub.cn/install.sh | bash -s -- @modelcontextprotocol/server-filesystem
```

### 方法二：pip 安装

```bash
# 安装 CLI
pip install mcp-hub

# 搜索可用的 MCP Server
mcp search

# 安装你需要的
mcp install @modelcontextprotocol/server-filesystem

# 查看配置（复制到本地 Agent）
mcp info @modelcontextprotocol/server-filesystem --config
```

### 方法三：npx 零安装（无需安装任何东西）

```bash
# 用 npx 直接运行 MCP Hub
npx -y mcp-hub search

# 生成配置
npx -y mcp-hub info @modelcontextprotocol/server-filesystem
```

## 使用方式

安装后，将以下配置添加到你的 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "mcp-hub": {
      "command": "mcp",
      "args": ["serve"]
    }
  }
}
```

或者直接复制单个 Server 的配置：

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@org/server-name"]
    }
  }
}
```

---

> 项目地址: https://github.com/blankbrains/McpServerHub
