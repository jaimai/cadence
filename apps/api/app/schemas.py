import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app import models
from app.storage import get_storage


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    platform: str
    display_name: str
    username: str | None
    avatar_url: str | None
    status: str


class MediaOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    kind: str
    size: int
    status: str
    url: str
    created_at: datetime

    @classmethod
    def of(cls, m: models.Media) -> "MediaOut":
        return cls(
            id=m.id,
            filename=m.filename,
            content_type=m.content_type,
            kind=m.kind,
            size=m.size,
            status=m.status,
            url=get_storage().public_url(m.key),
            created_at=m.created_at,
        )


class TargetOut(BaseModel):
    id: uuid.UUID
    account: AccountOut
    caption_override: str | None
    status: str
    attempts: int
    permalink: str | None
    error: str | None
    published_at: datetime | None


class PostOut(BaseModel):
    id: uuid.UUID
    caption: str
    status: str
    scheduled_at: datetime | None
    source: str
    created_at: datetime
    updated_at: datetime
    media: list[MediaOut]
    targets: list[TargetOut]

    @classmethod
    def of(cls, p: models.Post) -> "PostOut":
        return cls(
            id=p.id,
            caption=p.caption,
            status=p.status,
            scheduled_at=p.scheduled_at,
            source=p.source,
            created_at=p.created_at,
            updated_at=p.updated_at,
            media=[MediaOut.of(link.media) for link in p.media_links],
            targets=[
                TargetOut(
                    id=t.id,
                    account=AccountOut.model_validate(t.account),
                    caption_override=t.caption_override,
                    status=t.status,
                    attempts=t.attempts,
                    permalink=t.permalink,
                    error=t.error,
                    published_at=t.published_at,
                )
                for t in p.targets
            ],
        )


class PostIn(BaseModel):
    caption: str = Field(default="", max_length=20000)
    account_ids: list[uuid.UUID] = []
    media_ids: list[uuid.UUID] = []
    scheduled_at: datetime | None = None
    publish_now: bool = False
    # Per-account caption, keyed by account id.
    caption_overrides: dict[uuid.UUID, str] = {}


class PostPatch(BaseModel):
    caption: str | None = Field(default=None, max_length=20000)
    account_ids: list[uuid.UUID] | None = None
    media_ids: list[uuid.UUID] | None = None
    caption_overrides: dict[uuid.UUID, str] | None = None


class ScheduleIn(BaseModel):
    scheduled_at: datetime | None = None  # None = publish now


class PresignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    size: int = Field(gt=0)


class PresignOut(BaseModel):
    media: MediaOut
    upload_url: str
    upload_method: str
    upload_headers: dict[str, str]


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    llm_publish_mode: str


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    llm_publish_mode: str | None = Field(default=None, pattern="^(draft|direct)$")
