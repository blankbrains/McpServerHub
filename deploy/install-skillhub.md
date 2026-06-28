# SkillHub 商店 CLI 安装指南

> 供 AI 代理阅读并执行的安装说明。用户只需粘贴提示词，AI 会自动完成安装。

## 安装方式

### pip 安装（推荐）

```bash
pip install mcp-hub
```

安装完成后，运行以下命令验证：

```bash
mcp --version
```

### 验证是否已安装

```bash
which mcp 2>/dev/null && mcp --version || echo "未安装"
```

如果输出 `mcp` 命令路径和版本号，则说明已安装。

## 安装技能/Server

安装 CLI 后，通过以下命令安装指定 MCP Server：

```bash
mcp install @org/server-name
```

安装成功后，AI 应将生成的配置信息展示给用户。
