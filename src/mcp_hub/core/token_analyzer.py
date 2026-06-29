"""MCP Server Token 消耗分析引擎。

分析 MCP Server 的工具定义占用 Claude 上下文（100K tokens）多大比例，
并提供优化建议以减少 Token 消耗。

关键数据（2026年调研）:
  - 工具定义可占上下文窗口的 16%
  - GitHub 官方 MCP 消耗 55,000 tokens
  - 简单的 Markdown 文件仅需 200 tokens
  - 平均每条工具描述可优化 30-70%

注意事项:
  - Claude 使用自己的 tokenizer (未开源)，这里用 tiktoken cl100k_base 近似
  - cl100k_base 对英文的压缩率 ~1.7 chars/token，对中文 ~1.2 chars/token
  - 实际 Claude token 数可能偏差 ±15%，但相对比较价值很高
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ── 尝试加载 tiktoken，失败则用字符估计 ──────────────────

_TOKENIZER = None
_TOKENIZER_WARNING_SHOWN = False

try:
    import tiktoken
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    pass


# ── 常量 ───────────────────────────────────────────────────

# Claude 模型的上下文窗口大小（标准模型）
CONTEXT_WINDOW_SIZE = 100_000

# 行业基准数据（来自 2026 年 MCP 生态调研）
AVG_TOOL_DESC_TOKENS = 85        # 平均每个工具描述的 token 数
AVG_TOOL_PARAM_SCHEMA_TOKENS = 120  # 平均每个工具参数 Schema 的 token 数
AVG_TOOLS_PER_SERVER = 5         # 平均每个 Server 的工具数
AVG_SERVER_TOTAL_TOKENS = 1025   # 平均每个 Server 的完整工具定义 token 数
MAX_SAFE_TOOL_PCT = 16           # 所有工具定义不应超过上下文的 16%

# 优化策略
NAME_REDUNDANT_PREFIXES = [
    r"^mcp[-_]server[-_]", r"^server[-_]", r"^tool[-_]",
    r"^mcp[-_]", r"^ai[-_]",
]

DESC_REDUNDANT_PREFIXES = [
    "A tool that ", "A function that ", "A utility that ",
    "A helper that ", "This tool ", "This function ",
    "Tool for ", "Function for ", "Utility for ",
    "用来", "一个用于", "这是一个",
]

DESC_OPTIMAL_MAX_LENGTH = 200
PARAM_DESC_OPTIMAL_MAX_LENGTH = 100


# ── 数据结构 ───────────────────────────────────────────────


class OptimizationStrategy(Enum):
    """优化策略类型。"""
    SHORTEN_DESCRIPTION = "shorten_description"
    REMOVE_REDUNDANT_PREFIX = "remove_redundant_prefix"
    SHORTEN_PARAM_DESC = "shorten_param_desc"
    COMPRESS_SCHEMA = "compress_schema"
    MERGE_TOOLS = "merge_tools"


@dataclass
class TokenBreakdown:
    """单个字段的 Token 明细。"""
    field_name: str
    raw_text: str
    char_count: int
    token_count: int
    estimated: bool = False  # True 表示估算值


@dataclass
class ToolTokenDetail:
    """单个工具的 Token 消耗详情。"""
    tool_name: str
    total_tokens: int
    breakdown: list[TokenBreakdown] = field(default_factory=list)
    optimization_potential: int = 0  # 可节省的 token 数


@dataclass
class AnalysisReport:
    """完整分析报告。"""
    server_id: str
    total_tokens: int
    context_usage_pct: float  # 占上下文窗口百分比
    tools: list[ToolTokenDetail] = field(default_factory=list)
    optimization_potential: int = 0
    suggestions: list[str] = field(default_factory=list)
    estimated: bool = False
    has_tool_definitions: bool = False
    comparison_note: str = ""


@dataclass
class OptimizationSuggestion:
    """单条优化建议。"""
    strategy: OptimizationStrategy
    tool_name: str
    field: str
    original: str
    optimized: str
    tokens_saved: int


@dataclass
class OptimizationResult:
    """优化结果。"""
    server_id: str
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    savings_pct: float
    suggestions: list[OptimizationSuggestion] = field(default_factory=list)
    optimized_definition: str = ""


# ── Tokenizer ──────────────────────────────────────────────


class Tokenizer:
    """统一的 Token 计数接口。"""

    @staticmethod
    def count(text: str) -> int:
        """统计文本的 token 数。

        使用 tiktoken cl100k_base 精确计数，不可用时用字符估算。
        """
        global _TOKENIZER_WARNING_SHOWN
        if _TOKENIZER is not None:
            return len(_TOKENIZER.encode(text))
        # 字符估算：中文约 1.2 chars/token，英文约 1.7 chars/token
        char_count = len(text)
        # 简单启发：中文比例越高，chars/token 越低
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        ratio = 1.2 if chinese_chars > len(text) * 0.3 else 1.7
        if not _TOKENIZER_WARNING_SHOWN:
            import warnings
            warnings.warn("tiktoken 未安装，使用字符估算模式（精度较低）", stacklevel=2)
            _TOKENIZER_WARNING_SHOWN = True
        return max(1, int(char_count / ratio))

    @staticmethod
    def count_json(obj: Any) -> int:
        """统计 JSON 序列化后的 token 数。"""
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        return Tokenizer.count(text)

    @staticmethod
    def format_tokens(count: int) -> str:
        """格式化 token 数为人类可读字符串。"""
        if count < 1000:
            return f"{count} tokens"
        elif count < 100000:
            return f"{count / 1000:.1f}K tokens"
        else:
            return f"{count / 1000:.0f}K tokens"

    @staticmethod
    def format_pct(pct: float) -> str:
        """格式化百分比。"""
        if pct < 0.1:
            return "<0.1%"
        return f"{pct:.1f}%"


# ── 优化引擎 ──────────────────────────────────────────────


class Optimizer:
    """工具描述优化引擎。"""

    @staticmethod
    def shorten_description(desc: str, max_length: int = DESC_OPTIMAL_MAX_LENGTH) -> str:
        """缩短过长的描述。"""
        if len(desc) <= max_length:
            return desc
        # 在最后一个完整句号处截断
        truncated = desc[:max_length]
        last_period = truncated.rfind("。")
        if last_period > max_length * 0.5:
            return truncated[:last_period + 1]
        last_dot = truncated.rfind(". ")
        if last_dot > max_length * 0.5:
            return truncated[:last_dot + 1]
        return truncated + "..."

    @staticmethod
    def remove_redundant_prefix(desc: str) -> str:
        """移除描述中的冗余前缀。"""
        for prefix in DESC_REDUNDANT_PREFIXES:
            if desc.startswith(prefix):
                # 首字母小写（英文）
                rest = desc[len(prefix):]
                if rest and rest[0].isupper():
                    rest = rest[0].lower() + rest[1:]
                return rest
        return desc

    @staticmethod
    def shorten_name(name: str) -> str:
        """缩短工具名中的冗余前缀。"""
        for pattern in NAME_REDUNDANT_PREFIXES:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)
        return name

    @staticmethod
    def compress_schema(schema: dict) -> dict:
        """压缩 JSON Schema（移除冗余字段）。"""
        compressed = {}
        for key, value in schema.items():
            if key == "title":
                continue  # title 在 MCP 上下文中冗余
            if key == "description" and isinstance(value, str):
                compressed[key] = Optimizer.shorten_description(
                    Optimizer.remove_redundant_prefix(value),
                    PARAM_DESC_OPTIMAL_MAX_LENGTH,
                )
                continue
            if isinstance(value, dict):
                compressed[key] = Optimizer.compress_schema(value)
            elif isinstance(value, list):
                compressed[key] = [
                    Optimizer.compress_schema(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                compressed[key] = value
        return compressed

    @staticmethod
    def optimize_tool(name: str, description: str, input_schema: dict | None) -> tuple[str, str, dict | None, list[OptimizationSuggestion]]:  # noqa: E501
        """优化单个工具定义，返回 (优化后的name, 优化后的description, 优化后的schema, 建议列表)。"""
        suggestions: list[OptimizationSuggestion] = []
        old_name = name
        old_desc = description

        # 1. 缩短名称
        new_name = Optimizer.shorten_name(name)
        if new_name != old_name:
            saved = Tokenizer.count(old_name) - Tokenizer.count(new_name)
            suggestions.append(OptimizationSuggestion(
                strategy=OptimizationStrategy.REMOVE_REDUNDANT_PREFIX,
                tool_name=name,
                field="name",
                original=old_name,
                optimized=new_name,
                tokens_saved=max(1, saved),
            ))

        # 2. 移除冗余前缀
        new_desc = Optimizer.remove_redundant_prefix(description)
        if new_desc != old_desc:
            saved = Tokenizer.count(old_desc) - Tokenizer.count(new_desc)
            suggestions.append(OptimizationSuggestion(
                strategy=OptimizationStrategy.REMOVE_REDUNDANT_PREFIX,
                tool_name=name,
                field="description",
                original=old_desc[:100] + "..." if len(old_desc) > 100 else old_desc,
                optimized=new_desc[:100] + "..." if len(new_desc) > 100 else new_desc,
                tokens_saved=max(1, saved),
            ))

        # 3. 缩短过长描述
        shorter_desc = Optimizer.shorten_description(new_desc)
        if shorter_desc != new_desc:
            saved = Tokenizer.count(new_desc) - Tokenizer.count(shorter_desc)
            suggestions.append(OptimizationSuggestion(
                strategy=OptimizationStrategy.SHORTEN_DESCRIPTION,
                tool_name=name,
                field="description",
                original=new_desc[:100] + "..." if len(new_desc) > 100 else new_desc,
                optimized=shorter_desc[:100] + "..." if len(shorter_desc) > 100 else shorter_desc,
                tokens_saved=max(1, saved),
            ))
            new_desc = shorter_desc

        # 4. 压缩 Schema
        new_schema = None
        if input_schema:
            compressed = Optimizer.compress_schema(input_schema)
            old_schema_str = json.dumps(input_schema, ensure_ascii=False, separators=(",", ":"))
            new_schema_str = json.dumps(compressed, ensure_ascii=False, separators=(",", ":"))
            if new_schema_str != old_schema_str:
                saved = Tokenizer.count(old_schema_str) - Tokenizer.count(new_schema_str)
                if saved > 0:
                    suggestions.append(OptimizationSuggestion(
                        strategy=OptimizationStrategy.COMPRESS_SCHEMA,
                        tool_name=name,
                        field="input_schema",
                        original=f"schema ({Tokenizer.count(old_schema_str)} tokens)",
                        optimized=f"schema ({Tokenizer.count(new_schema_str)} tokens)",
                        tokens_saved=saved,
                    ))
                    new_schema = compressed
                else:
                    new_schema = input_schema
            else:
                new_schema = input_schema

        return new_name, new_desc, new_schema, suggestions


# ── 分析引擎 ──────────────────────────────────────────────


class TokenAnalyzer:
    """Token 消耗分析引擎。"""

    def __init__(self) -> None:
        self.tokenizer = Tokenizer()
        self.optimizer = Optimizer()

    # ── 公共接口 ──────────────────────────────────────────

    def analyze_server(self, server_data: dict) -> AnalysisReport:
        """分析单个 Server 的 Token 消耗。

        Args:
            server_data: Server 数据字典，可包含 tool_definitions 字段（可选）。

        Returns:
            包含完整 token 消耗分析的 AnalysisReport。
        """
        server_id = server_data.get("id", "") or server_data.get("name", "unknown")

        # 检查是否有实际的工具定义
        tool_defs = self._extract_tool_definitions(server_data)
        has_tool_defs = len(tool_defs) > 0

        if has_tool_defs:
            return self._analyze_with_definitions(server_id, tool_defs, server_data)
        else:
            return self._estimate_from_metadata(server_id, server_data)

    def analyze_all(self, servers: list[dict]) -> list[AnalysisReport]:
        """批量分析多个 Server。"""
        return [self.analyze_server(s) for s in servers]

    def optimize(  # noqa: PLR0912
        self,
        server_data: dict,
        tool_definitions: list[dict] | None = None,
    ) -> OptimizationResult:
        """生成 Server 的优化后工具定义。

        Args:
            server_data: Server 数据。
            tool_definitions: 可选的实际工具定义列表。

        Returns:
            包含优化前后对比和节省量的 OptimizationResult。
        """
        server_id = server_data.get("id", "") or server_data.get("name", "unknown")
        tools = tool_definitions or self._extract_tool_definitions(server_data)

        all_suggestions: list[OptimizationSuggestion] = []
        optimized_tools: list[dict] = []
        original_total = 0
        optimized_total = 0

        for tool in tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            input_schema = tool.get("inputSchema") or tool.get("input_schema", {})

            # 原始 token 数
            original_tool_str = json.dumps({
                "name": name,
                "description": description,
                "input_schema": input_schema,
            }, ensure_ascii=False, separators=(",", ":"))
            original_total += Tokenizer.count(original_tool_str)

            # 优化
            new_name, new_desc, new_schema, suggestions = self.optimizer.optimize_tool(
                name, description, input_schema,
            )
            all_suggestions.extend(suggestions)

            optimized_tool = {
                "name": new_name,
                "description": new_desc,
            }
            if new_schema:
                optimized_tool["input_schema"] = new_schema

            # 优化后 token 数
            opt_str = json.dumps(optimized_tool, ensure_ascii=False, separators=(",", ":"))
            optimized_total += Tokenizer.count(opt_str)

        tokens_saved = original_total - optimized_total
        savings_pct = (tokens_saved / original_total * 100) if original_total > 0 else 0

        return OptimizationResult(
            server_id=server_id,
            original_tokens=original_total,
            optimized_tokens=optimized_total,
            tokens_saved=max(0, tokens_saved),
            savings_pct=max(0, savings_pct),
            suggestions=all_suggestions,
            optimized_definition=json.dumps({
                "mcpServers": {server_id: {"tools": optimized_tools}},
            }, ensure_ascii=False, indent=2),
        )

    # ── 内部方法 ──────────────────────────────────────────

    def _extract_tool_definitions(self, server_data: dict) -> list[dict]:
        """从 server_data 中提取工具定义列表。"""
        # 尝试多种可能的字段名
        for key in ("tool_definitions", "tools", "tools_list", "tool_list"):
            val = server_data.get(key)
            if val and isinstance(val, list) and len(val) > 0:
                return val

        # 尝试从 install_command 和描述生成样例工具
        return []

    def _analyze_with_definitions(
        self,
        server_id: str,
        tool_defs: list[dict],
        server_data: dict,
    ) -> AnalysisReport:
        """使用实际的工具定义进行分析。"""
        tools_detail: list[ToolTokenDetail] = []
        total_tokens = 0
        total_optimization = 0

        for tool in tool_defs:
            name = tool.get("name", "unknown")
            description = tool.get("description", "")
            input_schema = tool.get("inputSchema") or tool.get("input_schema", {})

            breakdown: list[TokenBreakdown] = []

            # name
            name_tokens = Tokenizer.count(name)
            breakdown.append(TokenBreakdown("name", name, len(name), name_tokens))

            # description
            desc_tokens = Tokenizer.count(description)
            breakdown.append(TokenBreakdown("description", description, len(description), desc_tokens))  # noqa: E501

            # input_schema
            schema_str = json.dumps(input_schema, ensure_ascii=False) if input_schema else "{}"
            schema_tokens = Tokenizer.count(schema_str)
            breakdown.append(TokenBreakdown("input_schema", schema_str, len(schema_str), schema_tokens))  # noqa: E501

            # 检查描述是否可优化
            tool_opt = 0
            if len(description) > DESC_OPTIMAL_MAX_LENGTH:
                extra = desc_tokens - Tokenizer.count(
                    Optimizer.shorten_description(description)
                )
                tool_opt += max(0, extra)
            if any(description.startswith(p) for p in DESC_REDUNDANT_PREFIXES):
                tool_opt += desc_tokens // 4  # 估计可省 25%
            if input_schema and "title" in str(input_schema):
                tool_opt += schema_tokens // 10  # 压缩 Schema

            tool_total = name_tokens + desc_tokens + schema_tokens
            detail = ToolTokenDetail(
                tool_name=name,
                total_tokens=tool_total,
                breakdown=breakdown,
                optimization_potential=tool_opt,
            )
            tools_detail.append(detail)
            total_tokens += tool_total
            total_optimization += tool_opt

        context_pct = total_tokens / CONTEXT_WINDOW_SIZE * 100

        # 生成建议
        suggestions = self._generate_suggestions(
            server_id, total_tokens, context_pct, tools_detail, server_data,
        )

        # 与行业平均对比
        avg_tokens = AVG_TOOLS_PER_SERVER * (AVG_TOOL_DESC_TOKENS + AVG_TOOL_PARAM_SCHEMA_TOKENS)
        comparison = ""
        if total_tokens > avg_tokens * 1.5:
            comparison = f"🔺 高于同类 Server 平均（{Tokenizer.format_tokens(avg_tokens)}），建议优化"  # noqa: E501
        elif total_tokens < avg_tokens * 0.5:
            comparison = f"✅ 低于同类 Server 平均（{Tokenizer.format_tokens(avg_tokens)}），工具定义精简"  # noqa: E501
        else:
            comparison = f"📊 与同类 Server 平均水平相当（{Tokenizer.format_tokens(avg_tokens)}）"

        return AnalysisReport(
            server_id=server_id,
            total_tokens=total_tokens,
            context_usage_pct=context_pct,
            tools=tools_detail,
            optimization_potential=total_optimization,
            suggestions=suggestions,
            estimated=False,
            has_tool_definitions=True,
            comparison_note=comparison,
        )

    def _estimate_from_metadata(
        self,
        server_id: str,
        server_data: dict,
    ) -> AnalysisReport:
        """根据元数据估算 Token 消耗。"""
        description = server_data.get("description", "")
        install_command = server_data.get("install_command", "")
        install_type = server_data.get("install_type", "")

        # 根据安装类型和描述估算工具数量
        estimated_tools = self._estimate_tool_count(description, install_command, install_type)
        # 根据描述长度估算每个工具的复杂度
        desc_complexity = len(description) / 100  # 每100个描述字符多一个工具
        tool_count = max(1, int(estimated_tools + desc_complexity))

        # 估算每个工具的 token 消耗
        per_tool_desc_tokens = Tokenizer.count(description[:200]) if description else AVG_TOOL_DESC_TOKENS  # noqa: E501
        per_tool_schema_tokens = AVG_TOOL_PARAM_SCHEMA_TOKENS

        # 生成样例工具
        tools_detail: list[ToolTokenDetail] = []
        for i in range(min(tool_count, 10)):  # 最多展示 10 个
            tool_name = f"tool_{i + 1}"
            tool_desc = f"{description[:50]} - operation {i + 1}" if description else f"tool {i + 1}"  # noqa: E501
            tool_total = per_tool_desc_tokens + per_tool_schema_tokens

            tools_detail.append(ToolTokenDetail(
                tool_name=tool_name,
                total_tokens=tool_total,
                breakdown=[
                    TokenBreakdown("name", tool_name, len(tool_name), Tokenizer.count(tool_name), estimated=True),  # noqa: E501
                    TokenBreakdown("description", tool_desc, len(tool_desc), per_tool_desc_tokens, estimated=True),  # noqa: E501
                    TokenBreakdown("input_schema", "{}", 2, per_tool_schema_tokens, estimated=True),
                ],
                optimization_potential=int(per_tool_desc_tokens * 0.3),  # 估算优化潜力
            ))

        total_tokens = sum(t.total_tokens for t in tools_detail)
        context_pct = total_tokens / CONTEXT_WINDOW_SIZE * 100

        suggestions = [
            "💡 安装此 Server 并运行 `mcp analyze --live <server>` 获取精确 token 数据",
            "💡 此分析为估算值，实际消耗取决于 Server 暴露的具体工具",
        ]

        return AnalysisReport(
            server_id=server_id,
            total_tokens=total_tokens,
            context_usage_pct=context_pct,
            tools=tools_detail,
            optimization_potential=int(total_tokens * 0.3),
            suggestions=suggestions,
            estimated=True,
            has_tool_definitions=False,
            comparison_note="📊 基于元数据的估算值（非实际工具定义）",
        )

    def _estimate_tool_count(
        self,
        description: str,
        _install_command: str,
        install_type: str,
    ) -> int:
        """根据元数据估算 Server 的工具数量。"""
        desc_lower = description.lower()
        count = AVG_TOOLS_PER_SERVER  # 默认 5

        # 大型框架类的 Server 通常暴露更多工具
        if any(kw in desc_lower for kw in ["platform", "framework", "suite", "all-in-one"]):
            count += 5
        if any(kw in desc_lower for kw in ["database", "db ", "sql", "query"]):
            count += 3
        if any(kw in desc_lower for kw in ["file", "filesystem", "storage"]):
            count += 2
        if any(kw in desc_lower for kw in ["search", "web", "browser"]):
            count += 1

        # npm 包通常工具更多
        if install_type in ("npm", "npx"):
            count += 1

        return min(count, 20)  # 上限 20

    def _generate_suggestions(
        self,
        server_id: str,
        total_tokens: int,
        context_pct: float,
        tools: list[ToolTokenDetail],
        _server_data: dict,
    ) -> list[str]:
        """根据分析结果生成优化建议。"""
        suggestions: list[str] = []

        # 1. 上下文占比建议
        if context_pct > MAX_SAFE_TOOL_PCT:
            suggestions.append(
                f"⚠️  工具定义占用 {context_pct:.1f}% 上下文，超过建议的 {MAX_SAFE_TOOL_PCT}%"
            )
        elif context_pct > 10:
            suggestions.append(
                f"📝 工具定义占用 {context_pct:.1f}% 上下文，处于中等水平"
            )
        else:
            suggestions.append(
                f"✅ 工具定义占用 {context_pct:.1f}% 上下文，控制在健康范围内"
            )

        # 2. 单个工具描述过长
        for tool in tools:
            for b in tool.breakdown:
                if b.field_name == "description" and len(b.raw_text) > DESC_OPTIMAL_MAX_LENGTH:
                    suggestions.append(
                        f"✂️  '{tool.tool_name}' 描述过长（{len(b.raw_text)} 字符, {b.token_count} tokens），"  # noqa: E501
                        f"建议控制在 {DESC_OPTIMAL_MAX_LENGTH} 字符以内"
                    )

        # 3. 冗余前缀
        for tool in tools:
            for b in tool.breakdown:
                if b.field_name == "description":
                    for prefix in DESC_REDUNDANT_PREFIXES:
                        if b.raw_text.startswith(prefix):
                            suggestions.append(
                                f"🗑️  '{tool.tool_name}' 描述包含冗余前缀「{prefix}」，可移除节省 token"  # noqa: E501
                            )
                            break

        # 4. 优化潜力
        if total_tokens > 0:
            opt_pct = (sum(t.optimization_potential for t in tools) / total_tokens) * 100
            if opt_pct > 20:
                suggestions.append(
                    f"🎯 预估优化潜力 {opt_pct:.0f}%，可使用 mcp optimize {server_id} 查看具体建议"
                )

        # 5. 多工具建议
        if len(tools) > 15:
            suggestions.append(
                f"📦 此 Server 暴露了大量工具（{len(tools)} 个），建议按场景只启用需要的工具"
            )

        return suggestions


# ── 格式化器 ──────────────────────────────────────────────


def format_report(report: AnalysisReport, verbose: bool = False) -> str:
    """格式化分析报告为可读文本。"""
    lines: list[str] = []
    server_id = report.server_id.split("/")[-1] if "/" in report.server_id else report.server_id

    # 标题行
    estimated_tag = " (估算)" if report.estimated else ""
    lines.append(f"\n📊 Token 消耗分析: {server_id}{estimated_tag}")
    lines.append("─" * 60)

    # 总览
    lines.append(f"  总计:        {Tokenizer.format_tokens(report.total_tokens):>10}")
    lines.append(f"  上下文占比:  {Tokenizer.format_pct(report.context_usage_pct):>10}")
    lines.append(f"  工具数量:    {len(report.tools):>10}")
    lines.append(f"  优化潜力:    {Tokenizer.format_tokens(report.optimization_potential):>10}")
    lines.append(f"  对比:        {report.comparison_note}")

    # 工具明细
    if verbose and report.tools:
        lines.append("")
        lines.append(f"  {'工具名称':<30} {'Token':>6} {'描述':>6} {'Schema':>6} {'节省':>6}")
        lines.append("  " + "─" * 60)
        for tool in sorted(report.tools, key=lambda t: t.total_tokens, reverse=True):
            desc_t = next((b.token_count for b in tool.breakdown if b.field_name == "description"), 0)  # noqa: E501
            schema_t = next((b.token_count for b in tool.breakdown if b.field_name == "input_schema"), 0)  # noqa: E501
            opt = tool.optimization_potential
            lines.append(
                f"  {tool.tool_name[:28]:<30} {tool.total_tokens:>5} "
                f"{desc_t:>5} {schema_t:>5} {f'+{opt}' if opt > 0 else '-':>5}"
            )

    # 建议
    if report.suggestions:
        lines.append("")
        lines.append("  📋 建议:")
        for s in report.suggestions:
            lines.append(f"    {s}")

    # 如果只有估算，显示实际测量的方法
    if report.estimated:
        lines.append("")
        lines.append("  💡 提示: 安装此 Server 后运行 mcp analyze --deep <server> 获取精确分析")

    lines.append("")
    return "\n".join(lines)


def format_optimization(result: OptimizationResult) -> str:
    """格式化优化结果为可读文本。"""
    lines: list[str] = []
    server_id = result.server_id.split("/")[-1] if "/" in result.server_id else result.server_id

    lines.append(f"\n🔧 优化建议: {server_id}")
    lines.append("─" * 60)
    lines.append(f"  优化前:  {Tokenizer.format_tokens(result.original_tokens):>10}")
    lines.append(f"  优化后:  {Tokenizer.format_tokens(result.optimized_tokens):>10}")
    lines.append(f"  节省:    {Tokenizer.format_tokens(result.tokens_saved):>10}")
    lines.append(f"  节省率:  {result.savings_pct:.1f}%")

    if result.suggestions:
        lines.append("")
        lines.append("  📋 具体优化项:")
        for s in result.suggestions:
            lines.append(f"    [{s.strategy.value}] 节省 {s.tokens_saved} tokens")
            lines.append(f"      {s.tool_name}/{s.field}")
            lines.append(f"      原: {s.original[:60]}...")
            lines.append(f"      新: {s.optimized[:60]}...")

    if result.optimized_definition:
        lines.append("")
        lines.append("  📝 优化后的配置 (mcp optimize --apply 可写入):")
        # 只显示前 500 字符
        truncated = result.optimized_definition[:500]
        lines.append(f"  {truncated}")

    lines.append("")
    return "\n".join(lines)
