import asyncio
import ipaddress
import socket
import uuid
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Media
from app.services.errors import DomainError, NotFound
from app.storage import UploadTarget, get_storage

CONTENT_TYPES = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/webp": ("image", ".webp"),
    "video/mp4": ("video", ".mp4"),
    "video/quicktime": ("video", ".mov"),
}


def max_size(kind: str) -> int:
    s = get_settings()
    return s.max_video_bytes if kind == "video" else s.max_image_bytes


def _new_media(workspace_id: uuid.UUID, filename: str, content_type: str, size: int) -> Media:
    content_type = content_type.split(";")[0].strip().lower()
    if content_type not in CONTENT_TYPES:
        raise DomainError("Format non pris en charge. Formats acceptés : JPG, PNG, WebP, MP4, MOV.")
    kind, ext = CONTENT_TYPES[content_type]
    if size > max_size(kind):
        raise DomainError(f"Fichier trop lourd ({max_size(kind) // (1024 * 1024)} Mo maximum).")
    media_id = uuid.uuid4()
    return Media(
        id=media_id,
        workspace_id=workspace_id,
        key=f"{workspace_id}/{media_id}{ext}",
        filename=PurePosixPath(filename.replace("\\", "/")).name[:255] or f"media{ext}",
        content_type=content_type,
        kind=kind,
        size=size,
    )


async def get_media(session: AsyncSession, workspace_id: uuid.UUID, media_id: uuid.UUID) -> Media:
    media = (
        await session.execute(
            select(Media).where(Media.id == media_id, Media.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if media is None:
        raise NotFound("Média")
    return media


async def list_media(
    session: AsyncSession, workspace_id: uuid.UUID, limit: int = 200
) -> list[Media]:
    q = (
        select(Media)
        .where(Media.workspace_id == workspace_id, Media.status == "ready")
        .order_by(Media.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(q)).scalars())


async def create_upload(
    session: AsyncSession, workspace_id: uuid.UUID, filename: str, content_type: str, size: int
) -> tuple[Media, UploadTarget]:
    media = _new_media(workspace_id, filename, content_type, size)
    session.add(media)
    await session.commit()
    return media, get_storage().upload_target(str(media.id), media.key, media.content_type)


async def complete_upload(session: AsyncSession, media: Media) -> Media:
    size = await get_storage().size(media.key)
    if size is None:
        raise DomainError("Le fichier n'a pas été reçu.")
    if size > max_size(media.kind):
        await get_storage().delete(media.key)
        raise DomainError("Fichier trop lourd.")
    media.size, media.status = size, "ready"
    await session.commit()
    return media


async def delete_media(session: AsyncSession, media: Media) -> None:
    try:
        await session.delete(media)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DomainError("Ce média est utilisé par un post.", 409) from None
    await get_storage().delete(media.key)


async def _assert_public(url: str) -> None:
    """Refuse URLs that point inside our own network (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DomainError("L'URL doit commencer par http:// ou https://.")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, None)
    except socket.gaierror:
        raise DomainError("Adresse introuvable.") from None
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise DomainError("Cette adresse n'est pas accessible publiquement.")


async def import_from_url(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Media:
    """Download a public file into storage. Used by the MCP server."""
    async with httpx.AsyncClient(timeout=120, transport=transport) as client:
        for _ in range(4):
            if transport is None:
                await _assert_public(url)
            async with client.stream("GET", url) as resp:
                if resp.is_redirect and "location" in resp.headers:
                    url = urljoin(url, resp.headers["location"])
                    continue
                if not resp.is_success:
                    raise DomainError(f"Téléchargement impossible (HTTP {resp.status_code}).")
                name = PurePosixPath(urlparse(url).path).name or "media"
                media = _new_media(workspace_id, name, resp.headers.get("content-type", ""), 0)
                limit, chunks, total = max_size(media.kind), [], 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > limit:
                        raise DomainError("Fichier trop lourd.")
                    chunks.append(chunk)
            break
        else:
            raise DomainError("Trop de redirections.")
    if total == 0:
        raise DomainError("Le fichier est vide.")
    await get_storage().put(media.key, b"".join(chunks), media.content_type)
    media.size, media.status = total, "ready"
    session.add(media)
    await session.commit()
    return media
