import uuid
from datetime import datetime

from fastapi import APIRouter

from app.deps import CurrentAuth, Session
from app.schemas import PostIn, PostOut, PostPatch, ScheduleIn
from app.services import posts as svc

router = APIRouter(prefix="/api/posts", tags=["posts"])


@router.get("", response_model=list[PostOut])
async def list_posts(
    auth: CurrentAuth,
    session: Session,
    status: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 200,
):
    posts = await svc.list_posts(
        session, auth.workspace_id, status=status, start=start, end=end, limit=limit
    )
    return [PostOut.of(p) for p in posts]


@router.post("", response_model=PostOut, status_code=201)
async def create(body: PostIn, auth: CurrentAuth, session: Session):
    return PostOut.of(await svc.create_post(session, auth.workspace_id, **body.model_dump()))


@router.get("/{post_id}", response_model=PostOut)
async def get(post_id: uuid.UUID, auth: CurrentAuth, session: Session):
    return PostOut.of(await svc.get_post(session, auth.workspace_id, post_id))


@router.patch("/{post_id}", response_model=PostOut)
async def patch(post_id: uuid.UUID, body: PostPatch, auth: CurrentAuth, session: Session):
    post = await svc.get_post(session, auth.workspace_id, post_id)
    return PostOut.of(await svc.update_post(session, post, **body.model_dump()))


@router.post("/{post_id}/schedule", response_model=PostOut)
async def schedule(post_id: uuid.UUID, body: ScheduleIn, auth: CurrentAuth, session: Session):
    post = await svc.get_post(session, auth.workspace_id, post_id)
    return PostOut.of(await svc.schedule_post(session, post, body.scheduled_at))


@router.post("/{post_id}/unschedule", response_model=PostOut)
async def unschedule(post_id: uuid.UUID, auth: CurrentAuth, session: Session):
    post = await svc.get_post(session, auth.workspace_id, post_id)
    return PostOut.of(await svc.unschedule_post(session, post))


@router.post("/{post_id}/retry", response_model=PostOut)
async def retry(post_id: uuid.UUID, auth: CurrentAuth, session: Session):
    post = await svc.get_post(session, auth.workspace_id, post_id)
    return PostOut.of(await svc.retry_post(session, post))


@router.delete("/{post_id}", status_code=204)
async def delete(post_id: uuid.UUID, auth: CurrentAuth, session: Session) -> None:
    post = await svc.get_post(session, auth.workspace_id, post_id)
    await svc.delete_post(session, post)
