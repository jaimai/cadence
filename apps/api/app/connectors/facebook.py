"""Facebook Pages connector (Graph API). Each Page is one social account."""

from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.connectors.base import (
    AccountAuth,
    ConnectedAccount,
    Connector,
    ConnectorError,
    PublishContent,
    PublishResult,
)
from app.connectors.meta import graph_request

SCOPES = ["pages_show_list", "pages_manage_posts", "pages_read_engagement"]
MAX_PHOTOS = 10


class FacebookConnector(Connector):
    platform = "facebook"
    label = "Facebook"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    @property
    def _s(self):
        return get_settings()

    @property
    def configured(self) -> bool:
        return bool(self._s.meta_app_id and self._s.meta_app_secret)

    @property
    def _graph(self) -> str:
        return f"https://graph.facebook.com/{self._s.meta_graph_version}"

    async def _request(self, method: str, url: str, **kw: Any) -> dict[str, Any]:
        return await graph_request(self._client, "Facebook", method, url, **kw)

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_id": self._s.meta_app_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": ",".join(SCOPES),
                "response_type": "code",
            }
        )
        return f"https://www.facebook.com/{self._s.meta_graph_version}/dialog/oauth?{query}"

    async def exchange_code(
        self, code: str, redirect_uri: str, state: str = ""
    ) -> list[ConnectedAccount]:
        app = {"client_id": self._s.meta_app_id, "client_secret": self._s.meta_app_secret}
        token_url = f"{self._graph}/oauth/access_token"
        short = await self._request(
            "GET", token_url, params={**app, "redirect_uri": redirect_uri, "code": code}
        )
        # Page tokens derived from a long-lived user token do not expire.
        long = await self._request(
            "GET",
            token_url,
            params={
                **app,
                "grant_type": "fb_exchange_token",
                "fb_exchange_token": short["access_token"],
            },
        )
        accounts: list[ConnectedAccount] = []
        url: str | None = f"{self._graph}/me/accounts"
        params: dict[str, Any] | None = {
            "fields": "id,name,username,access_token,picture{url}",
            "limit": 100,
            "access_token": long["access_token"],
        }
        while url:
            page = await self._request("GET", url, params=params)
            for p in page.get("data", []):
                if not p.get("access_token"):
                    continue
                accounts.append(
                    ConnectedAccount(
                        external_id=p["id"],
                        display_name=p.get("name") or p["id"],
                        username=p.get("username"),
                        avatar_url=((p.get("picture") or {}).get("data") or {}).get("url"),
                        access_token=p["access_token"],
                    )
                )
            url, params = (page.get("paging") or {}).get("next"), None
        return accounts

    def validate(self, content: PublishContent) -> list[str]:
        problems = []
        images = [m for m in content.media if m.kind == "image"]
        videos = [m for m in content.media if m.kind == "video"]
        if not content.caption.strip() and not content.media:
            problems.append("Facebook : le post doit contenir un texte ou un média.")
        if images and videos:
            problems.append("Facebook : impossible de mélanger photos et vidéo dans un même post.")
        if len(videos) > 1:
            problems.append("Facebook : une seule vidéo par post.")
        if len(images) > MAX_PHOTOS:
            problems.append(f"Facebook : {MAX_PHOTOS} photos maximum par post.")
        return problems

    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult:
        page = f"{self._graph}/{auth.external_id}"
        token = {"access_token": auth.access_token}
        images = [m for m in content.media if m.kind == "image"]
        videos = [m for m in content.media if m.kind == "video"]

        if videos:
            res = await self._request(
                "POST",
                f"{page}/videos",
                data={**token, "file_url": videos[0].url, "description": content.caption},
            )
            post_id = res["id"]
        elif len(images) == 1:
            res = await self._request(
                "POST",
                f"{page}/photos",
                data={**token, "url": images[0].url, "caption": content.caption},
            )
            post_id = res.get("post_id") or res["id"]
        else:
            data: dict[str, Any] = {**token, "message": content.caption}
            for i, img in enumerate(images):
                photo = await self._request(
                    "POST", f"{page}/photos", data={**token, "url": img.url, "published": "false"}
                )
                data[f"attached_media[{i}]"] = f'{{"media_fbid":"{photo["id"]}"}}'
            res = await self._request("POST", f"{page}/feed", data=data)
            post_id = res["id"]

        return PublishResult(
            external_post_id=post_id, permalink=await self._permalink(post_id, token)
        )

    async def _permalink(self, post_id: str, token: dict[str, str]) -> str | None:
        # Best effort: the post is live even if this lookup fails.
        try:
            res = await self._request(
                "GET", f"{self._graph}/{post_id}", params={**token, "fields": "permalink_url"}
            )
        except ConnectorError:
            return None
        link = res.get("permalink_url")
        if link and link.startswith("/"):
            link = f"https://www.facebook.com{link}"
        return link
