"""Token 分析 API。"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_hub.core.registry import Registry
from mcp_hub.core.token_analyzer import TokenAnalyzer
from mcp_hub.exceptions import ServerNotFoundError

router = APIRouter(tags=["tokens"])


@router.get("/tokens/analyze/{server_id:path}")
async def analyze_tokens(server_id: str):
    """分析指定 Server 的 Token 消耗。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    analyzer = TokenAnalyzer()
    report = analyzer.analyze_server(server)

    return {
        "success": True,
        "data": {
            "server_id": report.server_id,
            "total_tokens": report.total_tokens,
            "context_usage_pct": report.context_usage_pct,
            "tool_count": len(report.tools),
            "optimization_potential": report.optimization_potential,
            "estimated": report.estimated,
            "has_tool_definitions": report.has_tool_definitions,
            "suggestions": report.suggestions,
            "tools": [
                {
                    "name": t.tool_name,
                    "tokens": t.total_tokens,
                    "optimization_potential": t.optimization_potential,
                    "breakdown": {
                        b.field_name: {"tokens": b.token_count, "chars": b.char_count}
                        for b in t.breakdown
                    },
                }
                for t in report.tools
            ],
        },
    }


@router.post("/tokens/optimize/{server_id:path}")
async def optimize_tokens(server_id: str):
    """生成指定 Server 的优化后配置。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    analyzer = TokenAnalyzer()
    result = analyzer.optimize(server)

    return {
        "success": True,
        "data": {
            "server_id": result.server_id,
            "original_tokens": result.original_tokens,
            "optimized_tokens": result.optimized_tokens,
            "tokens_saved": result.tokens_saved,
            "savings_pct": result.savings_pct,
            "optimized_definition": result.optimized_definition,
        },
    }
