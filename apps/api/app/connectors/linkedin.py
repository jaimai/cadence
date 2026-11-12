"""LinkedIn connector: posts on a member's personal profile (Posts API).

Company pages need the `w_organization_social` permission, which LinkedIn only
grants through its Community Management API review: not handled here.
"""

import re
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
from app.connectors.files import downloaded, read_range

API = "https://api.linkedin.com"
SCOPES = ["openid", "profile", "w_member_social"]
MAX_TEXT = 3000
MAX_IMAGES = 20
IMAGE_TYPES = {"image/jpeg", "image/png"}
# Reserved by LinkedIn's "little" text format. "#" is left alone so hashtags keep working.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>*_~])")


def escape(text: str) -> str:
    return _RESERVED.sub(r"\\\1", text)


def _tokens(body: dict[str, Any]) -> TokenSet:
    seconds = body.get("expires_in")
    return TokenSet(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        token_expires_at=datetime.now(UTC) + timedelta(seconds=int(seconds)) if seconds else None,
    )


class LinkedInConnector(Connector):
    platform = "linkedin"
    label = "LinkedIn"
    # Tokens last 60 days. Only some apps receive a refresh token; without one the
    # account simply has to be reconnected when the token expires.
    refresh_margin = timedelta(days=7)
    needs_refresh_token = True

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    @property
    def _s(self):
        return get_settings()

    @property
    def configured(self) -> bool:
        return bool(self._s.linkedin_client_id and self._s.linkedin_client_secret)

    async def _send(self, method: str, url: str, **kw: Any) -> httpx.Response:
        client = self._client or httpx.AsyncClient(timeout=300)
        try:
            resp = await client.request(method, url, **kw)
        except httpx.HTTPError as e:
            raise ConnectorError(f"LinkedIn injoignable : {e}", retryable=True) from e
        finally:
            if self._client is None:
                await client.aclose()
        if resp.is_success:
            return resp
        try:
            body = resp.json()
        except ValueError:
            body = {}
        message = body.get("message") or body.get("error_description")
        raise ConnectorError(
            message or f"Erreur LinkedIn HTTP {resp.status_code}",
            retryable=resp.status_code in (409, 429) or resp.status_code >= 500,
            reauth=resp.status_code == 401,
        )

    async def _rest(self, token: str, path: str, body: dict[str, Any]) -> httpx.Response:
        return await self._send(
            "POST",
            f"{API}/rest/{path}",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "LinkedIn-Version": self._s.linkedin_version,
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._s.linkedin_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": " ".join(SCOPES),
            }
        )
        return f"https://www.linkedin.com/oauth/v2/authorization?{query}"

    async def _token(self, **grant: str) -> TokenSet:
        resp = await self._send(
            "POST",
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "client_id": self._s.linkedin_client_id,
                "client_secret": self._s.linkedin_client_secret,
                **grant,
            },
        )
        return _tokens(resp.json())

    async def exchange_code(
        self, code: str, redirect_uri: str, state: str = ""
    ) -> list[ConnectedAccount]:
        tokens = await self._token(
            grant_type="authorization_code", code=code, redirect_uri=redirect_uri
        )
        me = (
            await self._send(
                "GET",
                f"{API}/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
        ).json()
        return [
            ConnectedAccount(
                external_id=me["sub"],
                display_name=me.get("name") or "Profil LinkedIn",
                avatar_url=me.get("picture"),
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_expires_at=tokens.token_expires_at,
            )
        ]

    async def refresh(self, access_token: str, refresh_token: str | None) -> TokenSet | None:
        if not refresh_token:
            return None
        return await self._token(grant_type="refresh_token", refresh_token=refresh_token)

    def validate(self, content: PublishContent) -> list[str]:
        problems = []
        images = [m for m in content.media if m.kind == "image"]
        videos = [m for m in content.media if m.kind == "video"]
        if not content.caption.strip() and not content.media:
            problems.append("LinkedIn : le post doit contenir un texte ou un média.")
        if images and videos:
            problems.append("LinkedIn : impossible de mélanger photos et vidéo dans un même post.")
        if len(videos) > 1:
            problems.append("LinkedIn : une seule vidéo par post.")
        if len(images) > MAX_IMAGES:
            problems.append(f"LinkedIn : {MAX_IMAGES} images maximum par post.")
        if any(m.content_type not in IMAGE_TYPES for m in images):
            problems.append("LinkedIn : les images doivent être au format JPG ou PNG.")
        if any(m.content_type != "video/mp4" for m in videos):
            problems.append("LinkedIn : la vidéo doit être au format MP4.")
        if len(content.caption) > MAX_TEXT:
            problems.append(f"LinkedIn : {MAX_TEXT} caractères maximum.")
        return problems

    async def _upload_image(self, token: str, owner: str, item: MediaItem) -> str:
        init = (
            await self._rest(
                token,
                "images?action=initializeUpload",
                {"initializeUploadRequest": {"owner": owner}},
            )
        ).json()["value"]
        async with downloaded(item.url, self._client) as path:
            await self._send(
                "PUT",
                init["uploadUrl"],
                content=path.read_bytes(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": item.content_type},
            )
        return init["image"]

    async def _upload_video(self, token: str, owner: str, item: MediaItem) -> str:
        async with downloaded(item.url, self._client) as path:
            init = (
                await self._rest(
                    token,
                    "videos?action=initializeUpload",
                    {
                        "initializeUploadRequest": {
                            "owner": owner,
                            "fileSizeBytes": path.stat().st_size,
                            "uploadCaptions": False,
                            "uploadThumbnail": False,
                        }
                    },
                )
            ).json()["value"]
            etags = []
            for part in init["uploadInstructions"]:
                resp = await self._send(
                    "PUT",
                    part["uploadUrl"],
                    content=read_range(path, part["firstByte"], part["lastByte"]),
                    headers={"Content-Type": "application/octet-stream"},
                )
                etags.append(resp.headers.get("etag", "").strip('"'))
        await self._rest(
            token,
            "videos?action=finalizeUpload",
            {
                "finalizeUploadRequest": {
                    "video": init["video"],
                    "uploadToken": init.get("uploadToken", ""),
                    "uploadedPartIds": etags,
                }
            },
        )
        return init["video"]

    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult:
        token, owner = auth.access_token, f"urn:li:person:{auth.external_id}"
        images = [m for m in content.media if m.kind == "image"]
        videos = [m for m in content.media if m.kind == "video"]
        post: dict[str, Any] = {
            "author": owner,
            "commentary": escape(content.caption),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        # A member token cannot read back the processing status of an upload: LinkedIn
        # publishes the post on its own once the media is ready.
        if videos:
            post["content"] = {"media": {"id": await self._upload_video(token, owner, videos[0])}}
        elif len(images) == 1:
            post["content"] = {"media": {"id": await self._upload_image(token, owner, images[0])}}
        elif images:
            ids = [await self._upload_image(token, owner, img) for img in images]
            post["content"] = {"multiImage": {"images": [{"id": i} for i in ids]}}

        resp = await self._rest(token, "posts", post)
        urn = resp.headers.get("x-restli-id")
        if not urn:
            raise ConnectorError("LinkedIn n'a pas confirmé la création du post.")
        return PublishResult(urn, f"https://www.linkedin.com/feed/update/{urn}/")
