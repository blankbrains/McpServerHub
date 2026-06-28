# MCP Server Hub 项目文档

> **MCP 生态的一站式平台 —— 发现 · 安装 · 管理 · 发布 · 社区**

| 项目 | 内容 |
|------|------|
| **版本** | v1.0 (规划中) |
| **产品定位** | MCP Server 的 npm + Docker Hub + K9s —— 发现、安装、运行、发布、社区评价全覆盖 |
| **预计周期** | 6-8 周 MVP |
| **难度** | ★★★★☆ |

---

## 一、项目概述

### 1.1 背景

2026 年 MCP（Model Context Protocol）正成为 AI Agent 行业的事实标准：

- MCP 已被 **Linux Foundation** 托管为行业标准协议
- **400+ MCP Server** 可用，社区贡献超 **100 万 GitHub Stars**
- **Claude Code**（$1B ARR）、**Cursor**（$2B ARR）、**ECC**（150K+ Stars）等主流 Agent 深度依赖 MCP
- 主流 Agent 框架（LangChain、CrewAI、LangGraph）均已原生支持 MCP

然而，MCP 生态的用户体验严重滞后于其技术增长。

### 1.2 解决什么问题

当前 MCP Server 的全链路体验：

```
发现: 不知道有什么好用的 Server → 只能 GitHub 盲搜 → 没法比较
安装: 翻 README → 手动 pip install → 手动写 mcp.json 配置
管理: 手动启动进程 → 进程挂了不知道 → 没有日志统一查看
发布: 写好了 Server → 不知道怎么让别人知道 → 没有分发渠道
社区: 想给好用的 Server 点赞 → 没有地方 → 遇到问题找不到帮助
```

**核心痛点矩阵：**

| 环节 | 痛点 | 当前方案 | 频率 |
|------|------|----------|------|
| **发现** | 想找一个功能的 Server，不知道有什么、哪个好 | GitHub 盲搜、口口相传 | 每天 |
| **比较** | 多个同类型 Server，不知道怎么选 | 一个个看 README 手动比较 | 每周 |
| **安装** | 手动 pip/npm install + 手动写 JSON 配置 | 无统一安装入口 | 每次添加 |
| **管理** | 不知道哪些在跑、哪些挂了、哪个版本 | 手动 ps aux / 自己记 | 持续 |
| **监控** | Server 挂了不知道、日志散落各处 | 没有监控 | 出问题时 |
| **发布** | 开源了但没人知道 | 发 Twitter / 写博客 | 一次性 |
| **安全** | 从 GitHub 装了一个，会不会有后门？ | 没人审查 | 每次安装 |
| **版本** | 更新了不知道、回滚需要手动操作 | 无版本管理 | 持续 |

### 1.3 目标用户

| 用户类型 | 描述 | 核心需求 | 规模 |
|----------|------|----------|------|
| **AI Agent 使用者** | 使用 Claude Code、Cursor 等工具的开发者 | 快速发现和安装 MCP Server | 100 万+ |
| **Agent 应用开发者** | 自研 Agent 系统，需集成 MCP 生态 | 管理运行时 Server + 监控状态 | 10 万+ |
| **MCP Server 开源作者** | 开发 MCP Server 的开源贡献者 | 发布和推广自己的 Server | 数千人 |
| **企业 Agent 团队** | 部署 10+ 个 MCP Server 的团队 | 统一管理、安全合规、运维监控 | 快速增长 |

---

## 二、市场竞争分析

### 2.1 现有方案格局

```
市场格局纵览：

传统方案:
  ┌─ 手动配置 (mcp.json)
  │  优点: 灵活
  │  缺点: 原始、手工、不可持续
  │  适合: 1-2 个 Server 的个人用户
  └─

工作流平台 (n8n / Dify / LangFlow):
  ┌─ 
  │  优点: 可视化编排、多工具集成
  │  缺点: 不是 MCP 原生、太重、MCP 只是小功能
  │  适合: 需要完整工作流引擎的用户
  └─

Agent 框架内管理 (LangGraph / CrewAI):
  ┌─
  │  优点: 深度集成到 Agent 开发流程
  │  缺点: 框架锁定、不通用
  │  适合: 已选定特定框架的团队
  └─

🔵 MCP Server Hub (我们):
    从 MCP 生态本身出发，做通用平台
```

### 2.2 竞品详细对比

| 维度 | 手动 mcp.json | n8n | Dify | ECC | MCP Server Hub |
|------|--------------|-----|------|-----|----------------|
| **MCP 原生** | ✅ | ❌ 通用工作流 | ❌ 应用平台 | ⚠️ 脚本聚合 | **✅ 纯 MCP** |
| **Server 发现** | ❌ | ❌ | ❌ | ⚠️ 有限 | **✅ Registry** |
| **一键安装** | ❌ | ⚠️ 节点安装 | ⚠️ 插件安装 | ❌ | **✅ 一行命令** |
| **自动配置** | ❌ | ❌ | ❌ | ❌ | **✅ 自动注入** |
| **进程管理** | ❌ | ✅ | ✅ | ❌ | **✅ 全生命周期** |
| **健康检查** | ❌ | ❌ | ✅ | ❌ | **✅ 三级检查** |
| **版本管理** | ❌ | ❌ | ❌ | ❌ | **✅ update/rollback** |
| **社区评分** | ❌ | ❌ | ❌ | ❌ | **✅ 星级+评价** |
| **开发者发布** | ❌ | ❌ | ❌ | ❌ | **✅ 一行提交** |
| **安全审查** | ❌ | ❌ | ❌ | ❌ | **✅ 三级标签** |
| **事件总线** | ❌ | ✅ | ❌ | ❌ | **✅ Pub/Sub** |
| **开源** | - | ✅ | ✅ | ✅ | **✅ MIT** |

### 2.3 机会窗口

1. **协议标准化完成** — MCP 已被 Linux Foundation 托管，生态进入规模化阶段
2. **400+ Server 临界点** — 数量到了需要管理工具的时候
3. **没有竞品专做 MCP 平台** — 所有现有方案都是"顺便管一下 MCP"
4. **网络效应明确** — 用户越多 → 发布者越多 → Server 越多 → 用户越多
5. **2026 年是窗口年** — MCP 正从"早期采用者"走向"早期大众"

---

## 三、产品定位与愿景

### 3.1 产品定位

> **MCP Server Hub —— MCP 生态的一站式平台**

```
发现 ─── 安装 ─── 管理 ─── 发布 ─── 社区
 │        │        │        │        │
 ▼        ▼        ▼        ▼        ▼
搜索   一行命令  进程管理  提交审核  评分评价
浏览   自动配置  健康检查  版本管理  排行榜
比较   依赖处理  日志查看  分发推广  讨论
```

### 3.2 类比理解

