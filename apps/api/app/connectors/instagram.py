"""Instagram connector (Instagram API with Instagram Login, professional accounts)."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.connectors.base import (
    AccountAuth,
    ConnectedAccount,
    Connector,
    ConnectorError,
    MediaItem,
    PublishContent,
    PublishResult,
    TokenSet,
)
from app.connectors.meta import graph_request

SCOPES = ["instagram_business_basic", "instagram_business_content_publish"]
MAX_CAROUSEL = 10
MAX_CAPTION = 2200


def _expiry(body: dict[str, Any]) -> datetime | None:
    seconds = body.get("expires_in")
    return datetime.now(UTC) + timedelta(seconds=int(seconds)) if seconds else None


class InstagramConnector(Connector):
    platform = "instagram"
    label = "Instagram"
    # Long-lived tokens last 60 days and can be renewed once they are a day old.
    refresh_margin = timedelta(days=7)
    poll_interval = 10.0
    poll_timeout = 300.0

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    @property
    def _s(self):
        return get_settings()

    @property
    def configured(self) -> bool:
        return bool(self._s.instagram_app_id and self._s.instagram_app_secret)

    @property
    def _graph(self) -> str:
        return f"https://graph.instagram.com/{self._s.meta_graph_version}"

    async def _request(self, method: str, url: str, **kw: Any) -> dict[str, Any]:
        return await graph_request(self._client, "Instagram", method, url, **kw)

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_id": self._s.instagram_app_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": ",".join(SCOPES),
                "state": state,
                # Always show the login screen, so a second account can be connected.
                "force_reauth": "true",
            }
        )
        return f"https://www.instagram.com/oauth/authorize?{query}"

    async def exchange_code(
        self, code: str, redirect_uri: str, state: str = ""
    ) -> list[ConnectedAccount]:
        short = await self._request(
            "POST",
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": self._s.instagram_app_id,
                "client_secret": self._s.instagram_app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code.removesuffix("#_"),
            },
        )
        if isinstance(short.get("data"), list) and short["data"]:
            short = short["data"][0]
        long = await self._request(
            "GET",
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self._s.instagram_app_secret,
                "access_token": short["access_token"],
            },
        )
        me = await self._request(
            "GET",
            f"{self._graph}/me",
            params={
                "fields": "user_id,username,name,profile_picture_url",
                "access_token": long["access_token"],
            },
        )
        return [
            ConnectedAccount(
                external_id=str(me["user_id"]),
                display_name=me.get("name") or me.get("username") or str(me["user_id"]),
                username=me.get("username"),
                avatar_url=me.get("profile_picture_url"),
                access_token=long["access_token"],
                token_expires_at=_expiry(long),
            )
        ]

    async def refresh(self, access_token: str, refresh_token: str | None) -> TokenSet | None:
        body = await self._request(
            "GET",
            "https://graph.instagram.com/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": access_token},
        )
        return TokenSet(access_token=body["access_token"], token_expires_at=_expiry(body))

    def validate(self, content: PublishContent) -> list[str]:
        problems = []
        if not content.media:
            problems.append("Instagram : une image ou une vidéo est obligatoire.")
        if len(content.media) > MAX_CAROUSEL:
            problems.append(f"Instagram : {MAX_CAROUSEL} médias maximum par carrousel.")
        if any(m.kind == "image" and m.content_type != "image/jpeg" for m in content.media):
            problems.append("Instagram : les images doivent être au format JPG.")
        if len(content.caption) > MAX_CAPTION:
            problems.append(f"Instagram : {MAX_CAPTION} caractères maximum.")
        return problems

    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult:
        account = f"{self._graph}/{auth.external_id}"
        token = {"access_token": auth.access_token}

        async def container(**params: str) -> str:
            res = await self._request("POST", f"{account}/media", data={**token, **params})
            return res["id"]

        def source(item: MediaItem, *, reel: bool) -> dict[str, str]:
            if item.kind == "video":
                return {"media_type": "REELS" if reel else "VIDEO", "video_url": item.url}
            return {"image_url": item.url}

        if len(content.media) == 1:
            creation_id = await container(
                **source(content.media[0], reel=True), caption=content.caption
            )
        else:
            children = []
            for item in content.media:
                child = await container(**source(item, reel=False), is_carousel_item="true")
                if item.kind == "video":
                    await self._wait_ready(child, token)
                children.append(child)
            creation_id = await container(
                media_type="CAROUSEL", children=",".join(children), caption=content.caption
            )
        await self._wait_ready(creation_id, token)

        res = await self._request(
            "POST", f"{account}/media_publish", data={**token, "creation_id": creation_id}
        )
        return PublishResult(res["id"], await self._permalink(res["id"], token))

    async def _wait_ready(self, container_id: str, token: dict[str, str]) -> None:
        """Instagram downloads and transcodes the media before it can be published."""
        deadline = asyncio.get_running_loop().time() + self.poll_timeout
        while True:
            res = await self._request(
                "GET",
                f"{self._graph}/{container_id}",
                params={**token, "fields": "status_code,status"},
            )
            status = res.get("status_code")
            if status in ("FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                detail = res.get("status") or "vérifie le format et les dimensions du fichier"
                raise ConnectorError(f"Instagram a refusé le média : {detail}.")
            if asyncio.get_running_loop().time() >= deadline:
                # Nothing is published yet, so trying again cannot create a duplicate.
                raise ConnectorError(
                    "Instagram met trop de temps à traiter le média.", retryable=True
                )
            await asyncio.sleep(self.poll_interval)

    async def _permalink(self, media_id: str, token: dict[str, str]) -> str | None:
        try:
            res = await self._request(
                "GET", f"{self._graph}/{media_id}", params={**token, "fields": "permalink"}
            )
        except ConnectorError:
            return None
        return res.get("permalink")
