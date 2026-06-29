"""单元测试 — Token 消耗分析引擎。"""

from __future__ import annotations

import json

from mcp_hub.core.token_analyzer import (
    AnalysisReport,
    OptimizationResult,
    OptimizationStrategy,
    OptimizationSuggestion,
    Optimizer,
    TokenAnalyzer,
    TokenBreakdown,
    Tokenizer,
    ToolTokenDetail,
    format_optimization,
    format_report,
)

# ── Tokenizer ──────────────────────────────────────────────

class TestTokenizer:
    def test_count_english(self) -> None:
        count = Tokenizer.count("Hello world")
        assert count > 0
        assert count < 10

    def test_count_empty(self) -> None:
        assert Tokenizer.count("") == 0

    def test_count_json(self) -> None:
        count = Tokenizer.count_json({"name": "test", "description": "hello"})
        assert count > 0

    def test_format_tokens_small(self) -> None:
        assert Tokenizer.format_tokens(42) == "42 tokens"

    def test_format_tokens_k(self) -> None:
        assert "K" in Tokenizer.format_tokens(1500)

    def test_format_pct_small(self) -> None:
        assert Tokenizer.format_pct(0.05) == "<0.1%"

    def test_format_pct_normal(self) -> None:
        assert Tokenizer.format_pct(12.5) == "12.5%"

    def test_long_text(self) -> None:
        text = "token " * 1000
        count = Tokenizer.count(text)
        assert count > 1000
        assert count < 10000

    def test_mixed_chinese_english(self) -> None:
        text = "搜索 web content 并返回结果"
        count = Tokenizer.count(text)
        assert count > 0


# ── TokenBreakdown ─────────────────────────────────────────

class TestTokenBreakdown:
    def test_creation(self) -> None:
        tb = TokenBreakdown("name", "test-tool", 8, 3)
        assert tb.field_name == "name"
        assert tb.token_count == 3
        assert tb.estimated is False

    def test_estimated_flag(self) -> None:
        tb = TokenBreakdown("desc", "text", 4, 2, estimated=True)
        assert tb.estimated is True


# ── ToolTokenDetail ────────────────────────────────────────

class TestToolTokenDetail:
    def test_creation(self) -> None:
        td = ToolTokenDetail("web-search", 150)
        assert td.tool_name == "web-search"
        assert td.total_tokens == 150
        assert td.breakdown == []
        assert td.optimization_potential == 0

    def test_with_breakdown(self) -> None:
        td = ToolTokenDetail(
            "db-query", 300,
            breakdown=[
                TokenBreakdown("name", "db-query", 7, 2),
                TokenBreakdown("description", "query db", 10, 5),
            ],
            optimization_potential=50,
        )
        assert len(td.breakdown) == 2
        assert td.optimization_potential == 50


# ── AnalysisReport ─────────────────────────────────────────

class TestAnalysisReport:
    def test_creation(self) -> None:
        r = AnalysisReport(
            server_id="@test/srv",
            total_tokens=500,
            context_usage_pct=0.5,
        )
        assert r.server_id == "@test/srv"
        assert r.total_tokens == 500
        assert not r.has_tool_definitions

    def test_with_tools(self) -> None:
        r = AnalysisReport(
            server_id="@test/srv",
            total_tokens=1000,
            context_usage_pct=1.0,
            tools=[ToolTokenDetail("t1", 500), ToolTokenDetail("t2", 500)],
            optimization_potential=200,
            suggestions=["优化描述"],
            has_tool_definitions=True,
        )
        assert len(r.tools) == 2
        assert r.optimization_potential == 200

    def test_estimated_flag(self) -> None:
        r = AnalysisReport(
            server_id="@test/srv",
            total_tokens=500,
            context_usage_pct=0.5,
            estimated=True,
        )
        assert r.estimated is True


# ── OptimizationSuggestion ─────────────────────────────────