| 生态 | 包管理 | 运行时管理 | 社区发现 |
|------|--------|-----------|---------|
| Node.js | npm install | pm2 | npm registry |
| Docker | docker pull | docker ps / docker-compose | Docker Hub |
| MCP Server | **Hub install** | **Hub manage** | **Hub search/rate** |

MCP Server Hub = npm + Docker Hub + pm2 + K9s，专为 MCP 生态定制。

### 3.3 核心价值主张

```
"想用 MCP Server？一行命令装好，自动配置，自动监控。

想发 MCP Server？一行命令提交，全社区都能发现，自动安全审核。"
```

三句话：

| 视角 | 价值 | 对应功能 |
|------|------|----------|
| **"发现即安装"** | 看到就能用，搜索完一键装好 | Registry + Install |
| **"安装即管理"** | 装了自动跑、挂了自动重启、日志自动收 | Process Manager + Health Check |
| **"发布即推广"** | 提交到 Hub 就是推广，评分+排行+安全认证 | Community + Publish |

---

## 四、核心功能详细设计

### 4.1 功能全景图

```
                              MCP Server Hub
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
    🏪 发现市场               ⚙️ 运行时管理              👥 社区生态
        │                           │                           │
  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
  │ 搜索与浏览    │          │ 进程管理      │          │ 评分评价      │
  │ 分类与标签    │          │ 健康检查      │          │ 排行榜       │
  │ Server 详情   │          │ 自动重启      │          │ 收藏/统计    │
  │ 功能对比      │          │ 日志查看      │          │ 讨论区       │
  └──────────────┘          └──────────────┘          └──────────────┘
        │                           │                           │
  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
  │ 一键安装      │◄────────►│ 版本管理      │          │ 开发者发布    │
  │ 自动配置      │          │ 配置管理      │          │ 安全审查      │
  │ 依赖处理      │          │ 更新/回滚     │          │ 合规认证      │
  └──────────────┘          └──────────────┘          └──────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                          ┌──────────────────┐
                          │ 事件总线 (Pub/Sub) │
                          └──────────────────┘
```

---

### 4.2 功能 F1: MCP 市场（发现 + 搜索 + 浏览）

**用户故事**：作为开发者，我想知道有什么 MCP Server 可以用，它们之间怎么选。

#### CLI 交互

```
mcp search                              # 浏览所有 Server (按热度排序)
mcp search web scraping                 # 按关键词搜索
mcp search --category browser           # 按分类筛选
mcp search --sort rating                # 按评分排序
mcp search --tag official               # 按标签筛选

mcp info @anthropic/web-search          # 查看 Server 详情
mpc info @anthropic/web-search --json   # JSON 格式输出
mcp compare @a/server @b/server         # 对比两个 Server
```

#### Web 市场界面

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Server Hub  ·  搜索 MCP Server...        [👤 登录]    │
├─────────────────────────────────────────────────────────────┤
│  分类: 全部 | 浏览器 | 数据库 | 代码 | 通信 | AI | 工具     │
├─────────────────────────────────────────────────────────────┤
│  排序: 🔥 热门  ⭐ 评分  📥 下载  🆕 最新                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ⭐⭐⭐⭐⭐ @anthropic/web-search                      │   │
│  │   🌐 浏览器 · 2026-06 · 📥 12,340 次下载            │   │
│  │   让 Agent 搜索网络并返回结构化结果                    │   │
│  │   [🔒 安全认证]  [💬 245 评价]                       │   │
│  │   ────────────────────────────────────────           │   │
│  │   🟢 v2.1.0 已安装 · 运行中                          │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ⭐⭐⭐⭐ @community/sql-query                        │   │
│  │   🗄️ 数据库 · 2026-05 · 📥 8,210 次下载              │   │
│  │   自然语言查询数据库，支持 PostgreSQL/MySQL           │   │
│  │   [⚪ 未认证]  [💬 89 评价]                          │   │
│  │   ────────────────────────────────────────           │   │
│  │   📥 [一键安装]                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│  ...                                                       │
├─────────────────────────────────────────────────────────────┤
│  📊 共 412 个 Server  ·  加载更多...                        │
└─────────────────────────────────────────────────────────────┘
```

#### Server 详情页

```
┌─────────────────────────────────────────────────────────────┐
│  @anthropic/web-search                    ⭐⭐⭐⭐⭐ 4.8     │
│  🔒 安全认证  ·  🌐 官方发布                              │
├─────────────────────────────────────────────────────────────┤
│  📝 描述                                                    │
│  让 Agent 搜索网络并返回结构化结果。支持 Google、Bing、      │
│  DuckDuckGo 等搜索引擎，自动提取摘要和关键信息。             │
├─────────────────────────────────────────────────────────────┤
│  📊 统计                                                    │
│  📥 12,340 次下载  ·  💬 245 评价  ·  ⭐ 4.8/5.0           │
│  📦 v2.1.0 (最新)    ·  🕐 2 小时前更新                     │
├─────────────────────────────────────────────────────────────┤
│  🏷️ 标签: search / web / scraping / official               │
│  ⚙️ 依赖: Python ≥3.10, httpx                              │
│  📄 许可证: MIT                                            │
│  🔗 GitHub: github.com/anthropic/mcp-web-search            │
├─────────────────────────────────────────────────────────────┤
│  [📥 一键安装]  [⭐ 收藏]  [💬 写评价]  [🚨 举报]          │
└─────────────────────────────────────────────────────────────┘
```

#### 数据结构

```json
{
  "name": "@anthropic/web-search",
  "version": "2.1.0",
  "description": "让 Agent 搜索网络并返回结构化结果",
  "author": "anthropic",
  "publisher": {
    "type": "organization",
    "verified": true
  },
  "categories": ["browser", "search", "web"],
  "tags": ["search", "web-scraping", "official"],
  "rating": 4.8,
  "review_count": 245,
  "download_count": 12340,
  "install": {
    "type": "pip",
    "package": "mcp-server-web-search",
    "command": "uvx mcp-server-web-search",
    "auto_config": true
  },
  "dependencies": {
    "python": ">=3.10",
    "pip_packages": ["httpx", "beautifulsoup4"]
  },
  "security": {
    "level": "verified",     // verified / reviewed / unreviewed
    "last_audit": "2026-06-15",
    "network_access": true,
    "file_access": false
  },
  "homepage": "https://github.com/anthropic/mcp-web-search",
  "license": "MIT",
  "updated_at": "2026-06-28T10:00:00Z"
}
```

---

### 4.3 功能 F2: 一键安装与自动配置

**用户故事**：找到想要的 Server 了，点一下就能装上，不用翻 README。

#### CLI 交互

```
mcp install @anthropic/web-search            # 安装最新版
mcp install @anthropic/web-search@2.0.0      # 安装指定版本
mcp uninstall @anthropic/web-search          # 卸载
mcp list                                      # 列出已安装的 Server
```

#### 安装流程

```
用户输入: mcp install @anthropic/web-search

