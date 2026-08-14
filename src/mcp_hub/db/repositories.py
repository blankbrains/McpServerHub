"""异步数据仓库层 — 所有数据库操作通过这里。"""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from mcp_hub.db.models import (
    FavoriteModel,
    RegistrySourceEntryModel,
    ReviewModel,
    ServerModel,
    UserModel,
)
from mcp_hub.runtime_config import (
    has_runnable_server_config,
    is_legacy_inferred_github_command,
)


class ServerRepository:
    """Server 数据仓库。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _server_to_dict(server: ServerModel) -> dict[str, Any]:
        try:
            config_template = json.loads(server.config_template) if server.config_template else {}
        except json.JSONDecodeError:
            config_template = {}
        install_command = server.install_command or ""
        if is_legacy_inferred_github_command(
            server.id,
            server.install_package or "",
            install_command,
        ):
            install_command = ""
        runnable_config = has_runnable_server_config(
            install_command,
            config_template if isinstance(config_template, dict) else None,
        )
        return {
            "id": server.id,
            "name": server.name,
            "display_name": server.display_name,
            "icon_url": server.icon_url or "",
            "description": server.description or "",
            "author": server.author or "",
            "current_version": server.current_version or "",
            "latest_version": server.latest_version or "",
            "categories": json.loads(server.categories) if server.categories else [],
            "tags": json.loads(server.tags) if server.tags else [],
            "install_type": server.install_type or "",
            "install_package": server.install_package or "",
            "install_command": install_command,
            "runtime_config_available": runnable_config,
            "config_template": config_template if isinstance(config_template, dict) else {},
            "catalog_source": server.catalog_source or "",
            "catalog_source_id": server.catalog_source_id or "",
            "catalog_status": server.catalog_status or "active",
            "homepage": server.homepage or "",
            "license": server.license or "MIT",
            "security_level": server.security_level or "unreviewed",
            "network_access": server.network_access or False,
            "file_access": server.file_access or False,
            "rating": server.rating or 0.0,
            "review_count": server.review_count or 0,
            "download_count": server.download_count or 0,
            "favorite_count": server.favorite_count or 0,
            "status": server.status or "not_installed",
            "version": server.current_version or server.latest_version or "",
            "created_at": str(server.created_at) if server.created_at else "",
            "updated_at": str(server.updated_at) if server.updated_at else "",
        }

    async def search(
        self,
        q: str = "",
        category: str | None = None,
        tag: str | None = None,
        sort: str = "hot",
        page: int = 1,
        page_size: int = 20,
        security_level: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """搜索 Server。"""
        visible = or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None))
        query = select(ServerModel).where(visible)
        count_query = select(func.count(ServerModel.id)).where(visible)

        conditions: list[ColumnElement[bool]] = []
        if q:
            conditions.append(
                or_(
                    ServerModel.name.ilike(f"%{q}%"),
                    ServerModel.description.ilike(f"%{q}%"),
                )
            )
        if category:
            conditions.append(ServerModel.categories.ilike(f"%{category}%"))
        if tag:
            conditions.append(ServerModel.tags.ilike(f"%{tag}%"))
        if security_level:
            conditions.append(ServerModel.security_level == security_level)

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        # Sort
        sort_map: dict[str, ColumnElement[Any]] = {
            "hot": ServerModel.download_count.desc(),
            "rating": ServerModel.rating.desc(),
            "downloads": ServerModel.download_count.desc(),
            "new": ServerModel.created_at.desc(),
        }
        order = sort_map.get(sort, ServerModel.download_count.desc())
        query = query.order_by(order)

        # Count total
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.session.execute(query)
        servers = result.scalars().all()

        return [self._server_to_dict(s) for s in servers], total

    async def get_by_id(
        self,
        server_id: str,
        *,
        include_hidden: bool = False,
    ) -> dict[str, Any] | None:
        query = select(ServerModel).where(ServerModel.id == server_id)
        if not include_hidden:
            query = query.where(
                or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None))
            )
        result = await self.session.execute(query)
        server = result.scalar_one_or_none()
        if not server:
            return None
        data = self._server_to_dict(server)
        provenance_result = await self.session.execute(
            select(RegistrySourceEntryModel)
            .where(RegistrySourceEntryModel.server_id == server.id)
            .order_by(RegistrySourceEntryModel.last_synced_at.desc())
            .limit(1)
        )
        provenance = provenance_result.scalar_one_or_none()
        if provenance:
            data["registry"] = {
                "source": provenance.source,
                "upstream_id": provenance.upstream_id,
                "version": provenance.upstream_version or "",
                "package_type": provenance.package_type or "",
                "package_identifier": provenance.package_identifier or "",
                "repository_url": provenance.repository_url or "",
                "transport": provenance.transport or "",
                "status": provenance.lifecycle_status or "active",
                "published_at": str(provenance.published_at) if provenance.published_at else "",
                "updated_at": (
                    str(provenance.upstream_updated_at)
                    if provenance.upstream_updated_at
                    else ""
                ),
                "last_synced_at": (
                    str(provenance.last_synced_at) if provenance.last_synced_at else ""
                ),
            }
        return data

    async def get_installed(self) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ServerModel)
            .where(
                ServerModel.status != "not_installed",
                or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None)),
            )
            .order_by(ServerModel.name)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def update_status(self, server_id: str, status: str) -> bool:
        result = await self.session.execute(
            update(ServerModel)
            .where(ServerModel.id == server_id)
            .values(status=status, updated_at=func.now())
        )
        await self.session.commit()
        return cast(CursorResult[Any], result).rowcount > 0

    async def increment_download(self, server_id: str) -> None:
        await self.session.execute(
            update(ServerModel)
            .where(ServerModel.id == server_id)
            .values(download_count=ServerModel.download_count + 1)
        )
        await self.session.commit()

    async def get_trending(self, limit: int = 20) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ServerModel)
            .where(or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None)))
            .order_by(ServerModel.download_count.desc())
            .limit(limit)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def get_top_rated(self, limit: int = 20) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ServerModel)
            .where(
                ServerModel.review_count > 0,
                or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None)),
            )
            .order_by(ServerModel.rating.desc())
            .limit(limit)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def get_new_releases(self, limit: int = 20) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ServerModel)
            .where(or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None)))
            .order_by(ServerModel.created_at.desc())
            .limit(limit)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def register_server(self, data: dict[str, Any]) -> str:
        server_id = str(data.get("id", ""))
        existing = await self.session.execute(
            select(ServerModel).where(ServerModel.id == server_id)
        )
        server = existing.scalar_one_or_none()

        if server:
            for key, value in data.items():
                if hasattr(server, key) and key not in ("id", "created_at"):
                    if isinstance(value, (list, dict)):
                        setattr(server, key, json.dumps(value))
                    else:
                        setattr(server, key, value)
            server.updated_at = func.now()
        else:
            new_server = ServerModel(id=server_id)
            for key, value in data.items():
                if hasattr(new_server, key) and key not in ("id", "created_at"):
                    if isinstance(value, (list, dict)):
                        setattr(new_server, key, json.dumps(value))
                    else:
                        setattr(new_server, key, value)
            self.session.add(new_server)

        await self.session.commit()
        return server_id

    async def get_all(self) -> list[dict[str, Any]]:
        """获取所有 Server 记录（包含未安装的）。"""
        result = await self.session.execute(
            select(ServerModel)
            .where(or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None)))
            .order_by(ServerModel.name)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def get_by_author(self, author: str) -> list[dict[str, Any]]:
        """按作者查询发布的 Server。"""
        result = await self.session.execute(
            select(ServerModel)
            .where(
                ServerModel.author == author,
                or_(ServerModel.market_visible.is_(True), ServerModel.market_visible.is_(None)),
            )
            .order_by(ServerModel.created_at.desc())
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def delete_server(self, server_id: str) -> bool:
        """删除 Server 记录（级联删除关联数据）。"""
        result = await self.session.execute(select(ServerModel).where(ServerModel.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            return False
        # 级联删除关联数据
        from sqlalchemy import delete as sa_delete

        from mcp_hub.db.models import FavoriteModel, ReviewModel, UsageStatsModel

        await self.session.execute(
            sa_delete(FavoriteModel).where(FavoriteModel.server_id == server_id)
        )
        await self.session.execute(sa_delete(ReviewModel).where(ReviewModel.server_id == server_id))
        await self.session.execute(
            sa_delete(UsageStatsModel).where(UsageStatsModel.server_id == server_id)
        )
        await self.session.delete(server)
        await self.session.commit()
        return True


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rate(
        self,
        server_id: str,
        user_id: str,
        rating: int,
        content: str = "",
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        if parent_id:
            # 回复已有评价
            reply = ReviewModel(
                server_id=server_id,
                user_id=user_id,
                rating=rating,
                content=content,
                parent_id=parent_id,
            )
            self.session.add(reply)
            await self.session.commit()
            return {"rating": rating, "review_count": 0, "parent_id": parent_id}

        existing = await self.session.execute(
            select(ReviewModel).where(
                ReviewModel.server_id == server_id,
                ReviewModel.user_id == user_id,
            )
        )
        review = existing.scalar_one_or_none()

        if review:
            review.rating = rating
            review.content = content
            review.updated_at = func.now()
        else:
            review = ReviewModel(
                server_id=server_id, user_id=user_id, rating=rating, content=content
            )
            self.session.add(review)

        # Update average rating
        avg_result = await self.session.execute(
            select(func.avg(ReviewModel.rating), func.count(ReviewModel.id)).where(
                ReviewModel.server_id == server_id
            )
        )
        row = avg_result.one()
        avg_rating = round(float(row[0]), 1) if row[0] else 0.0
        count = row[1] or 0

        await self.session.execute(
            update(ServerModel)
            .where(ServerModel.id == server_id)
            .values(rating=avg_rating, review_count=count)
        )
        await self.session.commit()

        return {"rating": avg_rating, "review_count": count}

    async def get_reviews(self, server_id: str, limit: int = 50) -> list[dict[str, Any]]:
        # 先查父评论（顶层评价），limit 只对父评论生效
        parent_result = await self.session.execute(
            select(ReviewModel)
            .where(
                ReviewModel.server_id == server_id,
                ReviewModel.parent_id.is_(None),
            )
            .order_by(ReviewModel.created_at.desc())
            .limit(limit)
        )
        parent_reviews = parent_result.scalars().all()
        parent_ids = [r.id for r in parent_reviews]

        reviews: list[dict[str, Any]] = []

        def _to_dict(review: ReviewModel) -> dict[str, Any]:
            return {
                "id": review.id,
                "server_id": review.server_id,
                "user_id": review.user_id,
                "parent_id": review.parent_id,
                "rating": review.rating,
                "content": review.content or "",
                "created_at": str(review.created_at) if review.created_at else "",
            }

        for parent_review in parent_reviews:
            reviews.append(_to_dict(parent_review))

        # 获取这些父评论的所有回复（不限数量）
        if parent_ids:
            reply_result = await self.session.execute(
                select(ReviewModel)
                .where(
                    ReviewModel.server_id == server_id,
                    ReviewModel.parent_id.in_(parent_ids),
                )
                .order_by(ReviewModel.created_at.asc())
            )
            for reply in reply_result.scalars().all():
                reviews.append(_to_dict(reply))

        # 构建树结构：顶层评价按时间降序，回复在 replies 里
        top = [review for review in reviews if review["parent_id"] is None]
        reply_map: dict[int, list[dict[str, Any]]] = {}
        for review_data in reviews:
            parent_id_value = review_data["parent_id"]
            if isinstance(parent_id_value, int):
                reply_map.setdefault(parent_id_value, []).append(review_data)
        for top_review in top:
            review_id = top_review["id"]
            top_review["replies"] = (
                reply_map.get(review_id, []) if isinstance(review_id, int) else []
            )
        return top

    async def get_review(self, review_id: int) -> ReviewModel | None:
        result = await self.session.execute(select(ReviewModel).where(ReviewModel.id == review_id))
        return result.scalar_one_or_none()

    async def can_delete_review(
        self, review: ReviewModel, user_id: str, user_role: str
    ) -> tuple[bool, str]:  # noqa: E501
        """检查用户是否有权限删除评价。"""
        if user_role in ("admin", "owner"):
            return True, ""
        if review.user_id == user_id:
            return True, ""
        # 发布者可删除自己 Server 上的评价
        server = await self.session.execute(
            select(ServerModel).where(ServerModel.id == review.server_id)
        )
        s = server.scalar_one_or_none()
        if s and s.author == user_id:
            return True, ""
        return False, "无权限删除此评价"

    async def delete_review(
        self,
        review_id: int,
        user_id: str,
        user_role: str = "user",
    ) -> dict[str, Any]:
        review = await self.get_review(review_id)
        if not review:
            return {"success": False, "error": "评价不存在"}
        can, msg = await self.can_delete_review(review, user_id, user_role)
        if not can:
            return {"success": False, "error": msg}
        server_id = review.server_id
        await self.session.delete(review)
        await self.session.commit()
        # 更新平均评分
        avg_result = await self.session.execute(
            select(func.avg(ReviewModel.rating), func.count(ReviewModel.id)).where(
                ReviewModel.server_id == server_id
            )
        )
        row = avg_result.one()
        avg_rating = round(float(row[0]), 1) if row[0] else 0.0
        count = row[1] or 0
        await self.session.execute(
            update(ServerModel)
            .where(ServerModel.id == server_id)
            .values(rating=avg_rating, review_count=count)
        )
        await self.session.commit()
        return {"success": True, "message": "评价已删除"}


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        """根据 ID 查找用户（不创建）。"""
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        return {
            "id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "role": user.role,
        }

    async def get_or_create(self, user_data: dict[str, Any]) -> dict[str, Any]:
        user_id = str(user_data.get("id") or user_data.get("login", ""))
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            user = UserModel(
                id=user_id,
                display_name=user_data.get("name", user_id),
                avatar_url=user_data.get("avatar_url", ""),
            )
            self.session.add(user)
        else:
            user.last_login = func.now()

        await self.session.commit()
        return {
            "id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "role": user.role,
        }

    async def favorite(self, user_id: str, server_id: str) -> bool:
        """收藏/取消收藏。返回收藏状态。"""
        existing = await self.session.execute(
            select(FavoriteModel).where(
                FavoriteModel.user_id == user_id,
                FavoriteModel.server_id == server_id,
            )
        )
        fav = existing.scalar_one_or_none()

        if fav:
            await self.session.delete(fav)
            is_favorited = False
        else:
            fav = FavoriteModel(user_id=user_id, server_id=server_id)
            self.session.add(fav)
            is_favorited = True

        # Update count
        count_result = await self.session.execute(
            select(func.count(FavoriteModel.id)).where(FavoriteModel.server_id == server_id)
        )
        count = count_result.scalar() or 0
        await self.session.execute(
            update(ServerModel).where(ServerModel.id == server_id).values(favorite_count=count)
        )
        await self.session.commit()

        return is_favorited

    async def get_favorites(self, user_id: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ServerModel)
            .join(FavoriteModel, FavoriteModel.server_id == ServerModel.id)
            .where(FavoriteModel.user_id == user_id)
            .order_by(FavoriteModel.created_at.desc())
        )
        return [ServerRepository._server_to_dict(s) for s in result.scalars().all()]
