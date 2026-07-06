"""配置方案市场 API — 发布/浏览/导入配置方案。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select, func, text

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import PresetModel

router = APIRouter(tags=["presets"])


@router.get("/presets")
async def list_presets(page: int = 1, page_size: int = 12, sort: str = "hot"):
    """浏览配置方案市场。"""
    async with async_session_factory() as session:
        stmt = select(PresetModel)
        if sort == "new":
            stmt = stmt.order_by(PresetModel.created_at.desc())
        elif sort == "rating":
            stmt = stmt.order_by(PresetModel.rating.desc())
        else:  # hot
            stmt = stmt.order_by(PresetModel.download_count.desc())

        count_stmt = select(func.count()).select_from(PresetModel)
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = []
        for r in rows:
            try:
                servers = json.loads(r.servers)
            except Exception:
                servers = []
            items.append({
                "id": r.id,
                "user_id": r.user_id,
                "name": r.name,
                "description": r.description,
                "tags": [t.strip() for t in r.tags.split(",") if t.strip()] if r.tags else [],
                "servers": servers,
                "server_count": len(servers),
                "download_count": r.download_count,
                "rating": r.rating,
                "created_at": str(r.created_at) if r.created_at else "",
            })

    return {
        "success": True,
        "data": items,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.get("/presets/{preset_id}")
async def get_preset(preset_id: int):
    """获取单个方案详情。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(PresetModel).where(PresetModel.id == preset_id)
        )
        r = result.scalar_one_or_none()
        if not r:
            return {"success": False, "error": "方案不存在"}

        try:
            servers = json.loads(r.servers)
        except Exception:
            servers = []

        return {
            "success": True,
            "data": {
                "id": r.id,
                "user_id": r.user_id,
                "name": r.name,
                "description": r.description,
                "tags": [t.strip() for t in r.tags.split(",") if t.strip()] if r.tags else [],
                "servers": servers,
                "server_count": len(servers),
                "download_count": r.download_count,
                "rating": r.rating,
                "created_at": str(r.created_at) if r.created_at else "",
            },
        }


@router.post("/presets")
async def create_preset(data: dict, user_id: str = Depends(get_current_user)):
    """创建/发布一个配置方案。"""
    name = data.get("name", "").strip()
    if not name:
        return {"success": False, "error": "方案名称不能为空"}
    servers = data.get("servers", [])
    if not servers:
        return {"success": False, "error": "方案至少需要一个 Server"}

    async with async_session_factory() as session:
        preset = PresetModel(
            user_id=user_id,
            name=name,
            description=data.get("description", ""),
            tags=",".join(data.get("tags", [])),
            servers=json.dumps(servers, ensure_ascii=False),
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)

    return {"success": True, "data": {"id": preset.id}, "message": "方案已发布"}


@router.post("/presets/{preset_id}/import")
async def import_preset(preset_id: int, user_id: str = Depends(get_current_user)):
    """一键导入方案：将方案中的所有 Server 添加到用户配置。"""
    from mcp_hub.db.models import UserServerModel

    async with async_session_factory() as session:
        result = await session.execute(
            select(PresetModel).where(PresetModel.id == preset_id)
        )
        preset = result.scalar_one_or_none()
        if not preset:
            return {"success": False, "error": "方案不存在"}

        try:
            servers = json.loads(preset.servers)
        except Exception:
            return {"success": False, "error": "方案数据损坏"}

        # 批量检查已存在的 Server（避免 N+1）
        all_sids = [srv.get("server_id", srv.get("hub_id", srv.get("name", ""))) for srv in servers]
        all_sids = [s for s in all_sids if s]
        existing_result = await session.execute(
            select(UserServerModel.server_id).where(
                UserServerModel.user_id == user_id,
                UserServerModel.server_id.in_(all_sids),
            )
        )
        existing_ids = set(row[0] for row in existing_result.fetchall())

        imported = 0
        for srv in servers:
            sid = srv.get("server_id", srv.get("hub_id", srv.get("name", "")))
            if not sid or sid in existing_ids:
                continue
            session.add(UserServerModel(
                user_id=user_id,
                server_id=sid,
                matched=srv.get("matched", True),
            ))
            imported += 1
            existing_ids.add(sid)  # 防止同方案中重复的 server_id

        # 原子递增下载计数（避免竞态）
        await session.execute(
            text("UPDATE presets SET download_count = download_count + 1 WHERE id = :pid"),
            {"pid": preset_id},
        )
        await session.commit()

    return {
        "success": True,
        "data": {"imported": imported},
        "message": f"已导入 {imported} 个 Server",
    }


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: int, user_id: str = Depends(get_current_user)):
    """删除自己的方案。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(PresetModel).where(
                PresetModel.id == preset_id,
                PresetModel.user_id == user_id,
            )
        )
        preset = result.scalar_one_or_none()
        if not preset:
            return {"success": False, "error": "方案不存在或无权限"}
        await session.delete(preset)
        await session.commit()
    return {"success": True, "message": "方案已删除"}