Hub 执行:
  Step 1 ✅ 解析 Server 元数据 → 获取安装信息
  Step 2 ✅ 检查环境 → Python 3.10+ ✓ / pip 已安装 ✓
  Step 3 ✅ 安装依赖 → pip install mcp-server-web-search
  Step 4 ✅ 写入配置 → 自动添加到 claude_desktop_config.json
  Step 5 ✅ 启动 Server → 子进程启动成功
  Step 6 ✅ 健康检查 → L1 ✓ L2 ✓

输出:
  ✅ 安装成功！
  📍 @anthropic/web-search v2.1.0
  📂 已自动配置到 Claude Code
  🟢 状态: 运行中
```

#### 自动配置细节

安装**前**，用户手动配置 `mcp.json`：

```json
{
  "mcpServers": {
    "web-search": {
      "command": "uvx",
      "args": ["mcp-server-web-scraper", "--api-key", "xxx"],
      "env": { "SEARCH_API_KEY": "xxx" }
    }
  }
}
```

安装**后**，Hub 自动完成：

```json
{
  "mcpServers": {
    "web-search": {   // ← Hub 会自动生成此项
      "command": "uvx",
      "args": ["mcp-server-web-search"],
      "env": {}
    }
  },
  "_mcpHub": {        // ← Hub 元数据（不干扰 Agent）
    "managed": ["web-search"],
    "hubUrl": "http://localhost:3987"
  }
}
```

#### 支持的安装方式

| 类型 | 支持 | MVP |
|------|------|-----|
| `uvx` (推荐) | ✅ | ✅ |
| `pip` | ✅ | ✅ |
| `npx` | ✅ | ✅ |
| `npm install -g` | ✅ | ⏳ |
| `docker` | ✅ | ⏳ |

---

### 4.4 功能 F3: 进程生命周期管理

**用户故事**：装了就要跑起来，我想要统一管理所有 Server 的启动/停止/重启。

#### CLI 交互

```
mcp start web-search                  # 启动
mcp stop web-search                   # 停止
mcp restart web-search                # 重启
mcp start all                         # 启动所有
mcp stop all                          # 停止所有
mcp status                            # 查看所有状态
mcp status web-search                 # 查看特定状态
mcp logs web-search                   # 查看日志（实时 tail）
mcp logs web-search --lines 50        # 查看最近 50 行
mcp logs web-search --since 1h        # 查看过去 1 小时
mcp logs web-search --level error     # 只看错误日志
```

#### 进程模型

```
MCP Hub (Daemon)
  │
  ├─ 🟢 web-search     (PID 12345, uptime 3d, mem 45MB)
  ├─ 🟢 db-query       (PID 12389, uptime 1d, mem 62MB)
  ├─ 🔴 file-processor (PID 12456, 异常: 连接超时, 已重启 2 次)
  ├─ ⏹  slient-trans   (已停止)
  │
  └─ [子进程隔离]
      每个 Server 运行在独立的 subprocess 中
      使用独立 venv / node_modules 避免依赖冲突
      CPU/内存/网络 通过资源限制隔离
```

#### 守护进程模式

```bash
# 后台常驻模式
mcp daemon start          # 启动 Hub 守护进程
mcp daemon status         # 查看 Hub 进程状态
mcp daemon stop           # 停止 Hub 守护进程

# 开机自启
mcp daemon enable         # 配置开机自启
mcp daemon disable        # 取消开机自启
```

---

### 4.5 功能 F4: 三级健康检查与自动恢复

**用户故事**：Server 挂了我要知道，最好能自己活过来。

#### 健康检查体系

| 级别 | 方法 | 频率 | 耗时 | 说明 |
|------|------|------|------|------|
| **L1 进程级** | `os.kill(pid, 0)` 检查进程存活 | 每 5 秒 | <1ms | 最轻量，仅查进程是否存在 |
| **L2 连接级** | 尝试连接 Server 的 stdio/SSE 端点 | 每 30 秒 | <10ms | 确认网络可通 |
| **L3 功能级** | 调用一个简单的 MCP tool（如 `ping`） | 每 5 分钟 | <100ms | 确认功能正常响应 |

#### 自动恢复策略

```
检测到异常 ──┐
             ▼
        ┌─────────┐
        │  L1 异常  │──── 直接重启
        └─────────┘
             │
        ┌─────────┐
        │  L2 异常  │──── 杀进程 → 等待 2s → 重启
        └─────────┘
             │
        ┌─────────┐
        │  L3 异常  │──── 记录错误 → 如果连续 3 次 → 重启
        └─────────┘
             │
        ┌─────────┐
        │  重启失败  │──── 最多重试 3 次 → 标记 ERROR → 桌面通知
        └─────────┘
```

#### 告警通知

```bash
# 桌面通知（异常时弹出）
🔴 MCP Hub 通知: @community/db-query 异常
   已自动重启 2 次仍失败
   ⚡ 建议: 查看日志 `mcp logs db-query` 排查

# 状态变化历史
mcp timeline @community/db-query
  [10:00:00] 🟢 运行正常
  [10:01:23] ⚠️ L3 功能检查超时
  [10:01:25] 🔄 自动重启 (第1次)
  [10:01:28] 🟢 重启成功
  [10:02:01] ⚠️ L3 再次超时
  ...
