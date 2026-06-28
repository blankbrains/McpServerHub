"""为 MCP Server 生成图标 + 翻译描述。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re

import httpx
from sqlalchemy import select

from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import ServerModel

# ========== 图标生成 ==========

# 调色板 — 根据名字 hash 选颜色
COLORS = [
    "#4F46E5", "#059669", "#D97706", "#DC2626", "#7C3AED",
    "#0284C7", "#0891B2", "#65A30D", "#9333EA", "#E11D48",
    "#2563EB", "#0D9488", "#CA8A04", "#EA580C", "#A21CAF",
    "#1D4ED8", "#0F766E", "#B45309", "#B91C1C", "#6D28D9",
]


def _pick_color(name: str) -> str:
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return COLORS[h % len(COLORS)]


def _generate_svg_icon(name: str) -> str:
    """生成首个字母的 SVG 图标，返回 data URL。"""
    letter = name.strip()[0].upper() if name.strip() else "?"
    color = _pick_color(name)
    # 根据字母宽度调整字号
    font_size = 36 if letter in "MW" else 42 if letter in "ABDOPQR" else 48

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" rx="12" fill="{color}"/>'
        f'<text x="32" y="32" text-anchor="middle" dominant-baseline="central" '
        f'fill="white" font-size="{font_size}" font-weight="bold" '
        f'font-family="-apple-system,BlinkMacSystemFont,sans-serif">{letter}</text>'
        f'</svg>'
    )
    b64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"


async def generate_icons() -> int:
    """为没有图标的 Server 生成图标。"""
    async with async_session_factory() as session:
        result = await session.execute(select(ServerModel).where(ServerModel.icon_url.is_(None)))
        servers = result.scalars().all()
        count = 0

        for s in servers:
            name = s.display_name or s.name or s.id
            s.icon_url = _generate_svg_icon(name)
            count += 1

        await session.commit()
    return count


# ========== 描述翻译 ==========

# 支持的语言代码检测
_ZH_PATTERN = re.compile(r"[一-鿿]")
_EN_PATTERN = re.compile(r"[a-zA-Z]{4,}")


def _needs_translation(desc: str) -> bool:
    """判断描述是否需要翻译（非中文且有英文内容）。"""
    if not desc or len(desc) < 10:
        return False
    if _ZH_PATTERN.search(desc):
        return False  # 已有中文
    return bool(_EN_PATTERN.search(desc))


async def translate_descriptions() -> int:
    """批量翻译英文描述为中文。"""
    # 简化翻译：常见技术术语的中文映射
    _glossary = {
        "server": "服务",
        "integration": "集成",
        "management": "管理",
        "automation": "自动化",
        "analysis": "分析",
        "monitoring": "监控",
        "database": "数据库",
        "search": "搜索",
        "API": "接口",
        "tool": "工具",
        "client": "客户端",
        "interface": "接口",
        "framework": "框架",
        "library": "库",
        "plugin": "插件",
        "extension": "扩展",
        "wrapper": "封装",
        "connector": "连接器",
        "bridge": "桥接",
        "gateway": "网关",
    }

    # 简单本地翻译（不需要调外部 API）
    def _simple_translate(text: str) -> str:
        """对描述做简单的中文翻译。"""
        # 处理常见模式
        if text.startswith("A ") or text.startswith("An "):
            text = re.sub(r"^(A|An)\s+", "", text)

        # 句式翻译
        patterns = [
            (r"^(.+?) for (.+)$", r"针对\2的\1"),
            (r"^(.+?) to (.+)$", r"用于\2的\1"),
            (r"^(.+?) using (.+)$", r"基于\2的\1"),
            (r"^(.+?) with (.+)$", r"支持\2的\1"),
            (r"^(.+?) based on (.+)$", r"基于\2的\1"),
            (r"^MCP server for (.+)$", r"MCP 服务 - 用于\1"),
            (r"^(.+?) for (.+?)\.(.+)$", r"针对\2的\1。\3"),
        ]
        translated = text
        for pattern, replacement in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                translated = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                break

        # 词汇替换
        for eng, cn in _glossary.items():
            translated = re.sub(rf"\b{eng}\b", cn, translated, flags=re.IGNORECASE)

        # 如果翻译结果和原文差异不大，尝试用 API
        if translated == text and len(text) > 20:
            return text + "（英文）"  # 标记未翻译

        return translated

    # 尝试用免费翻译 API（不需要 key）
    async def _api_translate(text: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://translate.googleapis.com/translate_a/single",
                    params={
                        "client": "gtx",
                        "sl": "en",
                        "tl": "zh-CN",
                        "dt": "t",
                        "q": text[:500],  # 限制长度
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = "".join(part[0] for part in data[0] if part[0])
                    if result and result != text:
                        return result
        except Exception:
            pass
        return None

    async with async_session_factory() as session:
        result = await session.execute(select(ServerModel))
        servers = result.scalars().all()

        count = 0
        for s in servers:
            if not _needs_translation(s.description or ""):
                continue

            old_desc = s.description or ""

            # 先尝试免费 API
            translated = await _api_translate(old_desc)
            if translated and translated != old_desc:
                s.description = translated
                count += 1
                continue

            # API 失败时用本地简化翻译
            simple = _simple_translate(old_desc)
            if simple != old_desc:
                s.description = simple
                count += 1

            # 每翻译 50 个停一下避免被限流
            if count % 50 == 0 and count > 0:
                await session.commit()
                await asyncio.sleep(1)

        await session.commit()
    return count


# ========== 导出 ==========


async def enrich_all():
    """一键执行：生成图标 + 翻译描述。"""
    await generate_icons()

    await translate_descriptions()



if __name__ == "__main__":
    asyncio.run(enrich_all())
