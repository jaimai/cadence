"""Contract every social platform connector implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


class ConnectorError(Exception):
    def __init__(self, message: str, *, retryable: bool = False, reauth: bool = False):
        super().__init__(message)
        self.retryable = retryable
        self.reauth = reauth


@dataclass
class ConnectedAccount:
    """One publishable identity returned by an OAuth flow (a Page, a profile...)."""

    external_id: str
    display_name: str
    access_token: str
    username: str | None = None
    avatar_url: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None


@dataclass
class MediaItem:
    url: str
    kind: str  # "image" | "video"
    content_type: str


@dataclass
class PublishContent:
    caption: str
    media: list[MediaItem] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountAuth:
    external_id: str
    access_token: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishResult:
    external_post_id: str
    permalink: str | None = None


class Connector(ABC):
    platform: str
    label: str
    # Renew tokens this long before they expire. None = tokens never expire.
    refresh_margin: timedelta | None = None
    # True when renewal is only possible with a refresh token (not every app gets one).
    needs_refresh_token: bool = False

    @property
    @abstractmethod
    def configured(self) -> bool:
        """True when the app credentials for this platform are set."""

    @abstractmethod
    def authorize_url(self, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str, state: str = ""
    ) -> list[ConnectedAccount]:
        """`state` is the value sent to authorize_url (needed by PKCE flows)."""

    @abstractmethod
    def validate(self, content: PublishContent) -> list[str]:
        """Human-readable problems that would make publish fail. Empty = OK."""

    @abstractmethod
    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult: ...

    async def refresh(self, access_token: str, refresh_token: str | None) -> TokenSet | None:
        """Renew tokens. None when the platform has nothing to refresh."""
        return None
