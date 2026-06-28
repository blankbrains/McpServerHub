#!/usr/bin/env bash
# ============================================
# MCP Server Hub — 一键安装脚本
# 用法: curl -fsSL https://mcphub.cn/install.sh | bash
# 用法（指定 Server）:
#   curl -fsSL https://mcphub.cn/install.sh | bash -s -- @modelcontextprotocol/server-filesystem
# ============================================
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SERVER_ID="${1:-}"

echo -e "${BLUE}🔵 MCP Server Hub Installer${NC}"
echo ""

# Step 1: Check Python
check_python() {
    if command -v python3 &>/dev/null; then
        echo -e "${GREEN}✅ Python: $(python3 --version)${NC}"
        return 0
    fi
    echo -e "${RED}❌ 需要 Python 3.10+，请先安装: https://python.org${NC}"
    exit 1
}

# Step 2: Install MCP Hub CLI
install_hub() {
    if command -v mcp &>/dev/null; then
        echo -e "${GREEN}✅ MCP Hub 已安装 (mcp $(mcp --version 2>/dev/null || echo ""))${NC}"
        return 0
    fi

    echo -e "${YELLOW}📦 正在安装 MCP Hub CLI...${NC}"

    # Try pip first
    if command -v pip3 &>/dev/null; then
        pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple mcp-hub 2>/dev/null ||
        pip3 install mcp-hub 2>/dev/null && {
            echo -e "${GREEN}✅ MCP Hub CLI 安装成功${NC}"
            return 0
        }
    fi

    # Fallback: pipx
    if command -v pipx &>/dev/null; then
        pipx install mcp-hub && {
            echo -e "${GREEN}✅ MCP Hub CLI 安装成功 (via pipx)${NC}"
            return 0
        }
    fi

    # Fallback: uv
    if command -v uv &>/dev/null; then
        uv pip install mcp-hub && {
            echo -e "${GREEN}✅ MCP Hub CLI 安装成功 (via uv)${NC}"
            return 0
        }
    fi

    echo -e "${RED}❌ 安装失败。请手动安装: pip install mcp-hub${NC}"
    exit 1
}

# Step 3: Install MCP Server
install_server() {
    if [ -z "$SERVER_ID" ]; then
        echo ""
        echo -e "${BLUE}📋 MCP Hub 已就绪！${NC}"
        echo "   使用方式:"
        echo "   mcp search              # 搜索 MCP Server"
        echo "   mcp install @org/server # 安装 Server"
        echo "   mcp start server-name   # 启动"
        echo "   mcp serve               # 启动 MCP 网关"
        echo ""
        echo -e "${YELLOW}或者直接安装推荐 Server:${NC}"
        echo "   curl -fsSL https://mcphub.cn/install.sh | bash -s -- @modelcontextprotocol/server-filesystem"
        return 0
    fi

    echo -e "${YELLOW}📦 正在安装 ${SERVER_ID}...${NC}"

    # 先注册 Server（如果 Hub 市场里没有）
    mcp install "$SERVER_ID" 2>/dev/null && {
        echo -e "${GREEN}✅ ${SERVER_ID} 安装成功！${NC}"
    } || {
        # 如果 Hub 市场里没有，用 npx 直接装
        echo -e "${YELLOW}   尝试直接 npx 安装...${NC}"
        local pkg_name="${SERVER_ID#@}"
        pkg_name="${pkg_name%/server-*}"
        local npx_cmd="npx -y ${SERVER_ID}"
        echo ""
        echo -e "${BLUE}📋 请将以下配置添加到你的 claude_desktop_config.json:${NC}"
        echo ""
        echo '  "mcpServers": {'
        echo "    \"$(basename ${SERVER_ID})\": {"
        echo "      \"command\": \"npx\","
        echo "      \"args\": [\"-y\", \"${SERVER_ID}\"]"
        echo "    }"
        echo "  }"
        echo ""
        echo -e "${GREEN}✅ 配置已生成，复制到本机即可使用${NC}"
    }
}

# ============================================

check_python
install_hub
install_server

echo ""
echo -e "${BLUE}🔵 MCP Server Hub — 安装完成${NC}"
echo "   文档: https://mcphub.cn"