```

---

### 4.6 功能 F5: Web Dashboard

**用户故事**：不想背命令行，打开浏览器看一眼就知道全部。

#### 仪表盘总览

```
┌─────────────────────────────────────────────────────────────┐
│  🔵 MCP Server Hub                              [⚙️ 设置]  │
├─────────────────────────────────────────────────────────────┤
│  📊 总览                                                 │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│  │ 🟢   │ │ 🔴   │ │ ⏹   │ │ 📥   │ │ ⭐   │           │
│  │ 12   │ │  2   │ │  3   │ │ 47   │ │ 4.2  │           │
│  │ 运行  │ │ 异常  │ │ 停止  │ │ 已装  │ │ 均分  │           │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘           │
├─────────────────────────────────────────────────────────────┤
│  🏪 发现市场                        [📥 已安装] [⭐ 收藏]  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 搜索: [................................] [搜索]       │   │
│  │ 分类: 全部 | 浏览器 | 数据库 | 代码 | AI | 工具     │   │
│  │ ─────────────────────────────────────────────────    │   │
│  │ ⭐⭐⭐⭐⭐ @anthropic/web-search  v2.1.0  [管理]     │   │
│  │ ⭐⭐⭐⭐  @community/sql-query    v1.3.0  [安装]     │   │
│  │ ⭐⭐⭐⭐  @community/file-tools   v0.8.2  [安装]     │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ⚙️ 已安装 Server                                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🟢 @anthropic/web-search    运行 3d  ·  CPU 0.5%    │   │
│  │   [重启] [停止] [日志] [配置]                         │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 🔴 @community/db-query      异常: 连接超时           │   │
│  │   [重启] [查看日志] [排查建议]                        │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ ⏹  @community/file-tools    已停止                   │   │
│  │   [启动] [卸载]                                       │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  📈 系统资源: 🖥 CPU 8%  ·  💾 内存 1.2G  ·  💿 磁盘 45%  │
└─────────────────────────────────────────────────────────────┘
```

#### 日志在线查看

```
┌─────────────────────────────────────────────────────────────┐
│  日志: @anthropic/web-search                 [实时] [清屏]  │
├─────────────────────────────────────────────────────────────┤
│  10:23:01 [INFO] Server started, listening on stdio         │
│  10:23:02 [INFO] Registered tools: search_web, crawl_url    │
│  10:23:05 [INFO] Request: search_web(q="MCP protocol")      │
│  10:23:06 [INFO] Calling Google Search API...               │
│  10:23:08 [INFO] Got 10 results in 2.1s                    │
│  10:23:08 [INFO] Returning structured results               │
│  ────────────────────────────────────────                  │
│  📊 实时统计                                                │
│  调用量: 1,234  (过去 24h: 89)                              │
│  平均响应: 1.2s  ·  错误率: 0.8%                           │
│  Token 消耗: 45,678 (输入) / 12,345 (输出)                  │
└─────────────────────────────────────────────────────────────┘
```

---

### 4.7 功能 F6: 版本管理与配置管理

**用户故事**：有新版本了我想知道，升级前怕兼容问题想备份。

#### CLI 交互

```bash
# 版本管理
mcp update                        # 检查所有 Server 更新
mcp update web-search             # 更新特定 Server
mcp update --check                # 只检查不更新
mcp rollback web-search           # 回滚上一版本
mcp rollback web-search --to 1.0  # 回滚到指定版本

# 配置管理
mcp config web-search --list               # 查看配置
mcp config web-search --set KEY=VALUE      # 设置环境变量
mcp config web-search --get KEY            # 获取配置项
mcp config web-search --env dev            # 切换配置环境

mcp config export > my-config.json         # 导出配置
mcp config import my-config.json           # 导入配置
```

#### 版本管理策略

```
v2.0.0 ── 升级 ──→ v2.1.0         # 小版本更新（自动兼容）
  ↑                     │
  └── rollback ─────────┘

v1.0.0 ── 升级 ──→ v2.0.0         # 大版本更新（breaking change）
                    │
  升级前自动备份     │
  通知用户确认       │
  提供 changelog    │
```

- **小版本更新**（patch/minor）：静默升级，升级前自动备份
- **大版本更新**（major）：标记 breaking change，通知用户确认
- **升级前自动备份**配置文件到 `data/backups/`

---

### 4.8 功能 F7: 开发者发布与安全审查

**用户故事**：我写了个 MCP Server，想让全社区的人都能发现它。

#### 开发者发布流程

```bash
# 登录
mcp login                          # 登录（GitHub OAuth）
mcp whoami                         # 查看当前用户
mcp logout                         # 退出登录

# 发布
mcp publish ./path/to/my-server    # 发布 Server
mcp publish --visibility private   # 私有发布（只自己可见）
mcp publish --draft                # 草稿（不公开）

# 管理已发布
mcp my-servers                     # 查看我发布的 Server
mcp deprecate my-server "原因"     # 废弃某个版本
mcp unpublish my-server            # 下架

# 数据
mcp stats my-server                # 查看下载/使用数据
```

#### 发布流程

```
开发者: mcp publish ./my-server

Hub 执行:
  Step 1 ✅ 解析 mcp-server 元数据（package.json/pyproject.toml）
  Step 2 ✅ 验证 Server 启动正常（自动启停测试）
  Step 3 ✅ 运行安全扫描（依赖检查 + 网络权限评估）
  Step 4 ✅ 分配安全标签（🔒 verified / ⚪ reviewed / ⚠️ unreviewed）
  Step 5 ✅ 上传到 Registry
  Step 6 ✅ 生成 Server 详情页

输出:
  ✅ 发布成功！
  📍 @username/my-server v1.0.0
  🔗 https://hub.mcp.com/@username/my-server
  ⚪ 安全标签: reviewed（等待验证）
  📊 预计 24 小时内被搜索到
```

#### 安全审查体系

| 安全等级 | 标签 | 含义 | 谁可以获得 |
|----------|------|------|-----------|
| **Verified** | 🔒 | 经过官方安全审计 | 大厂/经过验证的组织 |
| **Reviewed** | ⚪ | 已自动扫描，无已知风险 | 所有正常发布的 Server |
| **Unreviewed** | ⚠️ | 未审查或检测到潜在风险 | 新发布/有可疑特征的 Server |
| **Blocked** | 🚫 | 已确认恶意 | 封禁 |

**自动安全扫描**：

| 检查项 | 说明 |
|--------|------|
| 依赖漏洞 | 扫描已知 CVE |
| 网络权限 | 是否需要外网、局域网 |
| 文件权限 | 是否读写本地文件 |
| 环境变量 | 是否读取敏感环境变量 |
| 可疑代码 | 检测混淆、base64 解码、eval 等模式 |

---

### 4.9 功能 F8: 社区功能

**用户故事**：用了好的 Server 想给它点赞，遇到问题想看看别人怎么说。

#### 评分评价

```bash
mcp rate @anthropic/web-search 5                     # 评分（1-5）
mcp review @anthropic/web-search "非常好用！"        # 写评价
mcp reviews @anthropic/web-search                   # 查看所有评价
mcp reviews @anthropic/web-search --sort newest      # 按最新排序
```

#### 排行榜

```bash
mcp trending           # 热门趋势榜（近 7 天下载增速最快）
mcp top-rated          # 评分最高榜
mcp most-downloaded    # 下载最多榜
mcp new-releases       # 最新发布榜
mcp trending --category browser  # 按分类看热门
```

#### 收藏与统计

```bash
mcp favorite @anthropic/web-search       # 收藏 Server
mcp favorites                            # 查看收藏列表
mcp stats @anthropic/web-search          # 查看统计
mcp stats @anthropic/web-search --period 30d  # 近 30 天
```

---

### 4.10 功能 F9: 事件总线

**用户故事**：我希望 Server 之间能互相通信——A 搜完数据，B 自动处理。

#### 设计

```
┌─────────────────────────────────────────────────┐
│                 事件总线 (Event Bus)                │
│  ┌───────────────────────────────────────────┐   │
│  │  Topic: data.scraped                      │   │
│  │  ┌─────────┐    ┌─────────┐              │   │
│  │  │ 发布者 A │───→│ 订阅者 B │              │   │
│  │  │ web-search│    │ db-query │              │   │
│  │  └─────────┘    └─────────┘              │   │
│  └───────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────┐   │
│  │  Topic: system.server.error               │   │
│  │  ┌─────────┐    ┌─────────┐              │   │
│  │  │ Hub 系统│───→│ 所有订阅者│              │   │
│  │  └─────────┘    └─────────┘              │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

