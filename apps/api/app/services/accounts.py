import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectedAccount
from app.models import SocialAccount
from app.security import encrypt
from app.services.errors import NotFound


async def list_accounts(session: AsyncSession, workspace_id: uuid.UUID) -> list[SocialAccount]:
    q = (
        select(SocialAccount)
        .where(SocialAccount.workspace_id == workspace_id)
        .order_by(SocialAccount.platform, SocialAccount.display_name)
    )
    return list((await session.execute(q)).scalars())


async def get_account(
    session: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID
) -> SocialAccount:
    account = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id, SocialAccount.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise NotFound("Compte")
    return account


async def upsert_accounts(
    session: AsyncSession, workspace_id: uuid.UUID, platform: str, connected: list[ConnectedAccount]
) -> int:
    for c in connected:
        account = (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.workspace_id == workspace_id,
                    SocialAccount.platform == platform,
                    SocialAccount.external_id == c.external_id,
                )
            )
        ).scalar_one_or_none()
        if account is None:
            account = SocialAccount(
                workspace_id=workspace_id,
                platform=platform,
                external_id=c.external_id,
                display_name=c.display_name,
                access_token_enc="",
            )
            session.add(account)
        account.display_name = c.display_name
        account.username = c.username
        account.avatar_url = c.avatar_url
        account.access_token_enc = encrypt(c.access_token)
        account.refresh_token_enc = encrypt(c.refresh_token) if c.refresh_token else None
        account.token_expires_at = c.token_expires_at
        account.meta = c.meta
        account.status = "active"
    await session.commit()
    return len(connected)
