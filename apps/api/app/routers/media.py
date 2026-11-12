import uuid

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.deps import CurrentAuth, Session
from app.schemas import MediaOut, PresignIn, PresignOut
from app.services import media as svc
from app.storage import LocalStorage, get_storage

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("", response_model=list[MediaOut])
async def list_media(auth: CurrentAuth, session: Session):
    return [MediaOut.of(m) for m in await svc.list_media(session, auth.workspace_id)]


@router.post("/presign", response_model=PresignOut)
async def presign(body: PresignIn, auth: CurrentAuth, session: Session):
    media, target = await svc.create_upload(
        session, auth.workspace_id, body.filename, body.content_type, body.size
    )
    return PresignOut(
        media=MediaOut.of(media),
        upload_url=target.url,
        upload_method=target.method,
        upload_headers=target.headers,
    )


@router.put("/{media_id}/upload", status_code=204)
async def local_upload(media_id: uuid.UUID, request: Request, auth: CurrentAuth, session: Session):
    """Upload endpoint for the local storage backend (development)."""
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(404)
    media = await svc.get_media(session, auth.workspace_id, media_id)
    path = storage.path(media.key)
    path.parent.mkdir(parents=True, exist_ok=True)
    limit, total = svc.max_size(media.kind), 0
    with path.open("wb") as f:
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                f.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, "Fichier trop lourd.")
            f.write(chunk)


@router.post("/{media_id}/complete", response_model=MediaOut)
async def complete(media_id: uuid.UUID, auth: CurrentAuth, session: Session):
    media = await svc.get_media(session, auth.workspace_id, media_id)
    return MediaOut.of(await svc.complete_upload(session, media))


@router.delete("/{media_id}", status_code=204)
async def delete(media_id: uuid.UUID, auth: CurrentAuth, session: Session) -> None:
    media = await svc.get_media(session, auth.workspace_id, media_id)
    await svc.delete_media(session, media)


def local_media_dir() -> str | None:
    s = get_settings()
    return s.local_media_dir if s.storage_backend != "r2" else None