#### CLI 交互

```bash
mcp event subscribe data.scraped          # 订阅事件
mcp event subscribe system.server.error   # 订阅系统事件
mcp event publish data.scraped '{"url": "https://..."}'  # 发布事件
mcp event list                            # 查看事件订阅
mcp event history data.scraped            # 查看事件历史
```

#### 内置系统事件

| 事件 | 触发时机 | payload |
|------|----------|---------|
| `system.server.started` | Server 启动 | `{name, version, pid}` |
| `system.server.stopped` | Server 停止 | `{name, pid, exit_code}` |
| `system.server.error` | Server 异常 | `{name, error, restarts}` |
| `system.server.updated` | Server 更新 | `{name, old_ver, new_ver}` |
| `system.hub.started` | Hub 启动 | `{version, servers_count}` |
| `system.hub.stopping` | Hub 关闭 | `{running_servers}` |

---

## 五、技术架构设计

### 5.1 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        用户交互层                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │  CLI (mcp)       │  │  Web Dashboard   │  │  VS Code       │  │
│  │  Python click    │  │  React / HTMX    │  │  Extension     │  │
│  │  (主入口)         │  │  (可视化管理)     │  │  (IDE 内管理)   │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬────────┘  │
└───────────┼─────────────────────┼────────────────────┼────────────┘
            │                     │                    │
            ▼                     ▼                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                       API 层 (FastAPI)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │  Market  │ │  Install │ │  Manage  │ │  Publish │ │Community│  │
│  │  /search │ │  /install│ │ /start/  │ │  /publish│ │ /rate   │  │
│  │  /info   │ │  /uninst │ │ /stop/   │ │  /deprec │ │ /review │  │
│  │  /compare│ │  /config │ │ /restart │ │  /stats  │ │/trending│  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                          │
│  │  Health  │ │  Version │ │  Event   │                          │
│  │  /health │ │ /update  │ │  Bus     │                          │
│  │  /alerts │ │ /rollback│ │ /publish │                          │
│  │          │ │ /history │ │/subscribe│                          │
│  └──────────┘ └──────────┘ └──────────┘                          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                       核心服务层                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ │
│  │ Registry     │ │ Process      │ │ Event Bus    │ │ Security │ │
│  │ (索引/搜索)   │ │ Manager      │ │ (Pub/Sub)    │ │ Scanner  │ │
│  │ 本地+远程索引  │ │ 子进程生命周期  │ │ 事件路由    │ │ 安全审查  │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────┬─────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │ │
│  │ Installer    │ │ Health       │ │ Auth         │           │ │
│  │ (安装执行器)  │ │ Checker      │ │ (GitHub OAuth)│           │ │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘           │ │
└─────────┼─────────────────┼───────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                        数据层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ SQLite /     │  │ Local        │  │ Logs                    │ │
│  │ PostgreSQL   │  │ Filesystem   │  │ 结构化日志 + 轮转归档    │ │
│  │ (元数据/      │  │ (Server 包/   │  │                         │ │
│  │ 用户/评价)    │  │  配置备份)    │  │                         │ │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 技术选型

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| **CLI** | Python + click | 原生 Python 生态，pip install 即用 |
| **API** | Python + FastAPI | 高性能异步、类型安全、自动 OpenAPI 文档 |
| **数据库** | SQLite（本地）/ PostgreSQL（生产） | MVP SQLite 零配置，后续可平滑迁移 |
| **MCP 运行时** | fastmcp + subprocess | fastmcp 简化 MCP Server 封装与通信 |
| **Web 前端** | React 19 + Tailwind CSS | 轻量 SPA，适合 Dashboard 场景 |
| **进程管理** | subprocess + psutil | 跨平台，轻量无额外依赖 |
| **包管理** | pip/uvx + npm/npx | 覆盖主流 MCP Server 安装方式 |
| **安全扫描** | 自定义规则引擎 + CVE 数据库 | 自动化安全检测 |
| **认证** | GitHub OAuth | 开发者最熟悉，发布有门槛 |

### 5.3 数据库设计

#### servers —— Server 元数据表

```sql
CREATE TABLE servers (
    id TEXT PRIMARY KEY,                       -- @org/server-name
    name TEXT NOT NULL,
    display_name TEXT,
    description TEXT,
    author TEXT NOT NULL,                      -- 发布者用户名
    publisher_type TEXT DEFAULT 'individual',  -- individual / organization
    publisher_verified INTEGER DEFAULT 0,      -- 是否验证
    current_version TEXT,                      -- 当前已安装版本
    latest_version TEXT,                       -- 远程最新版本
    categories TEXT,                           -- JSON ["browser","data"]
    tags TEXT,                                 -- JSON ["search","official"]
    install_type TEXT,                         -- pip / npm / uvx / docker
    install_package TEXT,
    install_command TEXT,
    config_template TEXT,                      -- JSON 配置模板
    homepage TEXT,
    license TEXT,
    security_level TEXT DEFAULT 'unreviewed',  -- verified / reviewed / unreviewed
    security_audit_at TIMESTAMP,
    network_access INTEGER DEFAULT 0,          -- 是否需要网络
    file_access INTEGER DEFAULT 0,             -- 是否需要文件系统
    rating REAL DEFAULT 0.0,                   -- 均分
    review_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    favorite_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'not_installed',       -- not_installed / running / stopped / error
    auto_restart INTEGER DEFAULT 1,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### reviews —— 评价表

```sql
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id TEXT REFERENCES servers(id),
    user_id TEXT,
    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
    content TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(server_id, user_id)
);
```

#### install_history —— 安装记录表

```sql
CREATE TABLE install_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id TEXT REFERENCES servers(id),
    version TEXT,
    action TEXT,                              -- install / uninstall / update / rollback
    status TEXT,                              -- success / failed
    error_message TEXT,
    created_at TIMESTAMP
);
```

#### health_logs —— 健康日志表

```sql
CREATE TABLE health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id TEXT REFERENCES servers(id),
    check_type TEXT,                          -- L1_process / L2_connection / L3_functional
    status TEXT,                              -- ok / warning / error
    message TEXT,
    response_time_ms INTEGER,
    created_at TIMESTAMP
);
```

#### events —— 事件表

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    publisher TEXT,                           -- server_id 或 system
    payload TEXT,                             -- JSON
    created_at TIMESTAMP
);

CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id TEXT,
    topic TEXT,
    created_at TIMESTAMP
);
```