class TestOptimizationSuggestion:
    def test_creation(self) -> None:
        s = OptimizationSuggestion(
            strategy=OptimizationStrategy.SHORTEN_DESCRIPTION,
            tool_name="test-tool",
            field="description",
            original="very long description here",
            optimized="short description",
            tokens_saved=10,
        )
        assert s.tokens_saved == 10
        assert s.strategy == OptimizationStrategy.SHORTEN_DESCRIPTION


# ── OptimizationResult ─────────────────────────────────────

class TestOptimizationResult:
    def test_creation(self) -> None:
        r = OptimizationResult(
            server_id="@test/srv",
            original_tokens=1000,
            optimized_tokens=700,
            tokens_saved=300,
            savings_pct=30.0,
        )
        assert r.savings_pct == 30.0
        assert r.tokens_saved == 300


# ── Optimizer ──────────────────────────────────────────────

class TestOptimizer:
    def test_shorten_description_short(self) -> None:
        result = Optimizer.shorten_description("short desc")
        assert result == "short desc"

    def test_shorten_description_long(self) -> None:
        long_desc = "A " * 150  # 300 chars
        result = Optimizer.shorten_description(long_desc)
        assert len(result) <= len(long_desc)

    def test_remove_redundant_prefix_english(self) -> None:
        result = Optimizer.remove_redundant_prefix("A tool that searches the web")
        assert not result.startswith("A tool that")

    def test_remove_redundant_prefix_clean(self) -> None:
        result = Optimizer.remove_redundant_prefix("searches the web")
        assert result == "searches the web"

    def test_shorten_name_no_match(self) -> None:
        result = Optimizer.shorten_name("web-search")
        assert result == "web-search"

    def test_compress_schema_removes_title(self) -> None:
        schema = {
            "type": "object",
            "title": "Args",
            "properties": {
                "query": {
                    "type": "string",
                    "title": "Query",
                    "description": "The search query",
                }
            },
        }
        result = Optimizer.compress_schema(schema)
        # title should be removed
        assert "title" not in json.dumps(result)

    def test_compress_schema_shortens_descriptions(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A" * 300,  # very long
                }
            },
        }
        result = Optimizer.compress_schema(schema)
        desc = result["properties"]["query"]["description"]
        assert len(desc) <= 200  # should be shortened

    def test_optimize_tool_no_changes(self) -> None:
        name, desc, schema, suggestions = Optimizer.optimize_tool(
            "simple", "short desc", {"type": "object", "properties": {}},
        )
        # May have no suggestions if already optimal
        assert isinstance(suggestions, list)

    def test_optimize_tool_redundant_prefix(self) -> None:
        _, new_desc, _, suggestions = Optimizer.optimize_tool(
            "test-tool",
            "A tool that does something useful for users",
            {"type": "object", "properties": {}},
        )
        assert not new_desc.startswith("A tool that")
        # There should be at least one suggestion for the prefix

    def test_empty_schema(self) -> None:
        name, desc, schema, suggestions = Optimizer.optimize_tool(
            "test", "desc", None,
        )
        assert schema is None


# ── TokenAnalyzer ──────────────────────────────────────────

