import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import CurrentAuth, Session
from app.models import ApiKey, Workspace
from app.schemas import ApiKeyCreated, ApiKeyIn, ApiKeyOut, WorkspaceOut, WorkspacePatch
from app.security import generate_api_key

router = APIRouter(prefix="/api", tags=["settings"])


@router.patch("/workspace", response_model=WorkspaceOut)
async def update_workspace(body: WorkspacePatch, auth: CurrentAuth, session: Session):
    workspace = await session.get(Workspace, auth.workspace_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(workspace, field, value)
    await session.commit()
    return workspace


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_keys(auth: CurrentAuth, session: Session):
    q = (
        select(ApiKey)
        .where(ApiKey.workspace_id == auth.workspace_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return list((await session.execute(q)).scalars())


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_key(body: ApiKeyIn, auth: CurrentAuth, session: Session):
    key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        workspace_id=auth.workspace_id, name=body.name, prefix=prefix, key_hash=key_hash
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return ApiKeyCreated(**ApiKeyOut.model_validate(api_key).model_dump(), key=key)


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_key(key_id: uuid.UUID, auth: CurrentAuth, session: Session) -> None:
    api_key = await session.get(ApiKey, key_id)
    if api_key is None or api_key.workspace_id != auth.workspace_id:
        raise HTTPException(404, "Clé introuvable.")
    api_key.revoked_at = datetime.now(UTC)
    await session.commit()
