#!/usr/bin/env bash
# ============================================
# MCP Server Hub — 一键安装脚本
# 用法: curl -fsSL https://mcphub.cn/install.sh | bash
# 当前稳定版本通过 GitHub Tag 安装；PyPI 发布暂缓。
# ============================================
set -e

REPOSITORY="https://github.com/blankbrains/McpServerHub.git"
STABLE_TAG="v0.3.2"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔵 MCP Server Hub Installer${NC}"
echo ""

# Step 1: Install MCP Hub CLI
install_hub() {
    if ! command -v uv &>/dev/null; then
        echo -e "${RED}❌ 需要 uv。请先安装: https://docs.astral.sh/uv/${NC}"
        exit 1
    fi

    echo -e "${YELLOW}📦 正在从 ${STABLE_TAG} 安装 MCP Hub CLI...${NC}"
    uv tool install --force "git+${REPOSITORY}@${STABLE_TAG}"
    uv tool update-shell
    echo -e "${GREEN}✅ MCP Hub CLI 安装成功 ($(mcp-hub --version 2>/dev/null || echo "请重新打开终端后运行 mcp-hub --version"))${NC}"
}

install_hub

echo ""
echo -e "${BLUE}🔵 MCP Server Hub — 安装完成${NC}"
echo "   接入现有 Hub: mcp-hub agent setup --agent <agent> --hub-url <url> --telemetry-token <token>"
echo "   完整文档: https://github.com/blankbrains/McpServerHub/blob/main/deploy/install.md"