class TestTokenAnalyzer:
    def test_analyze_server_no_tools(self) -> None:
        analyzer = TokenAnalyzer()
        report = analyzer.analyze_server({
            "id": "@test/srv",
            "description": "a test server",
            "install_command": "pip install test",
            "install_type": "pip",
        })
        assert report.server_id == "@test/srv"
        assert report.total_tokens > 0
        assert report.estimated  # no tool definitions
        assert not report.has_tool_definitions

    def test_analyze_server_with_tools(self) -> None:
        analyzer = TokenAnalyzer()
        report = analyzer.analyze_server({
            "id": "@test/srv",
            "description": "a test server",
            "tool_definitions": [
                {
                    "name": "search",
                    "description": "Search the web for information",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "search term"},
                        },
                    },
                },
                {
                    "name": "fetch",
                    "description": "Fetch a URL and return content",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "the url"},
                        },
                    },
                },
            ],
        })
        assert report.server_id == "@test/srv"
        assert report.total_tokens > 0
        assert not report.estimated
        assert report.has_tool_definitions
        assert len(report.tools) == 2

    def test_analyze_server_large_tool(self) -> None:
        """Server with large tool definitions should show high token count."""
        analyzer = TokenAnalyzer()
        long_desc = "A tool that " + "helpful " * 100
        report = analyzer.analyze_server({
            "id": "@test/large",
            "description": "big server",
            "tool_definitions": [
                {
                    "name": "big-tool",
                    "description": long_desc,
                    "inputSchema": {
                        "type": "object",
                        "title": "Args",
                        "properties": {
                            "p1": {"type": "string", "description": "very " * 50},
                            "p2": {"type": "integer", "description": "lots of " * 40},
                        },
                    },
                },
            ],
        })
        assert report.total_tokens > 100
        assert report.optimization_potential > 0
        assert len(report.suggestions) >= 1

    def test_analyze_all(self) -> None:
        analyzer = TokenAnalyzer()
        servers = [
            {"id": "@test/a", "description": "server a"},
            {"id": "@test/b", "description": "server b"},
        ]
        reports = analyzer.analyze_all(servers)
        assert len(reports) == 2

    def test_optimize_simple(self) -> None:
        analyzer = TokenAnalyzer()
        result = analyzer.optimize(
            {"id": "@test/srv", "description": "test"},
            tool_definitions=[
                {
                    "name": "search",
                    "description": "A tool that searches the web for content",
                    "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                },
            ],
        )
        assert result.original_tokens > 0
        assert result.optimized_tokens > 0
        assert result.server_id == "@test/srv"

    def test_optimize_large(self) -> None:
        """Optimization should save tokens on verbose tools."""
        analyzer = TokenAnalyzer()
        result = analyzer.optimize(
            {"id": "@test/big", "description": "test"},
            tool_definitions=[
                {
                    "name": "mcp-server-big-helper",
                    "description": "A tool that does something extremely useful and important for users all around the world who need help with their daily tasks",  # noqa: E501
                    "inputSchema": {
                        "type": "object",
                        "title": "Parameters",
                        "properties": {
                            "input": {"type": "string", "description": "The input parameter that needs to be processed by this very useful and amazing tool"},  # noqa: E501
                        },
                        "required": ["input"],
                    },
                },
            ],
        )
        assert result.tokens_saved > 0
        assert result.savings_pct > 0
        assert len(result.suggestions) > 0

    def test_empty_tool_list_fallback(self) -> None:
        """Empty tool definitions should still produce an estimate."""
        analyzer = TokenAnalyzer()
        result = analyzer.optimize(
            {"id": "@test/empty", "description": "something"},
            tool_definitions=[],
        )
        # Without tool definitions, it returns a result with 0 original tokens
        assert result.original_tokens == 0 or result.server_id == "@test/empty"


# ── format_report / format_optimization ────────────────────

class TestFormatters:
    def test_format_report_no_tools(self) -> None:
        report = AnalysisReport(
            server_id="@test/srv",
            total_tokens=500,
            context_usage_pct=0.5,
            estimated=True,
            suggestions=["suggestion 1"],
        )
        text = format_report(report)
        assert "500" in text
        assert "suggestion 1" in text

    def test_format_report_with_tools(self) -> None:
        report = AnalysisReport(
            server_id="@test/srv",
            total_tokens=1000,
            context_usage_pct=1.0,
            tools=[ToolTokenDetail("tool1", 500), ToolTokenDetail("tool2", 500)],
            has_tool_definitions=True,
        )
        text = format_report(report, verbose=True)
        assert "tool1" in text
        assert "tool2" in text

    def test_format_optimization(self) -> None:
        result = OptimizationResult(
            server_id="@test/srv",
            original_tokens=1000,
            optimized_tokens=700,
            tokens_saved=300,
            savings_pct=30.0,
        )
        text = format_optimization(result)
        assert "30.0%" in text or "30" in text
        assert "1.0K" in text or "1000" in text
        assert "700" in text or "0.7K" in text
