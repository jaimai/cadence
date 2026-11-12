"""Publishing engine run by the worker. Postgres is the queue (SKIP LOCKED)."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.connectors import get_connector
from app.connectors.base import AccountAuth, ConnectorError
from app.models import Post, PostTarget, SocialAccount
from app.security import decrypt, encrypt
from app.services.posts import build_content

log = logging.getLogger("cadence.publisher")
BATCH = 10
# A target left "publishing" this long means the worker died mid-call. We fail it
# rather than retry: the platform may already have the post, and a duplicate is worse.
STUCK_AFTER = timedelta(minutes=30)


async def _claim(session: AsyncSession) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    rows = (
        (
            await session.execute(
                select(PostTarget)
                .join(Post, Post.id == PostTarget.post_id)
                .where(
                    Post.status.in_(["scheduled", "publishing"]),
                    Post.scheduled_at <= now,
                    PostTarget.status == "pending",
                    or_(PostTarget.next_attempt_at.is_(None), PostTarget.next_attempt_at <= now),
                )
                .order_by(Post.scheduled_at)
                .limit(BATCH)
                .with_for_update(of=PostTarget, skip_locked=True)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    for t in rows:
        t.status, t.locked_at, t.attempts = "publishing", now, t.attempts + 1
    if rows:
        await session.execute(
            update(Post).where(Post.id.in_({t.post_id for t in rows})).values(status="publishing")
        )
    await session.commit()
    return [t.id for t in rows]


async def _refresh_post_status(session: AsyncSession, post_id: uuid.UUID) -> None:
    statuses = set(
        (
            await session.execute(select(PostTarget.status).where(PostTarget.post_id == post_id))
        ).scalars()
    )
    if statuses & {"pending", "publishing"}:
        status = "publishing"
    elif statuses == {"published"}:
        status = "published"
    elif statuses == {"failed"}:
        status = "failed"
    else:
        status = "partial"
    await session.execute(update(Post).where(Post.id == post_id).values(status=status))


async def _publish_one(session: AsyncSession, target_id: uuid.UUID) -> None:
    target = await session.get(PostTarget, target_id)
    if target is None:
        return
    post = await session.get(Post, target.post_id)
    account = target.account
    connector = get_connector(account.platform)
    try:
        if connector is None:
            raise ConnectorError(f"{account.platform} : publication pas encore disponible.")
        await _ensure_fresh_token(session, account, timedelta(minutes=10))
        result = await connector.publish(
            AccountAuth(account.external_id, decrypt(account.access_token_enc), account.meta or {}),
            build_content(post, target),
        )
    except Exception as e:
        retryable = isinstance(e, ConnectorError) and e.retryable
        if isinstance(e, ConnectorError) and e.reauth:
            account.status = "needs_reauth"
        if not isinstance(e, ConnectorError):
            log.exception("unexpected publish error for target %s", target_id)
        if retryable and target.attempts < get_settings().publish_max_attempts:
            target.status = "pending"
            target.next_attempt_at = datetime.now(UTC) + timedelta(minutes=2**target.attempts)
        else:
            target.status = "failed"
        target.error = str(e) or e.__class__.__name__
    else:
        target.status, target.error = "published", None
        target.external_post_id, target.permalink = result.external_post_id, result.permalink
        target.published_at = datetime.now(UTC)
    target.locked_at = None
    await session.flush()
    await _refresh_post_status(session, target.post_id)
    await session.commit()


async def _fail_stuck(session: AsyncSession) -> None:
    stuck = (
        (
            await session.execute(
                select(PostTarget).where(
                    PostTarget.status == "publishing",
                    PostTarget.locked_at < datetime.now(UTC) - STUCK_AFTER,
                )
            )
        )
        .unique()
        .scalars()
        .all()
    )
    for t in stuck:
        t.status, t.locked_at = "failed", None
        t.error = "Publication interrompue. Vérifie sur la plateforme avant de relancer."
    await session.flush()
    for post_id in {t.post_id for t in stuck}:
        await _refresh_post_status(session, post_id)
    await session.commit()


async def _ensure_fresh_token(
    session: AsyncSession, account: SocialAccount, margin: timedelta
) -> None:
    """Renew the account's token if it expires within `margin`.

    The row is locked because some platforms rotate the refresh token: two
    concurrent renewals would leave one of them holding a dead token.
    """
    connector = get_connector(account.platform)
    if connector is None or connector.refresh_margin is None or account.token_expires_at is None:
        return
    if account.token_expires_at > datetime.now(UTC) + margin:
        return
    await session.refresh(account, with_for_update=True)
    if account.token_expires_at > datetime.now(UTC) + margin:
        await session.commit()  # another worker renewed it while we waited for the lock
        return
    try:
        tokens = await connector.refresh(
            decrypt(account.access_token_enc),
            decrypt(account.refresh_token_enc) if account.refresh_token_enc else None,
        )
    except ConnectorError as e:
        if e.reauth or (not e.retryable and account.token_expires_at <= datetime.now(UTC)):
            account.status = "needs_reauth"
        await session.commit()
        raise
    if tokens is not None:
        account.access_token_enc = encrypt(tokens.access_token)
        if tokens.refresh_token:
            account.refresh_token_enc = encrypt(tokens.refresh_token)
        account.token_expires_at = tokens.token_expires_at
    await session.commit()


async def _refresh_tokens(session: AsyncSession) -> None:
    """Keep tokens alive in the background so accounts stay connected when idle."""
    now = datetime.now(UTC)
    accounts = (
        (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.status == "active",
                    SocialAccount.token_expires_at < now + timedelta(days=30),
                )
            )
        )
        .scalars()
        .all()
    )
    for account in accounts:
        connector = get_connector(account.platform)
        if connector is None or connector.refresh_margin is None:
            continue
        if account.token_expires_at > now + connector.refresh_margin:
            continue
        try:
            await _ensure_fresh_token(session, account, connector.refresh_margin)
        except ConnectorError as e:
            log.warning("token refresh failed for account %s: %s", account.id, e)


async def run_once(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """One worker tick. Returns how many targets were attempted."""
    async with session_factory() as session:
        await _fail_stuck(session)
        await _refresh_tokens(session)
        claimed = await _claim(session)

    async def publish(target_id: uuid.UUID) -> None:
        async with session_factory() as session:
            await _publish_one(session, target_id)

    # Concurrent: a video can take minutes to process and must not hold up the rest.
    await asyncio.gather(*(publish(t) for t in claimed))
    return len(claimed)