#### users —— 用户表

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,                      -- GitHub username
    display_name TEXT,
    avatar_url TEXT,
    github_id TEXT,
    email TEXT,
    role TEXT DEFAULT 'user',                 -- user / publisher / admin
    created_at TIMESTAMP,
    last_login TIMESTAMP
);
```

### 5.4 API 接口设计

#### 市场与发现

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| `GET` | `/api/v1/market/search?q=&cat=&sort=` | 搜索 Server | ✅ |
| `GET` | `/api/v1/market/trending` | 热门趋势榜 | ✅ |
| `GET` | `/api/v1/market/top-rated` | 评分最高榜 | ✅ |
| `GET` | `/api/v1/market/new-releases` | 最新发布 | ✅ |
| `GET` | `/api/v1/market/servers/{id}` | Server 详情 | ✅ |
| `GET` | `/api/v1/market/servers/{id}/reviews` | 评价列表 | ✅ |
| `GET` | `/api/v1/market/compare?ids=a,b` | 对比 Server | ⏳ |
| `GET` | `/api/v1/market/categories` | 分类列表 | ✅ |

#### 安装与管理

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| `POST` | `/api/v1/servers/install` | 安装 Server | ✅ |
| `POST` | `/api/v1/servers/{id}/uninstall` | 卸载 Server | ✅ |
| `POST` | `/api/v1/servers/{id}/start` | 启动 | ✅ |
| `POST` | `/api/v1/servers/{id}/stop` | 停止 | ✅ |
| `POST` | `/api/v1/servers/{id}/restart` | 重启 | ✅ |
| `GET` | `/api/v1/servers/` | 列出已安装 | ✅ |
| `GET` | `/api/v1/servers/{id}/status` | 运行状态 | ✅ |
| `GET` | `/api/v1/servers/{id}/logs` | 日志 | ✅ |
| `PUT` | `/api/v1/servers/{id}/config` | 更新配置 | ✅ |
| `POST` | `/api/v1/servers/{id}/update` | 更新版本 | ⏳ |
| `POST` | `/api/v1/servers/{id}/rollback` | 回滚版本 | ⏳ |

#### 开发者发布

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| `POST` | `/api/v1/publish` | 发布 Server | ✅ |
| `PUT` | `/api/v1/publish/{id}` | 更新 Server | ⏳ |
| `DELETE` | `/api/v1/publish/{id}` | 下架 Server | ⏳ |
| `GET` | `/api/v1/publish/mine` | 我的发布 | ✅ |
| `GET` | `/api/v1/publish/{id}/stats` | 统计数据 | ⏳ |

#### 社区

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| `POST` | `/api/v1/community/rate` | 评分 | ✅ |
| `POST` | `/api/v1/community/review` | 写评价 | ✅ |
| `POST` | `/api/v1/community/favorite` | 收藏 | ✅ |
| `GET` | `/api/v1/community/favorites` | 收藏列表 | ✅ |

#### 健康检查

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| `GET` | `/api/v1/health` | Hub 自身健康 | ✅ |
| `GET` | `/api/v1/health/servers` | 全局健康摘要 | ✅ |

#### 事件总线

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| `POST` | `/api/v1/events/publish` | 发布事件 | ⏳ |
| `POST` | `/api/v1/events/subscribe` | 订阅事件 | ⏳ |
| `GET` | `/api/v1/events/history?topic=` | 事件历史 | ⏳ |

#### 认证

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| `GET` | `/api/v1/auth/login` | GitHub OAuth 登录 | ✅ |
| `GET` | `/api/v1/auth/callback` | OAuth 回调 | ✅ |
| `GET` | `/api/v1/auth/me` | 当前用户 | ✅ |

---

## 六、CLI 命令全景

```
mcp
├── search [query]       # 搜索/浏览 MCP Server
│   ├── --category/-c    # 按分类筛选
│   ├── --sort           # 排序: hot/rating/downloads/new
│   ├── --tag            # 按标签筛选
│   └── --json           # JSON 输出
│
├── info <server>        # 查看 Server 详情
│   └── --json           # JSON 输出
│
├── compare <a> <b>      # 对比两个 Server
│
├── install <server>     # 安装 Server
│   └── [version]        # 指定版本
│
├── uninstall <server>   # 卸载
│
├── list                 # 列出已安装
│
├── start <server>       # 启动
│   └── all              # 启动所有
│
├── stop <server>        # 停止
│   └── all              # 停止所有
│
├── restart <server>     # 重启
│
├── status [server]      # 查看状态
│   └── --json           # JSON 输出
│
├── logs <server>        # 查看日志
│   ├── --lines/-n       # 行数
│   ├── --since          # 时间范围
│   ├── --level          # 日志级别
│   └── --follow/-f      # 实时 tail
│
├── update [server]      # 检查/执行更新
│   └── --check          # 只检查不更新
│
├── rollback <server>    # 回滚版本
│   └── --to <version>   # 指定版本
│
├── config <server>      # 配置管理
│   ├── --list           # 查看
│   ├── --set K=V        # 设置
│   ├── --get K          # 获取
│   └── --env <name>     # 环境切换
│
├── config export        # 导出配置
├── config import <file> # 导入配置
│
├── daemon               # 守护进程
│   ├── start            # 启动 Hub
│   ├── stop             # 停止 Hub
│   ├── status           # Hub 状态
│   ├── enable           # 开机自启
│   └── disable          # 取消自启
│
├── login                # 登录 (GitHub OAuth)
├── logout               # 退出
├── whoami               # 当前用户
│
├── publish <path>       # 发布 Server
│   ├── --visibility     # 公开/私有
│   └── --draft          # 草稿
│
├── my-servers           # 我的发布
├── unpublish <server>   # 下架
├── deprecate <server>   # 废弃版本
├── stats <server>       # 统计数据
│
├── rate <server> <n>    # 评分
├── review <server>      # 写/看评价
│
├── favorite <server>    # 收藏
├── favorites            # 收藏列表
│
├── trending             # 热门趋势
├── top-rated            # 评分最高
├── most-downloaded      # 下载最多
├── new-releases         # 最新发布
│
├── event                # 事件总线
│   ├── subscribe <topic>  # 订阅
│   ├── publish <topic>    # 发布
│   ├── list               # 订阅列表
│   └── history <topic>    # 事件历史
│
└── help [command]       # 帮助
```

---

## 七、目录结构

```
McpServerHub/
├── README.md
├── McpServerHub项目文档.md
├── pyproject.toml
│
├── src/
│   └── mcp_hub/
│       ├── __init__.py
│       ├── main.py                    # FastAPI 应用入口
│       │
│       ├── cli/                       # CLI 命令
│       │   ├── __init__.py
│       │   ├── app.py                 # CLI 主入口 (click group)
│       │   ├── search.py              # mcp search / info / compare
│       │   ├── install.py             # mcp install / uninstall / list
│       │   ├── manage.py              # mcp start / stop / restart / status
│       │   ├── logs.py                # mcp logs
│       │   ├── update.py              # mcp update / rollback
│       │   ├── config.py              # mcp config
│       │   ├── daemon.py              # mcp daemon
│       │   ├── publish.py             # mcp publish / unpublish / my-servers
│       │   ├── community.py           # mcp rate / review / favorite
│       │   ├── trending.py            # mcp trending / top-rated / ...
│       │   ├── event.py               # mcp event
│       │   └── auth.py                # mcp login / logout / whoami
│       │
│       ├── api/                       # REST API
│       │   ├── __init__.py
│       │   ├── app.py                 # FastAPI 路由注册
│       │   ├── routes_market.py       # 市场发现 API
│       │   ├── routes_manage.py       # 安装/管理 API
│       │   ├── routes_publish.py      # 发布 API
│       │   ├── routes_community.py    # 社区 API
│       │   ├── routes_health.py       # 健康检查 API
│       │   ├── routes_events.py       # 事件总线 API
│       │   ├── routes_auth.py         # 认证 API
│       │   └── schemas.py             # Pydantic 模型
│       │
│       ├── core/                      # 核心服务
│       │   ├── __init__.py
│       │   ├── registry.py            # Server 注册与索引
│       │   ├── process_manager.py     # 子进程生命周期管理
│       │   ├── health_check.py        # 三级健康检查
│       │   ├── installer.py           # 安装执行器
│       │   ├── version_manager.py     # 版本管理
│       │   ├── config_manager.py      # 配置管理
│       │   ├── event_bus.py           # 事件总线
│       │   ├── security_scanner.py    # 安全扫描引擎
│       │   └── auth.py                # OAuth 认证
│       │
│       ├── models/                    # 数据模型
│       │   ├── __init__.py
│       │   ├── server.py
│       │   ├── review.py
│       │   └── user.py
│       │
│       ├── db/                        # 数据库层
│       │   ├── __init__.py
│       │   ├── database.py            # SQLite 操作封装
│       │   ├── migrations.py          # 数据库迁移
│       │   └── seed.py                # 初始数据（预置 Server 索引）
│       │
│       └── web/                       # Web Dashboard (React)
│           ├── __init__.py
│           ├── app.py                 # 前端入口
│           ├── static/                # 构建产物
│           ├── components/
│           │   ├── Dashboard.tsx
│           │   ├── Market.tsx
│           │   ├── ServerDetail.tsx
│           │   ├── LogViewer.tsx
│           │   ├── StatusBadge.tsx
│           │   └── ...
│           └── pages/
│               ├── index.html
│               ├── market.html
│               └── server.html
│
├── tests/
│   ├── __init__.py
│   ├── test_cli_search.py
│   ├── test_cli_install.py
│   ├── test_cli_manage.py
│   ├── test_api_market.py
│   ├── test_api_manage.py
│   ├── test_api_publish.py
│   ├── test_registry.py
│   ├── test_process_manager.py
│   ├── test_health_check.py
│   ├── test_installer.py
│   └── test_security_scanner.py
│
└── data/
    ├── servers.db                     # SQLite 数据库
    └── logs/                          # 日志目录
