"""异步数据仓库层 — 所有数据库操作通过这里。"""

from __future__ import annotations

import json

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_hub.db.models import (
    FavoriteModel,
    ReviewModel,
    ServerModel,
    UserModel,
)


class ServerRepository:
    """Server 数据仓库。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _server_to_dict(server: ServerModel) -> dict:
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
            "install_command": server.install_command or "",
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
    ) -> tuple[list[dict], int]:
        """搜索 Server。"""
        query = select(ServerModel)
        count_query = select(func.count(ServerModel.id))

        conditions = []
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

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        # Sort
        sort_map = {
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

    async def get_by_id(self, server_id: str) -> dict | None:
        result = await self.session.execute(
            select(ServerModel).where(ServerModel.id == server_id)
        )
        server = result.scalar_one_or_none()
        return self._server_to_dict(server) if server else None

    async def get_installed(self) -> list[dict]:
        result = await self.session.execute(
            select(ServerModel)
            .where(ServerModel.status != "not_installed")
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
        return result.rowcount > 0

    async def increment_download(self, server_id: str) -> None:
        await self.session.execute(
            update(ServerModel)
            .where(ServerModel.id == server_id)
            .values(download_count=ServerModel.download_count + 1)
        )
        await self.session.commit()

    async def get_trending(self, limit: int = 20) -> list[dict]:
        result = await self.session.execute(
            select(ServerModel).order_by(ServerModel.download_count.desc()).limit(limit)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def get_top_rated(self, limit: int = 20) -> list[dict]:
        result = await self.session.execute(
            select(ServerModel)
            .where(ServerModel.review_count > 0)
            .order_by(ServerModel.rating.desc())
            .limit(limit)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def get_new_releases(self, limit: int = 20) -> list[dict]:
        result = await self.session.execute(
            select(ServerModel).order_by(ServerModel.created_at.desc()).limit(limit)
        )
        return [self._server_to_dict(s) for s in result.scalars().all()]

    async def register_server(self, data: dict) -> str:
        server_id = data.get("id", "")
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
            new_server = ServerModel(
                id=server_id,
                name=data.get("name", server_id.split("/")[-1] if "/" in server_id else server_id),
                description=data.get("description", ""),
                author=data.get("author", ""),
                categories=json.dumps(data.get("categories", [])),
                tags=json.dumps(data.get("tags", [])),
                install_type=data.get("install_type", "pip"),
                install_package=data.get("install_package", ""),
                install_command=data.get("install_command", ""),
                homepage=data.get("homepage", ""),
                license=data.get("license", "MIT"),
            )
            self.session.add(new_server)

        await self.session.commit()
        return server_id


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def rate(self, server_id: str, user_id: str, rating: int, content: str = "") -> dict:
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

        await self.session.commit()

        # Update average rating
        avg_result = await self.session.execute(
            select(func.avg(ReviewModel.rating), func.count(ReviewModel.id))
            .where(ReviewModel.server_id == server_id)
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

    async def get_reviews(self, server_id: str, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            select(ReviewModel)
            .where(ReviewModel.server_id == server_id)
            .order_by(ReviewModel.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": r.id,
                "server_id": r.server_id,
                "user_id": r.user_id,
                "rating": r.rating,
                "content": r.content or "",
                "created_at": str(r.created_at) if r.created_at else "",
            }
            for r in result.scalars().all()
        ]


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_data: dict) -> dict:
        user_id = user_data.get("id") or user_data.get("login", "")
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
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

        await self.session.commit()

        # Update count
        count_result = await self.session.execute(
            select(func.count(FavoriteModel.id)).where(
                FavoriteModel.server_id == server_id
            )
        )
        count = count_result.scalar() or 0
        await self.session.execute(
            update(ServerModel)
            .where(ServerModel.id == server_id)
            .values(favorite_count=count)
        )
        await self.session.commit()

        return is_favorited

    async def get_favorites(self, user_id: str) -> list[dict]:
        result = await self.session.execute(
            select(ServerModel)
            .join(FavoriteModel, FavoriteModel.server_id == ServerModel.id)
            .where(FavoriteModel.user_id == user_id)
            .order_by(FavoriteModel.created_at.desc())
        )
        return [ServerRepository._server_to_dict(s) for s in result.scalars().all()]
