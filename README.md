<div align="center">

# <svg width="40" height="40" viewBox="0 0 64 64" style="vertical-align:middle"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#3B82F6"/><stop offset="100%" stop-color="#8B5CF6"/></linearGradient></defs><circle cx="32" cy="32" r="30" fill="url(#g)"/><text x="32" y="34" text-anchor="middle" fill="white" font-size="24" font-weight="700" font-family="system-ui,sans-serif">M</text></svg> MCP Server Hub

**The missing platform for the MCP ecosystem**

Discover · Install · Manage · Publish · Community

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-316192?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![React 19](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/badge/dynamic/json?style=flat-square&label=stars&query=stargazers_count&url=https%3A%2F%2Fapi.github.com%2Frepos%2Fblankbrains%2FMcpServerHub)](https://github.com/blankbrains/McpServerHub)

---

<p align="center">
  <b>970+ MCP Servers</b> · <b>36 CLI commands</b> · <b>16 categories</b> · <b>20 tags</b><br>
  Search → Install → Auto-configure → Manage. One platform.
</p>

</div>

---

## 🤔 The Problem

MCP (Model Context Protocol) is exploding — 400+ servers, 100k+ stars, adopted by every major AI platform. But the user experience is stuck in 2015:

```
👎 Find a server     → GitHub blind search, no ratings, no comparison
👎 Install           → Manual README → pip install → hand-write JSON config
👎 Manage            → No unified process manager, no health checks
👎 Monitor           → Crashes? No idea. Logs? Scattered everywhere.
👎 Publish           → No registry, no discovery, no community
```

**MCP Server Hub fixes all of this.**

---

## ✨ What It Does

```
🏪 MARKETPLACE        ⚡ INSTALL              ⚙️ MANAGE              👥 PUBLISH
┌──────────┐         ┌──────────┐            ┌──────────┐           ┌──────────┐
│ Search   │  ──→   │ One-line │    ──→     │ Process  │   ──→    │ 1-Click  │
│ Browse   │         │ Auto-Cfg │            │ Health   │           │ Registry │
│ Compare  │         │ Versions │            │ Logs     │           │ Ratings  │
│ Rate     │         │ Rollback │            │ Auto-Heal│           │ Stats    │
└──────────┘         └──────────┘            └──────────┘           └──────────┘
                          │                       │
                          └─────── 🔗 MCP Gateway ───────┘
                          Single stdio entry for Claude Code/Cursor
                          One config file. All servers auto-discovered.
```

---

## 🚀 Quick Start

### 1. Install

```bash
pip install mcp-hub
```

<details>
<summary><b>🐳 Or use Docker</b></summary>

```bash
git clone https://github.com/your-org/mcp-hub
cd mcp-hub
docker-compose up -d
# Open http://localhost:3987
```
</details>

### 2. Initialize

```bash
mcp init
```

This sets up PostgreSQL, creates tables, seeds 10+ real MCP servers, configures auto-start.

### 3. Start

```bash
mcp daemon start
# Dashboard: http://localhost:3987
```

---

## 🎮 Usage

### 🔍 Search & Compare

```bash
# Browse the marketplace
mcp search

# Search by keyword
mcp search database
mcp search web --category browser

# Compare two servers
mcp compare @modelcontextprotocol/server-postgres @modelcontextprotocol/server-sqlite

# View details
mcp info @modelcontextprotocol/server-filesystem
```

### 📦 Install & Run

```bash
# One command installs + auto-configures
mcp install @modelcontextprotocol/server-filesystem

# Manage the process
mcp start server-filesystem
mcp status
mcp logs server-filesystem -f
mcp stop server-filesystem
```

### 🔌 Connect to Claude Code

Add this single entry to `claude_desktop_config.json`:

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

**Any server you install through Hub is automatically available** in Claude Code. No more manual JSON editing for each server.

### 🌐 Web Dashboard

```
http://localhost:3987
```

Real-time monitoring, live logs, search, install, and management — all from your browser.

---

## 📋 Full Command Reference

```
Usage: mcp [OPTIONS] COMMAND [ARGS]...

🛒  Market
  search [query]       Search MCP Servers
  info <server>        Server details  
  compare <a> <b>      Compare two servers

📦  Installation
  install <server>     Install a server (auto-configures)
  uninstall <server>   Uninstall
  list                 List installed servers

⚙️  Management
  start <server>       Start a server
  stop <server>        Stop a server
  restart <server>     Restart a server
  status [server]      Show status
  logs <server>        Tail logs (-f for follow)
  update [server]      Check/apply updates
  rollback <server>    Rollback version
  config               Manage server config

🔧  System
  daemon start         Start Hub service
  daemon stop          Stop Hub service
  daemon status        Hub status
  serve                Start MCP gateway (stdio)
  init                 One-time initialization

👤  Auth
  login                GitHub login
  logout               Logout
  whoami               Current user

📤  Publish
  publish <path>       Publish your server
  my-servers           Your published servers
  unpublish <server>   Unpublish
  stats <server>       Usage statistics

⭐  Community
  rate <srv> <n>       Rate (1-5)
  review <srv>         Write/view reviews
  favorite <srv>       Add to favorites
  favorites            Your favorites
  trending             Trending servers
  top-rated            Top rated
  most-downloaded      Most downloaded
  new-releases         New releases

📡  Events
  event publish        Publish event
  event subscribe      Subscribe to event
```

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────┐
│                    User Interfaces                     │
│    ┌──────────┐        ┌──────────┐    ┌──────────┐  │
│    │   CLI    │        │ Web Dash │    │ MCP stdio│  │
│    │ (Rich)   │        │ (React)  │    │ (Gateway)│  │
│    └────┬─────┘        └────┬─────┘    └────┬─────┘  │
├─────────┼───────────────────┼───────────────┼────────┤
│         │                   │               │        │
│         ▼                   ▼               ▼        │
│    ┌────────────────────────────────────────────┐    │
│    │          FastAPI + Core Services           │    │
│    │  ┌─────────┐ ┌──────────┐ ┌─────────────┐ │    │
│    │  │Registry │ │Process   │ │MCP Gateway  │ │    │
│    │  │         │ │Manager   │ │(Aggregator) │ │    │
│    │  ├─────────┤ ├──────────┤ ├─────────────┤ │    │
│    │  │Installer│ │Health    │ │Event Bus    │ │    │
│    │  │         │ │Checker   │ │(Pub/Sub)    │ │    │
│    │  └─────────┘ └──────────┘ └─────────────┘ │    │
│    └────────────────────┬───────────────────────┘    │
│                         │                           │
│                         ▼                           │
│              ┌─────────────────────┐                │
│              │ PostgreSQL 16+      │                │
│              │ (asyncpg, SQLAlchemy│                │
│              │  2.0 async ORM)     │                │
│              └─────────────────────┘                │
└──────────────────────────────────────────────────────┘
```

---

## 🛠 Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Runtime** | Python 3.10+ | Universal, async-native |
| **API** | FastAPI + uvicorn | High-performance async |
| **Database** | PostgreSQL 16+ | Production-grade, asyncpg |
| **ORM** | SQLAlchemy 2.0 | Mature async ORM |
| **CLI** | Click + Rich | Beautiful terminal output |
| **Frontend** | React 19 + Tailwind | Modern, fast, responsive |
| **Build** | Vite | Instant HMR, optimized builds |
| **Protocol** | MCP (JSON-RPC 2.0) | Industry standard |
| **Auth** | GitHub OAuth + JWT | Zero external deps |

---

## 📊 Project Status

**Current: Alpha** — Active development, APIs may change.

| Phase | Status | What |
|-------|--------|------|
| ✅ P0 | **Complete** | MCP protocol gateway (aggregate all servers) |
| ✅ P1 | **Complete** | `mcp init`, Docker, PyPI-ready |
| ✅ P2 | **Complete** | Dashboard: SSE logs, real-time status |
| ✅ P3 | **Complete** | CLI: Rich tables, spinners, colors |
| ✅ P4 | **Complete** | Tests (9/9), GitHub Actions CI |
| ✅ P5 | **Complete** | English docs, CONTRIBUTING, PyPI metadata |

---

## 🗺 Roadmap

- [ ] **Hub SDK** — Python/JS SDK for building MCP Servers
- [ ] **VS Code Extension** — Manage servers from your editor
- [ ] **Team Features** — Multi-user, RBAC, audit logs
- [ ] **Remote Registry** — Cloud sync for your server collection
- [ ] **Docker Sandbox** — Run servers in isolated containers
- [ ] **Performance Dashboard** — Latency, error rates, usage analytics

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

- 🐛 Found a bug? [Open an issue](https://github.com/your-org/mcp-hub/issues)
- 💡 Have an idea? [Start a discussion](https://github.com/your-org/mcp-hub/discussions)
- 🔧 Want to contribute? Check out our [good first issues](https://github.com/your-org/mcp-hub/contribute)

---

## 📄 License

MIT © 2026 McpServerHub

---

<div align="center">
  <sub>Built with ❤️ for the MCP community</sub>
</div>
