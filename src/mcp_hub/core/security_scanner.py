"""MCP Server 安全评分引擎。

四维评分体系:
  1. CommandAnalyzer   (40分) — 安装命令安全性
  2. PackageChecker    (25分) — npm/PyPI 包信誉
  3. ReputationChecker (20分) — 发布者可信度
  4. CodePatternChecker(15分) — 代码危险模式检测

等级:
  verified   (90-100) — 安全可信
  reviewed   (70-89)  — 需复核
  unreviewed (40-69)  — 未审计，谨慎使用
  blocked    (0-39)   — 危险，阻止安装
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from mcp_hub.models.server import SecurityLevel

# ── 常量 ───────────────────────────────────────────────────

KNOWN_OFFICIAL_AUTHORS = {"anthropic", "openai", "google", "github", "vercel", "cloudflare"}
VERIFIED_COMMUNITY_AUTHORS = {
    "modelcontextprotocol",
    "puppeteer",
    "sentry",
    "datadog",
    "elastic",
    "mongodb",
    "neo4j",
    "docker",
    "supabase",
    "railway",
}

# 最高危模式 — 直接 shell 注入 / 远程代码执行
CRITICAL_PATTERNS = [
    (r"curl\s+.+?\|\s*(?:bash|sh|zsh)", "从网络下载并执行脚本"),
    (r"wget\s+.+?\|\s*(?:bash|sh|zsh)", "从网络下载并执行脚本"),
    (r"base64\s*-d.*?\|.*?(?:bash|sh)", "解码并执行 base64 内容"),
    (r"eval\s*\(", "动态执行代码"),
    (r"exec\s*\(", "动态执行代码"),
    (r"__import__\s*\(", "动态导入模块"),
]

# 高危模式 — 绕过安全检查
HIGH_RISK_PATTERNS = [
    (r"npm\s+install.*--ignore-scripts", "忽略安装脚本安全检查"),
    (r"npm\s+install.*--no-verify", "跳过 npm 安全验证"),
    (r"pip\s+install.*--no-verify", "跳过 pip 安全验证"),
    (r"--unsafe-perm", "以不安全权限运行"),
]

# 可疑模式 — 需要关注
SUSPICIOUS_PATTERNS = [
    (r"os\.system\s*\(", "调用系统命令"),
    (r"subprocess\.(?:call|Popen|run|check_output)\s*\(", "运行子进程"),
    (r"requests?\.get\s*\(", "发起网络请求"),
    (r"urllib\.request", "发起网络请求"),
    (r"open\(.*['\"].*\.(?:env|key|cert|pem|secret)['\"].*\)", "访问敏感文件"),
    (r"tempfile|NamedTemporaryFile", "创建临时文件"),
    (r"chmod\s+.*777", "设置不安全文件权限"),
    (r"(?:/tmp|/var/tmp)", "使用临时目录"),
]


# ── 数据结构 ───────────────────────────────────────────────


@dataclass
class ScanFinding:
    """单个发现项。"""
    severity: str  # critical / high / suspicious / info
    category: str  # command / package / reputation / code
    title: str
    description: str
    score_impact: int  # 负值表示扣分


@dataclass
class ScanReport:
    """完整扫描报告。"""
    server_id: str
    level: SecurityLevel
    score: int  # 0-100
    findings: list[ScanFinding] = field(default_factory=list)
    network_access: bool = False
    file_access: bool = False
    scanned_at: str = ""

    def score_breakdown(self) -> dict[str, int]:
        """返回每个维度的扣分明细。"""
        breakdown = {
            "command_safety": 40,
            "package_reputation": 25,
            "publisher_trust": 20,
            "code_patterns": 15,
        }
        for f in self.findings:
            if f.category == "command" and f.score_impact < 0:
                breakdown["command_safety"] += f.score_impact
            elif f.category == "package" and f.score_impact < 0:
                breakdown["package_reputation"] += f.score_impact
            elif f.category == "reputation" and f.score_impact < 0:
                breakdown["publisher_trust"] += f.score_impact
            elif f.category == "code" and f.score_impact < 0:
                breakdown["code_patterns"] += f.score_impact
        # clamp to 0
        for k in breakdown:
            breakdown[k] = max(0, breakdown[k])
        return breakdown


# ── 各检测模块 ─────────────────────────────────────────────


class CommandAnalyzer:
    """检测安装命令是否安全。"""

    def analyze(self, install_command: str, install_type: str) -> list[ScanFinding]:
        findings: list[ScanFinding] = []
        if not install_command:
            return findings

        # 检查高危模式
        for pattern, desc in CRITICAL_PATTERNS:
            if re.search(pattern, install_command, re.IGNORECASE):
                findings.append(ScanFinding(
                    severity="critical",
                    category="command",
                    title=f"检测到危险模式: {desc}",
                    description=f"安装命令 '{install_command[:80]}' 包含 '{pattern}'",
                    score_impact=-40,
                ))

        # 检查高危模式
        for pattern, desc in HIGH_RISK_PATTERNS:
            if re.search(pattern, install_command, re.IGNORECASE):
                findings.append(ScanFinding(
                    severity="high",
                    category="command",
                    title=f"绕过安全机制: {desc}",
                    description=f"安装命令 '{install_command[:80]}' 包含 '{pattern}'",
                    score_impact=-20,
                ))

        # 检查可疑模式
        for pattern, desc in SUSPICIOUS_PATTERNS:
            if re.search(pattern, install_command, re.IGNORECASE):
                findings.append(ScanFinding(
                    severity="suspicious",
                    category="command",
                    title=f"可疑操作: {desc}",
                    description=f"安装命令 '{install_command[:80]}' 包含 '{pattern}'",
                    score_impact=-10,
                ))

        # 按安装类型检测
        if install_type == "pip":
            if "/" in install_command and "@" not in install_command.split("/")[0]:
                findings.append(ScanFinding(
                    severity="suspicious",
                    category="command",
                    title="从直接 URL 安装 pip 包",
                    description=f"pip 从非 PyPI 源直接安装: {install_command[:80]}",
                    score_impact=-8,
                ))
        elif install_type == "npm":
            if "npm" in install_command and not install_command.startswith("npx"):
                findings.append(ScanFinding(
                    severity="suspicious",
                    category="command",
                    title="全局安装 npm 包",
                    description=f"npm install 可能导致全局污染: {install_command[:80]}",
                    score_impact=-5,
                ))
        elif install_type == "docker":
            # Docker 安装一般需要网络和系统权限
            findings.append(ScanFinding(
                severity="suspicious",
                category="command",
                title="Docker 安装",
                description="Docker 容器需要网络和系统级访问",
                score_impact=-15,
            ))

        return findings


class PackageChecker:
    """检查 npm/PyPI 包的元数据信誉。"""

    async def check(self, install_command: str, install_type: str) -> list[ScanFinding]:
        findings: list[ScanFinding] = []
        if not install_command:
            return findings

        # 提取包名
        package_name = self._extract_package_name(install_command, install_type)
        if not package_name:
            return findings

        if install_type in ("npm", "npx"):
            npm_findings = await self._check_npm(package_name)
            findings.extend(npm_findings)
        elif install_type == "pip":
            pypi_findings = await self._check_pypi(package_name)
            findings.extend(pypi_findings)

        return findings

    def _extract_package_name(self, command: str, install_type: str) -> str | None:
        """从安装命令中提取包名。"""
        parts = command.split()
        if install_type in ("npx",):
            # npx -y @org/package 或 npx @org/package
            for p in parts:
                if p.startswith("@"):
                    return p
            # 最后一个参数通常是包名
            if parts and not parts[-1].startswith("-"):
                return parts[-1]
        elif install_type == "npm":
            for p in parts:
                if p.startswith("@") or (not p.startswith("-") and p != "npm" and p != "install"):
                    return p
        elif install_type == "pip":
            for p in parts:
                if p != "pip" and p != "install" and not p.startswith("-") and p != "--upgrade":
                    return p
        elif install_type == "uvx":
            for p in parts:
                if not p.startswith("-") and p != "uvx":
                    return p
        return None

    async def _check_npm(self, package: str) -> list[ScanFinding]:
        """检查 npm 包的信誉。"""
        findings: list[ScanFinding] = []
        # 对 @org/pkg 格式的处理
        url_pkg = package.replace("@", "%40") if package.startswith("@") else package

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://registry.npmjs.org/{url_pkg}/latest",
                )
                if resp.status_code != 200:
                    return findings

                data = resp.json()
                version = data.get("version", "")
                # 获取完整包信息以检查发布时间等
                full_resp = await client.get(
                    f"https://registry.npmjs.org/{url_pkg}",
                )
                if full_resp.status_code == 200:
                    full_data = full_resp.json()

                    # 检查包发布时间
                    time_data = full_data.get("time", {})
                    first_release = time_data.get(version, "") or list(time_data.values())[0] if time_data else ""  # noqa: E501
                    if first_release:
                        try:
                            release_date = datetime.fromisoformat(first_release.replace("Z", "+00:00"))  # noqa: E501
                            age_days = (datetime.now(timezone.utc) - release_date).days
                            if age_days < 30:
                                findings.append(ScanFinding(
                                    severity="high",
                                    category="package",
                                    title="包发布时间不足 30 天",
                                    description=f"npm 包 '{package}' 发布于 {age_days} 天前，风险较高",  # noqa: E501
                                    score_impact=-15,
                                ))
                            elif age_days > 365:
                                findings.append(ScanFinding(
                                    severity="info",
                                    category="package",
                                    title="包已发布超过 1 年",
                                    description=f"npm 包 '{package}' 已发布 {age_days} 天，相对成熟",  # noqa: E501
                                    score_impact=5,
                                ))
                        except (ValueError, IndexError):
                            pass

                    # 检查版本数量（越多越成熟）
                    versions = len(full_data.get("versions", {}))
                    if versions >= 10:
                        findings.append(ScanFinding(
                            severity="info",
                            category="package",
                            title="版本历史丰富",
                            description=f"npm 包 '{package}' 有 {versions} 个版本",
                            score_impact=5,
                        ))
                    elif versions == 1:
                        findings.append(ScanFinding(
                            severity="suspicious",
                            category="package",
                            title="只有一个版本",
                            description=f"npm 包 '{package}' 只有 1 个版本",
                            score_impact=-8,
                        ))

                    # 检查维护者数量
                    maintainers = full_data.get("maintainers", [])
                    if len(maintainers) >= 3:
                        findings.append(ScanFinding(
                            severity="info",
                            category="package",
                            title="多维护者",
                            description=f"npm 包 '{package}' 有 {len(maintainers)} 位维护者",
                            score_impact=5,
                        ))

        except (httpx.TimeoutException, httpx.RequestError):
            findings.append(ScanFinding(
                severity="info",
                category="package",
                title="无法连接 npm 注册表",
                description=f"无法获取 npm 包 '{package}' 的元数据",
                score_impact=0,
            ))
        except Exception:
            pass

        return findings

    async def _check_pypi(self, package: str) -> list[ScanFinding]:
        """检查 PyPI 包的信誉。"""
        findings: list[ScanFinding] = []

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://pypi.org/pypi/{package}/json",
                )
                if resp.status_code != 200:
                    return findings

                data = resp.json()
                info = data.get("info", {})

                # 检查发布时间
                release_date_str = info.get("release_date", "")
                if not release_date_str:
                    # 从版本历史获取
                    releases = data.get("releases", {})
                    all_dates = []
                    for _ver, files in releases.items():
                        for f in files:
                            upload_time = f.get("upload_time", "")
                            if upload_time:
                                all_dates.append(upload_time)
                    if all_dates:
                        all_dates.sort()
                        release_date_str = all_dates[0]

                if release_date_str:
                    try:
                        release_date = datetime.fromisoformat(release_date_str.replace("Z", "+00:00"))  # noqa
                        age_days = (datetime.now(timezone.utc) - release_date).days
                        if age_days < 30:
                            findings.append(ScanFinding(
                                severity="high",
                                category="package",
                                title="包发布时间不足 30 天",
                                description=f"PyPI 包 '{package}' 发布于 {age_days} 天前",
                                score_impact=-15,
                            ))
                        elif age_days > 365:
                            findings.append(ScanFinding(
                                severity="info",
                                category="package",
                                title="包已发布超过 1 年",
                                description=f"PyPI 包 '{package}' 已发布 {age_days} 天",
                                score_impact=5,
                            ))
                    except (ValueError, IndexError):
                        pass

        except (httpx.TimeoutException, httpx.RequestError):
            findings.append(ScanFinding(
                severity="info",
                category="package",
                title="无法连接 PyPI 注册表",
                description=f"无法获取 PyPI 包 '{package}' 的元数据",
                score_impact=0,
            ))
        except Exception:
            pass

        return findings


class ReputationChecker:
    """评估发布者的可信度。"""

    def check(
        self,
        author: str,
        _install_command: str = "",
        _publisher_type: str = "individual",
        publisher_verified: bool = False,
    ) -> list[ScanFinding]:
        findings: list[ScanFinding] = []

        if not author:
            findings.append(ScanFinding(
                severity="suspicious",
                category="reputation",
                title="无发布者信息",
                description="Server 没有发布者信息，来源不明",
                score_impact=-10,
            ))
            return findings

        author_lower = author.lower()

        if author_lower in KNOWN_OFFICIAL_AUTHORS:
            findings.append(ScanFinding(
                severity="info",
                category="reputation",
                title="官方发布者",
                description=f"{author} 是官方认证发布者",
                score_impact=20,
            ))
        elif author_lower in VERIFIED_COMMUNITY_AUTHORS:
            findings.append(ScanFinding(
                severity="info",
                category="reputation",
                title="已验证社区发布者",
                description=f"{author} 是已知的社区发布者",
                score_impact=10,
            ))
        elif publisher_verified:
            findings.append(ScanFinding(
                severity="info",
                category="reputation",
                title="已验证发布者",
                description=f"{author} 已经过平台验证",
                score_impact=10,
            ))
        else:
            # 检查发布者是否是 GitHub 组织
            if "/" in author and not author.startswith("@"):
                findings.append(ScanFinding(
                    severity="info",
                    category="reputation",
                    title="组织级发布者",
                    description=f"{author} 可能来自组织账号",
                    score_impact=5,
                ))
            else:
                findings.append(ScanFinding(
                    severity="suspicious",
                    category="reputation",
                    title="未知发布者",
                    description=f"{author} 不是已知的发布者，需要谨慎",
                    score_impact=-5,
                ))

        return findings


class CodePatternChecker:
    """检测描述/元数据中的危险代码模式。"""

    def check(self, description: str, _tags: list[str], homepage: str) -> list[ScanFinding]:
        findings: list[ScanFinding] = []
        desc_lower = (description or "").lower()

        # 检查网络访问
        network_keywords = ["web", "api", "http", "search", "network", "fetch", "download"]
        if any(w in desc_lower for w in network_keywords):
            findings.append(ScanFinding(
                severity="suspicious",
                category="code",
                title="Server 需要网络访问",
                description="描述中包含网络相关关键词",
                score_impact=-5,
            ))

        # 检查文件访问
        file_keywords = ["file", "filesystem", "fs ", "read", "write", "create", "delete"]
        if any(w in desc_lower for w in file_keywords):
            findings.append(ScanFinding(
                severity="suspicious",
                category="code",
                title="Server 需要文件系统访问",
                description="描述中包含文件操作相关关键词",
                score_impact=-5,
            ))

        # 检查 homePage 是否有效
        if homepage:
            if not homepage.startswith(("https://", "http://")):
                findings.append(ScanFinding(
                    severity="suspicious",
                    category="code",
                    title="主页 URL 异常",
                    description=f"主页 '{homepage}' 不是有效的 URL",
                    score_impact=-3,
                ))
            elif "github.com" not in homepage and "gitlab.com" not in homepage:
                findings.append(ScanFinding(
                    severity="info",
                    category="code",
                    title="非 GitHub 托管",
                    description="主页不在 GitHub 上，代码透明度较低",
                    score_impact=-3,
                ))
        else:
            findings.append(ScanFinding(
                severity="suspicious",
                category="code",
                title="无主页信息",
                description="Server 没有提供主页，来源难以追溯",
                score_impact=-5,
            ))

        return findings


# ── 协调器 ─────────────────────────────────────────────────


class SecurityScanner:
    """安全评分引擎 —— 综合所有检测维度的评分器。"""

    def __init__(self) -> None:
        self.command_analyzer = CommandAnalyzer()
        self.package_checker = PackageChecker()
        self.reputation_checker = ReputationChecker()
        self.code_pattern_checker = CodePatternChecker()

    async def scan(self, server_data: dict) -> ScanReport:
        """对 Server 执行完整安全扫描。

        Args:
            server_data: Server 数据字典，至少包含 id, description, author,
                        install_command, install_type 等字段。

        Returns:
            包含评分、发现项和等级的 ScanReport。
        """
        server_id = server_data.get("id", "") or server_data.get("name", "unknown")
        install_command = server_data.get("install_command", "")
        install_type = server_data.get("install_type", "")

        # 1. 命令安全检测
        command_findings = self.command_analyzer.analyze(
            install_command, install_type
        )

        # 2. 包信誉检查
        package_findings = await self.package_checker.check(
            install_command, install_type
        )

        # 3. 发布者信誉检查
        reputation_findings = self.reputation_checker.check(
            server_data.get("author", ""),
            publisher_verified=server_data.get("publisher_verified", False),
        )

        # 4. 代码模式检测
        tags_raw = server_data.get("tags", [])
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags = []
        else:
            tags = tags_raw

        code_findings = self.code_pattern_checker.check(
            server_data.get("description", ""),
            tags,
            server_data.get("homepage", ""),
        )

        # 汇总所有发现
        all_findings = command_findings + package_findings + reputation_findings + code_findings

        # 计算总分
        score = self._calculate_score(all_findings)

        # 确定等级
        level = self._determine_level(score, server_data)

        # 网络/文件访问标记
        network_access = any(
            f.category == "code" and "network" in f.description
            for f in code_findings
        )
        file_access = any(
            f.category == "code" and "file" in f.description
            for f in code_findings
        )

        # 如果命令分析发现有网络相关操作
        if any("network" in str(f).lower() for f in command_findings):
            network_access = True
        if install_type == "docker":
            network_access = True
            file_access = True

        return ScanReport(
            server_id=server_id,
            level=level,
            score=score,
            findings=all_findings,
            network_access=network_access,
            file_access=file_access,
            scanned_at=datetime.now(timezone.utc).isoformat(),
        )

    def _calculate_score(self, findings: list[ScanFinding]) -> int:
        """从 100 分开始，根据发现项扣分/加分。"""
        score = 100
        for f in findings:
            score += f.score_impact
        return max(0, min(100, score))

    def _determine_level(self, score: int, _server_data: dict) -> SecurityLevel:
        """根据分数和元数据确定安全等级。"""
        # 如果分数极低，直接 blocked
        if score < 50:
            return "blocked"
        # 官方发布者自动更高
        if score >= 90:
            return "verified"
        elif score >= 70:
            return "reviewed"
        else:
            return "unreviewed"

    @staticmethod
    def format_report(report: ScanReport, verbose: bool = False) -> str:
        """格式化扫描报告为可读文本（用于 CLI）。"""
        level_icons = {
            "verified": "🟢",
            "reviewed": "🟡",
            "unreviewed": "🟠",
            "blocked": "🔴",
        }
        icon = level_icons.get(report.level, "❓")
        lines = [
            f"\n{icon}  安全评分: {report.score}/100 — {report.level}",
            f"  Server: {report.server_id}",
        ]

        if report.findings:
            sev_counts = {}
            for f in report.findings:
                sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1
            lines.append(f"  发现: {len(report.findings)} 项问题")
            lines.append(
                f"    critical: {sev_counts.get('critical', 0)}  "
                f"high: {sev_counts.get('high', 0)}  "
                f"suspicious: {sev_counts.get('suspicious', 0)}  "
                f"info: {sev_counts.get('info', 0)}"
            )

            if verbose and report.findings:
                lines.append("")
                for f in report.findings:
                    sev_icon = {"critical": "🔴", "high": "🟠", "suspicious": "🟡", "info": "ℹ️"}
                    lines.append(f"  {sev_icon.get(f.severity, '•')} [{f.severity}] {f.title}")
                    lines.append(f"     {f.description}")
                    lines.append(f"     影响: {f.score_impact:+d} 分 | 类别: {f.category}")

        lines.append("")
        return "\n".join(lines)
