import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True), dict[str, Any]: JSONB}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _fk(target: str, **kw: Any) -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete="CASCADE"), **kw)


def _created() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created()


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(120))
    # "draft": posts created by an LLM wait for approval. "direct": they go out.
    llm_publish_mode: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[datetime] = _created()


class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[uuid.UUID] = _fk("users.id", primary_key=True)
    workspace_id: Mapped[uuid.UUID] = _fk("workspaces.id", primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="owner")


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = _pk()
    workspace_id: Mapped[uuid.UUID] = _fk("workspaces.id", index=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _created()
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("workspace_id", "platform", "external_id"),)
    id: Mapped[uuid.UUID] = _pk()
    workspace_id: Mapped[uuid.UUID] = _fk("workspaces.id", index=True)
    platform: Mapped[str] = mapped_column(String(24))
    external_id: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None]
    # "active" | "needs_reauth"
    status: Mapped[str] = mapped_column(String(16), default="active")
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = _created()


class OAuthLink(Base):
    """Short-lived link, shown as a QR code, to connect an account from another device."""

    __tablename__ = "oauth_links"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = _fk("workspaces.id", index=True)
    platform: Mapped[str] = mapped_column(String(24))
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = _created()


class Media(Base):
    __tablename__ = "media"
    id: Mapped[uuid.UUID] = _pk()
    workspace_id: Mapped[uuid.UUID] = _fk("workspaces.id", index=True)
    key: Mapped[str] = mapped_column(String(512), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(8))  # "image" | "video"
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | ready
    created_at: Mapped[datetime] = _created()


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (Index("ix_posts_due", "status", "scheduled_at"),)
    id: Mapped[uuid.UUID] = _pk()
    workspace_id: Mapped[uuid.UUID] = _fk("workspaces.id", index=True)
    caption: Mapped[str] = mapped_column(Text, default="")
    # draft | scheduled | publishing | published | partial | failed
    status: Mapped[str] = mapped_column(String(16), default="draft")
    scheduled_at: Mapped[datetime | None]
    source: Mapped[str] = mapped_column(String(8), default="web")  # web | mcp
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    targets: Mapped[list["PostTarget"]] = relationship(
        back_populates="post", cascade="all, delete-orphan", lazy="selectin"
    )
    media_links: Mapped[list["PostMedia"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="PostMedia.position"
    )


class PostMedia(Base):
    __tablename__ = "post_media"
    post_id: Mapped[uuid.UUID] = _fk("posts.id", primary_key=True)
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    media: Mapped[Media] = relationship(lazy="joined")


class PostTarget(Base):
    __tablename__ = "post_targets"
    __table_args__ = (UniqueConstraint("post_id", "social_account_id"),)
    id: Mapped[uuid.UUID] = _pk()
    post_id: Mapped[uuid.UUID] = _fk("posts.id", index=True)
    social_account_id: Mapped[uuid.UUID] = _fk("social_accounts.id", index=True)
    caption_override: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # pending | publishing | published | failed
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None]
    locked_at: Mapped[datetime | None]
    external_post_id: Mapped[str | None] = mapped_column(String(255))
    permalink: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None]

    post: Mapped[Post] = relationship(back_populates="targets")
    account: Mapped[SocialAccount] = relationship(lazy="joined")
