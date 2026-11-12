"""Post lifecycle. REST routes and MCP tools both go through here."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors import get_connector
from app.connectors.base import MediaItem, PublishContent
from app.models import Media, Post, PostMedia, PostTarget, SocialAccount, Workspace
from app.services.errors import DomainError, NotFound
from app.storage import get_storage

EDITABLE = {"draft", "scheduled"}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _absolute(url: str) -> str:
    """Local storage serves relative URLs; connectors need one they can fetch."""
    return f"{get_settings().api_base_url.rstrip('/')}{url}" if url.startswith("/") else url


def build_content(post: Post, target: PostTarget) -> PublishContent:
    storage = get_storage()
    return PublishContent(
        caption=target.caption_override if target.caption_override is not None else post.caption,
        media=[
            MediaItem(
                url=_absolute(storage.public_url(l.media.key)),
                kind=l.media.kind,
                content_type=l.media.content_type,
            )
            for l in post.media_links
        ],
        options=target.options or {},
    )


def check_publishable(post: Post) -> None:
    """Raise with every problem that would make this post fail at publish time."""
    if not post.targets:
        raise DomainError("Sélectionne au moins un compte sur lequel publier.")
    problems: list[str] = []
    for t in post.targets:
        connector = get_connector(t.account.platform)
        if connector is None:
            problems.append(f"{t.account.platform} : publication pas encore disponible.")
            continue
        if t.account.status != "active":
            problems.append(f"{t.account.display_name} : le compte doit être reconnecté.")
        problems += connector.validate(build_content(post, t))
    if problems:
        raise DomainError(" ".join(dict.fromkeys(problems)))


async def get_post(session: AsyncSession, workspace_id: uuid.UUID, post_id: uuid.UUID) -> Post:
    post = (
        await session.execute(
            select(Post)
            .where(Post.id == post_id, Post.workspace_id == workspace_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if post is None:
        raise NotFound("Post")
    return post


async def list_posts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    status: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[Post]:
    q = select(Post).where(Post.workspace_id == workspace_id)
    if status:
        q = q.where(Post.status == status)
    if start:
        q = q.where(Post.scheduled_at >= _aware(start))
    if end:
        q = q.where(Post.scheduled_at < _aware(end))
    q = q.order_by(Post.scheduled_at.desc().nulls_first(), Post.created_at.desc())
    return list((await session.execute(q.limit(min(limit, 500)))).scalars())


async def _set_targets(
    session: AsyncSession,
    post: Post,
    account_ids: list[uuid.UUID],
    overrides: dict[uuid.UUID, str],
) -> None:
    ids = list(dict.fromkeys(account_ids))
    accounts = list(
        (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.id.in_(ids), SocialAccount.workspace_id == post.workspace_id
                )
            )
        ).scalars()
    )
    if len(accounts) != len(ids):
        raise DomainError("Un des comptes sélectionnés n'existe pas dans cet espace.")
    existing = {t.social_account_id: t for t in post.targets}
    post.targets = [
        existing.get(a.id) or PostTarget(social_account_id=a.id, account=a) for a in accounts
    ]
    for t in post.targets:
        t.caption_override = overrides.get(t.social_account_id)


async def _set_media(session: AsyncSession, post: Post, media_ids: list[uuid.UUID]) -> None:
    ids = list(dict.fromkeys(media_ids))
    found = {
        m.id: m
        for m in (
            await session.execute(
                select(Media).where(Media.id.in_(ids), Media.workspace_id == post.workspace_id)
            )
        ).scalars()
    }
    if len(found) != len(ids):
        raise DomainError("Un des médias sélectionnés n'existe pas dans cet espace.")
    if any(m.status != "ready" for m in found.values()):
        raise DomainError("Un des médias n'a pas fini d'être envoyé.")
    post.media_links = []
    await session.flush()
    post.media_links = [
        PostMedia(media_id=mid, media=found[mid], position=i) for i, mid in enumerate(ids)
    ]


async def _apply_schedule(
    session: AsyncSession, post: Post, when: datetime | None, actor: str
) -> None:
    """Validate then schedule. LLM-created posts stay drafts in approval mode."""
    check_publishable(post)
    when = _aware(when)
    ws = await session.get(Workspace, post.workspace_id)
    if actor == "mcp" and ws is not None and ws.llm_publish_mode == "draft":
        post.status = "draft"
        post.scheduled_at = when  # intended time, applied when a human approves
        return
    post.status = "scheduled"
    post.scheduled_at = when or datetime.now(UTC)
    for t in post.targets:
        t.status, t.attempts, t.next_attempt_at, t.error = "pending", 0, None, None


async def create_post(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    caption: str = "",
    account_ids: list[uuid.UUID] | None = None,
    media_ids: list[uuid.UUID] | None = None,
    scheduled_at: datetime | None = None,
    publish_now: bool = False,
    caption_overrides: dict[uuid.UUID, str] | None = None,
    actor: str = "web",
) -> Post:
    post = Post(
        workspace_id=workspace_id, caption=caption, source=actor, targets=[], media_links=[]
    )
    session.add(post)
    await _set_targets(session, post, account_ids or [], caption_overrides or {})
    await _set_media(session, post, media_ids or [])
    if scheduled_at or publish_now:
        await _apply_schedule(session, post, None if publish_now else scheduled_at, actor)
    await session.commit()
    return await get_post(session, workspace_id, post.id)


async def update_post(
    session: AsyncSession,
    post: Post,
    *,
    caption: str | None = None,
    account_ids: list[uuid.UUID] | None = None,
    media_ids: list[uuid.UUID] | None = None,
    caption_overrides: dict[uuid.UUID, str] | None = None,
) -> Post:
    if post.status not in EDITABLE:
        raise DomainError("Ce post ne peut plus être modifié.", 409)
    if caption is not None:
        post.caption = caption
    if account_ids is not None or caption_overrides is not None:
        current = {
            t.social_account_id: t.caption_override
            for t in post.targets
            if t.caption_override is not None
        }
        await _set_targets(
            session,
            post,
            account_ids if account_ids is not None else [t.social_account_id for t in post.targets],
            caption_overrides if caption_overrides is not None else current,
        )
    if media_ids is not None:
        await _set_media(session, post, media_ids)
    if post.status == "scheduled":
        check_publishable(post)
    await session.commit()
    return await get_post(session, post.workspace_id, post.id)


async def schedule_post(
    session: AsyncSession, post: Post, when: datetime | None, actor: str = "web"
) -> Post:
    if post.status not in EDITABLE:
        raise DomainError("Ce post est déjà parti ou en cours de publication.", 409)
    await _apply_schedule(session, post, when, actor)
    await session.commit()
    return await get_post(session, post.workspace_id, post.id)


async def unschedule_post(session: AsyncSession, post: Post) -> Post:
    if post.status != "scheduled":
        raise DomainError("Seul un post planifié peut être annulé.", 409)
    post.status = "draft"
    await session.commit()
    return await get_post(session, post.workspace_id, post.id)


async def retry_post(session: AsyncSession, post: Post) -> Post:
    if post.status not in {"failed", "partial"}:
        raise DomainError("Seul un post en échec peut être relancé.", 409)
    for t in post.targets:
        if t.status == "failed":
            t.status, t.attempts, t.next_attempt_at, t.error = "pending", 0, None, None
    post.status = "scheduled"
    post.scheduled_at = datetime.now(UTC)
    await session.commit()
    return await get_post(session, post.workspace_id, post.id)


async def delete_post(session: AsyncSession, post: Post) -> None:
    if post.status == "publishing":
        raise DomainError("Publication en cours, réessaie dans un instant.", 409)
    await session.delete(post)
    await session.commit()