```

---

## 八、开发路线图

### Phase 1: MVP（第 1-5 周）

**目标**：可用的 CLI + 基础 Web Dashboard + 市场发现 + 社区功能原型

| 周 | 任务 | 交付物 |
|----|------|--------|
| W1 | 项目脚手架 + 数据库设计 + 预置 Server 索引 | 项目骨架 + seed data |
| W2 | `mcp search` / `mcp info` / `mcp install` / `mcp list` | 核心 CLI 发现+安装 |
| W3 | `mcp start/stop/restart/status/logs` + 进程管理引擎 | CLI 管理功能 |
| W4 | 三级健康检查 + 自动重启 + `mcp daemon` | 监控 + 守护进程 |
| W5 | 基础 Web Dashboard + `mcp login` + `mcp rate/review` | Web 界面 + 社区 |

**MVP 验收标准**：

- [ ] `pip install mcp-hub` → `mcp daemon start` 能跑起来
- [ ] `mcp search "web"` 能搜到 50+ 预置 Server
- [ ] `mcp install @anthropic/web-search` 能安装并自动配置
- [ ] `mcp start/stop/status` 能正确控制进程
- [ ] Server 异常后能在 30 秒内自动重启
- [ ] `mcp logs web-search -f` 能实时查看日志
- [ ] `mcp login` 能用 GitHub OAuth 登录
- [ ] `mcp rate @anthropic/web-search 5` 能评分
- [ ] Web Dashboard 能打开：总览 + 市场搜索 + Server 管理
- [ ] 所有预置 Server 详情页可查看

### Phase 2: 增强（第 6-8 周）

**目标**：版本管理 + 开发者发布 + 配置管理

| 周 | 任务 | 交付物 |
|----|------|--------|
| W6 | `mcp update/rollback` + 版本管理引擎 | 版本管理 |
| W7 | `mcp config` + 配置环境切换 + `mcp config export/import` | 配置管理 |
| W7 | Web Dashboard 增强（配置编辑、日志在线查看） | 增强 Web |
| W8 | `mcp publish` + 安全扫描引擎 | 开发者发布 |
| W8 | `mcp trending/top-rated/most-downloaded/new-releases` | 排行榜 |

### Phase 3: 生态（第 9-12 周）

**目标**：事件总线 + 安全沙箱 + IDE 集成

| 周 | 任务 | 交付物 |
|----|------|--------|
| W9 | 事件总线（Pub/Sub）+ `mcp event` | 事件系统 |
| W9 | 远程 Registry 同步 + Server 元数据自动更新 | 社区 Registry |
| W10 | 安全沙箱（资源限制、隔离）+ `security_level` 标签 | 安全机制 |
| W10 | Server 统计 (`mcp stats`) + 排行榜算法优化 | 数据驱动 |
| W11 | VS Code Extension 集成 | IDE 插件 |
| W12 | 文档完善 + 发布策略 + 社区渠道搭建 | 社区运营 |

---

## 九、面试价值

### 9.1 面试官为什么看重这个项目

| 维度 | 展示的能力 | 面试官心理 |
|------|------------|-----------|
| **协议深度** | 对 MCP 协议的理解是设计者级别而非调用者级别 | "这人懂底层协议" |
| **平台思维** | 不是造轮子，是造"管理轮子的平台" | "抽象层次比同龄人高" |
| **生态敏感度** | 看到了 MCP 生态空白并验证了需求 | "有产品嗅觉" |
| **全栈工程** | CLI + API + DB + 进程管理 + Web + CI/CD | "一个人顶一个团队" |
| **社区运营** | 开源 + 排行榜 + 评分 + 发布流程 | "还具备社区能力" |
| **安全意识** | 安全审查 + 沙箱 + 分级认证 | "有生产安全意识" |
| **差异化** | 10 个候选人 8 个做 RAG Chatbot，极少人做 MCP 平台 | "这人有差异化" |

### 9.2 高频追问及回答框架

#### Q1: MCP 协议的通信模型是什么？Hub 如何与 Agent 交互？

> MCP 使用 **JSON-RPC 2.0** 协议，支持 **stdio** 和 **SSE** 两种传输层
>
> Hub 的角色是**代理层**：
> 1. Hub 通过 stdio 启动 Server 子进程，建立 JSON-RPC 通道
> 2. Hub 自身也暴露一个 MCP Server 接口，提供 `list_servers`、`search_servers` 等工具
> 3. Agent 配置 `mcp.json` 指向 Hub 的 stdio 入口，Agent 调用 Hub 像调用普通 Server 一样
> 4. Hub 将请求路由到目标 Server，聚合返回
>
> 这种设计的优点是：Agent 零改造，只要支持 MCP 就能用 Hub。

#### Q2: 市场（Marketplace）和运行时管理为什么放在一个产品里？

> 因为这两者的**用户是同一批人**，使用场景是**连续流程**：
>
> 用户在市场上发现一个 Server → 想试用 → 需要安装 → 装了需要管理 → 管理时需要看状态和日志
>
> 如果把发现和管理拆成两个产品，用户就要在市场和 Dashboard 之间来回切换。一体化之后：
> - 市场页面可以直接管理已安装的 Server（启动/停止）
> - Dashboard 可以直接跳转到市场搜索新 Server
> - 发布者可以同时看到自己 Server 的社区评价和运行数据
>
> 类比：App Store 和 iOS 设置是同一个生态，不是两个公司做的。

#### Q3: 如何做 Server 的发现？为什么不用已有的包管理器？

> 三层发现机制：
>
> 1. **本地索引**：安装时携带预置 Server 列表（50+ 热门），离线可用
> 2. **远程 Registry**：定期从 Hub 官方 Registry 同步最新数据
> 3. **社区提交**：开发者通过 `mcp publish` 提交到 Registry
>
> 包管理器（pip/npm）的核心问题是：
> - pip/npm 管的是代码包，不是 MCP Server（有运行时语义）
> - 包管理器没有进程管理、健康检查、自动配置
> - 用户需要的不是 `pip install xxx`，而是"我想让 Agent 能搜索网页，装一个能用的 Server"

#### Q4: Server 热插拔怎么实现？

> `mcp start server-a` → Process Manager spawn 子进程 → 建立 JSON-RPC 管道 → L1/L2/L3 健康检查通过 → 注册到 Hub 内部路由表
>
> `mcp stop server-a` → 发送 SIGTERM（优雅关闭）→ 等待 5 秒 → SIGKILL（强制）→ 从路由表移除
>
> Hub 本身是一个特殊的 MCP Server，Agent 通过 Hub 发现所有已注册 Server。新 Server 启动后，Agent 下次调用 Hub 的 `list_tools` 时自动感知。

#### Q5: 如何防止恶意 Server？

> 三层防御：
>
> **安装前**：自动安全扫描（依赖 CVE、网络权限评估、可疑代码检测）→ 分配安全标签（verified/reviewed/unreviewed/blocked）
>
> **运行时**：子进程隔离 + 资源限制（CPU 配额、内存上限）+ 文件系统沙箱 + 网络访问控制
>
> **监控时**：异常行为检测（频繁调用、大量数据外发）+ 自动评分下降 → 社区举报机制
>
> 用户可以在市场搜索时过滤安全等级，比如只看 `verified` 的 Server。

#### Q6: 这个项目跟 npm 有什么区别？

> 核心区别：**npm 管的是"包"（静态代码），Hub 管的是"Server"（运行时进程）**
>
> MCP Server 需要 npm 不做的事：
> - 进程生命周期：启动、停止、重启、守护
> - 健康检查：周期性检测并自动恢复
> - Agent 配置注入：自动写到 mcp.json
> - 运行时监控：CPU、内存、响应时间
> - Server 间通信：事件总线
> - MCP 协议适配：JSON-RPC 管道
>
> 更贴切的类比：**Docker Hub + Docker Compose** —— Docker Hub 管镜像发现，Docker Compose 管容器编排。MCP Hub = Docker Hub + Docker Compose 二合一。

#### Q7: 一人开发 12 周能做完吗？怎么保证？

> **MVP 严格限范围**：前 5 周只做核心链路（发现→安装→管理→社区），不做锦上添花的功能
>
> **分阶段交付**：每个 Phase 结束时都有可演示的交付物，没做完的功能延后到下一阶段
>
> **功能优先级**：
> - P0（必须）：Search、Install、Start/Stop/Status、Logs、Daemon、Dashboard
> - P1（重要）：Update/Rollback、Config、Publish、Rate/Review
> - P2（锦上添花）：Event Bus、Security Sandbox、VS Code Extension
>
> P0 做完就是一个可用的产品，P2 没做完不影响核心价值。

#### Q8: 你的商业模式是什么？

> MVP 阶段完全开源免费，目标是最大化采用和社区贡献
>
> 后续商业化方向：
> - **企业版**：多用户、RBAC 权限、审计日志、私有 Registry
> - **安全认证**：官方的 Server 安全审计服务
> - **托管版**：SaaS 化 Registry + 团队协作
> - **赞助版**：Server 推广位（类似 Homebrew 的 `brew tap`）

---

## 十、开源与社区策略

### 10.1 开源协议

- **MIT 协议**，最大化社区采用
- 核心功能完全开源免费

### 10.2 社区建设

| 渠道 | 策略 |
|------|------|
| **GitHub** | 开源仓库，Issues + PR 驱动 |
| **X/Twitter** | 每日推荐一个好用的 MCP Server（"今日 MCP"系列） |
| **技术博客** | 每周一篇 MCP 生态分析 + Hub 开发日志 |
| **Discord** | 开发者社区，讨论 + 反馈 + 互助 |
| **Newsletter** | 每周推送：新收录 Server + 排行榜 + 生态动态 |

### 10.3 增长策略

- **开箱即用**：预置 50+ 热门 Server 索引
- **发现效应**："今日 MCP"系列帮助小众好用的 Server 获得曝光
- **价值量化**："用 Hub 之后，管理 Server 的时间从 30 分钟降到 1 分钟"
- **口碑传播**：开发者最信任开发者的推荐

---

## 十一、风险管理

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| MCP 协议快速变更 | 中 | 高 | 紧跟协议版本，抽象协议适配层 |
| 生态增长不及预期 | 低 | 高 | 有教育价值：学习 MCP 的最佳实践工具 |
| 大厂推出竞品 | 中 | 中 | 专注 DX 和社区，大厂难复制开发者文化 |
| 一人开发精力有限 | 高 | 中 | MVP 严格限范围，P0 做完就是可用产品 |
| Server 安装兼容性问题 | 中 | 中 | 动态适配不同安装方式，社区贡献兼容配置 |
| 安全审查准确性 | 低 | 高 | 分级标签 + 免责说明，不盲目打"安全"标签 |

---

<p align="center">
  <sub>2026 年 6 月 · MCP Server Hub v1.0 项目文档 · 集成市场发现 + 运行时管理 + 社区生态</sub>
</p>
