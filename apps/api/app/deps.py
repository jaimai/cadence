import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, Membership
from app.security import SESSION_COOKIE, hash_api_key, read_session_token

Session = Annotated[AsyncSession, Depends(get_session)]


@dataclass
class Auth:
    user_id: uuid.UUID
    workspace_id: uuid.UUID


async def current_auth(
    session: Session, token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None
) -> Auth:
    ids = read_session_token(token) if token else None
    if ids is None:
        raise HTTPException(401, "Non connecté.")
    user_id, workspace_id = ids
    member = await session.get(Membership, (user_id, workspace_id))
    if member is None:
        raise HTTPException(401, "Non connecté.")
    return Auth(user_id, workspace_id)


CurrentAuth = Annotated[Auth, Depends(current_auth)]


async def workspace_for_api_key(session: AsyncSession, key: str) -> uuid.UUID | None:
    api_key = (
        await session.execute(
            select(ApiKey).where(ApiKey.key_hash == hash_api_key(key), ApiKey.revoked_at.is_(None))
        )
    ).scalar_one_or_none()
    if api_key is None:
        return None
    api_key.last_used_at = datetime.now(UTC)
    await session.commit()
    return api_key.workspace_id
