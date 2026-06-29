# MCP Server Hub

MCP 生态的一站式管理平台：发现、安装、管理、发布 MCP Server。

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)

980+ 个 MCP Server · 46 个 CLI 命令 · 16 个分类 · 206 个测试

搜索 → 安装 → 自动配置 → 管理。一个平台搞定。

---

## 安装

```bash
pip install mcp-hub-cli
```

```bash
# 零配置启动（SQLite，30 秒上线）
mcp quickstart

# 或完整初始化（PostgreSQL）
mcp init
mcp daemon start
# 仪表盘: http://localhost:3987
```

---

## 功能

### 市场与安装
- `mcp search` — 搜索 980+ 个 MCP Server，支持分类/标签/排序筛选
- `mcp info <server>` — 查看详情、评分、安全评分、Token 消耗
- `mcp install <server>` — 一行命令安装 + 自动配置，安装前自动安全扫描
- `mcp start/stop/restart <server>` — 进程管理
- `mcp logs <server>` — 实时日志

### 安全评分
- `mcp security <server>` — 四维评分（命令安全/包信誉/发布者可信度/代码模式）
- `mcp security --all` — 批量扫描全部 Server
- 安装时自动预扫描，危险 Server 阻止安装

### Token 消耗分析
- `mcp analyze <server>` — 分析工具定义占上下文窗口比
- `mcp analyze --all` — 批量分析
- `mcp optimize <server>` — 自动生成优化后的工具描述

### MCP Server Builder
- `mcp create` — 交互式向导，生成完整的 MCP Server 项目
- 支持 Python/TypeScript，8 个工具模板
- 前端页面也支持在线生成并下载 ZIP

### 质量监控
- `mcp monitor <server>` — 查看 Uptime/响应时间/可靠性评分
- `mcp reliability` — 最稳定 Server 排行榜
- 三级健康检查自动记录到数据库

### Web 仪表盘
- Server 详情页：安全评分、Token 分析、可靠性监控
- 在线 Builder：选择工具 → 生成 → 下载 ZIP

---

## 命令大全

```
🛒  市场              📦  安装              ⚙️  管理
  search <query>        install <server>      start <server>
  info <server>         uninstall <server>    stop <server>
  compare <a> <b>       list                  restart <server>
                                            status [server]
🔒  安全                📊  Token              logs <server> -f
  security <server>     analyze <server>      update <server>
  security --all        analyze --all         upgrade <server>
                        optimize <server>     rollback <server>
🔧  系统                                          
  daemon                🛠️  构建              📈  监控
  serve                 create                 monitor <server>
  init                                         monitor --all
  quickstart            🏆  可靠性             reliability
                        reliability --limit
👤  认证                                      
  login / logout / whoami                     
📤  发布                                      
  publish / my-servers / unpublish / stats    
⭐  社区                                      
  rate / review / favorite / favorites        
  trending / top-rated / most-downloaded      
```

---

## 技术栈

| 层 | 技术 |
|---|------|
| API | FastAPI + uvicorn |
| 数据库 | PostgreSQL 16+ / SQLite |
| ORM | SQLAlchemy 2.0 async |
| CLI | Click + Rich |
| 前端 | React 19 + Tailwind CSS + Vite |
| 协议 | MCP (JSON-RPC 2.0 over stdio) |
| 认证 | GitHub OAuth + JWT |

---

## 测试

```bash
pip install -e ".[dev]"
pytest tests/      # 206 个测试
ruff check src/    # 代码风格
```

---

## 许可证

MIT © 2026 McpServerHub
