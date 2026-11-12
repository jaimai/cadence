"""X (Twitter) connector: API v2 with OAuth 2.0 PKCE."""

import asyncio
import base64
import hashlib
import hmac
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
from app.connectors.files import chunks, downloaded

API = "https://api.x.com/2"
SCOPES = ["tweet.read", "tweet.write", "users.read", "media.write", "offline.access"]
MAX_IMAGES = 4
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
CHUNK = 4 * 1024 * 1024  # X accepts up to 5 MB per chunk


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _tokens(body: dict[str, Any]) -> TokenSet:
    return TokenSet(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        token_expires_at=datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 7200))),
    )


class XConnector(Connector):
    platform = "x"
    label = "X"
    refresh_margin = timedelta(minutes=30)
    poll_interval: float | None = None  # None = wait what X asks for
    poll_timeout = 300.0

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    @property
    def _s(self):
        return get_settings()

    @property
    def configured(self) -> bool:
        return bool(self._s.x_client_id and self._s.x_client_secret)

    def _verifier(self, state: str) -> str:
        """PKCE verifier derived from the signed state, so nothing has to be stored
        between the redirect to X and the callback."""
        return _b64(hmac.new(self._s.secret_key.encode(), state.encode(), hashlib.sha256).digest())

    async def _request(self, method: str, url: str, **kw: Any) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=120)
        try:
            resp = await client.request(method, url, **kw)
        except httpx.HTTPError as e:
            raise ConnectorError(f"X injoignable : {e}", retryable=True) from e
        finally:
            if self._client is None:
                await client.aclose()
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.is_success and isinstance(body, dict):
            return body
        errors = body.get("errors") if isinstance(body, dict) else None
        message = (
            (errors[0].get("message") or errors[0].get("detail") if errors else None)
            or body.get("detail")
            or body.get("error_description")
            or body.get("title")
            or f"Erreur X HTTP {resp.status_code}"
        )
        raise ConnectorError(
            message,
            retryable=resp.status_code == 429 or resp.status_code >= 500,
            reauth=resp.status_code == 401 or body.get("error") == "invalid_grant",
        )

    def _bearer(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        challenge = _b64(hashlib.sha256(self._verifier(state).encode()).digest())
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._s.x_client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(SCOPES),
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://x.com/i/oauth2/authorize?{query}"

    async def _token(self, **grant: str) -> TokenSet:
        body = await self._request(
            "POST",
            f"{API}/oauth2/token",
            data={"client_id": self._s.x_client_id, **grant},
            auth=(self._s.x_client_id, self._s.x_client_secret),
        )
        return _tokens(body)

    async def exchange_code(
        self, code: str, redirect_uri: str, state: str = ""
    ) -> list[ConnectedAccount]:
        tokens = await self._token(
            grant_type="authorization_code",
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=self._verifier(state),
        )
        me = (
            await self._request(
                "GET",
                f"{API}/users/me",
                params={"user.fields": "profile_image_url"},
                headers=self._bearer(tokens.access_token),
            )
        )["data"]
        return [
            ConnectedAccount(
                external_id=me["id"],
                display_name=me.get("name") or me["username"],
                username=me["username"],
                avatar_url=me.get("profile_image_url"),
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_expires_at=tokens.token_expires_at,
                meta={"username": me["username"]},
            )
        ]

    async def refresh(self, access_token: str, refresh_token: str | None) -> TokenSet | None:
        if not refresh_token:
            raise ConnectorError("Session X expirée.", reauth=True)
        return await self._token(grant_type="refresh_token", refresh_token=refresh_token)

    def validate(self, content: PublishContent) -> list[str]:
        problems = []
        images = [m for m in content.media if m.kind == "image"]
        videos = [m for m in content.media if m.kind == "video"]
        limit = self._s.x_max_chars
        if not content.caption.strip() and not content.media:
            problems.append("X : le post doit contenir un texte ou un média.")
        if images and videos:
            problems.append("X : impossible de mélanger photos et vidéo dans un même post.")
        if len(videos) > 1:
            problems.append("X : une seule vidéo par post.")
        if len(images) > MAX_IMAGES:
            problems.append(f"X : {MAX_IMAGES} images maximum par post.")
        if any(m.content_type not in IMAGE_TYPES for m in images):
            problems.append("X : les images doivent être au format JPG, PNG ou WebP.")
        if len(content.caption) > limit:
            problems.append(f"X : {limit} caractères maximum.")
        return problems

    async def _upload(self, token: str, item: MediaItem) -> str:
        headers = self._bearer(token)
        async with downloaded(item.url, self._client) as path:
            init = await self._request(
                "POST",
                f"{API}/media/upload/initialize",
                headers=headers,
                json={
                    "media_type": item.content_type,
                    "total_bytes": path.stat().st_size,
                    "media_category": "tweet_video" if item.kind == "video" else "tweet_image",
                },
            )
            media_id = init["data"]["id"]
            for index, chunk in enumerate(chunks(path, CHUNK)):
                await self._request(
                    "POST",
                    f"{API}/media/upload/{media_id}/append",
                    headers=headers,
                    data={"segment_index": str(index)},
                    files={"media": ("chunk", chunk, "application/octet-stream")},
                )
        done = await self._request(
            "POST", f"{API}/media/upload/{media_id}/finalize", headers=headers
        )
        await self._wait_processed(token, media_id, (done.get("data") or {}).get("processing_info"))
        return media_id

    async def _wait_processed(self, token: str, media_id: str, info: dict[str, Any] | None) -> None:
        """Videos are transcoded after upload and cannot be attached before that ends."""
        deadline = asyncio.get_running_loop().time() + self.poll_timeout
        while info and info.get("state") != "succeeded":
            if info.get("state") == "failed":
                reason = (info.get("error") or {}).get("message") or "format non pris en charge"
                raise ConnectorError(f"X a refusé le média : {reason}.")
            if asyncio.get_running_loop().time() >= deadline:
                # Nothing is posted yet, so trying again cannot create a duplicate.
                raise ConnectorError("X met trop de temps à traiter le média.", retryable=True)
            wait = info.get("check_after_secs", 5)
            await asyncio.sleep(wait if self.poll_interval is None else self.poll_interval)
            status = await self._request(
                "GET",
                f"{API}/media/upload",
                headers=self._bearer(token),
                params={"command": "STATUS", "media_id": media_id},
            )
            info = (status.get("data") or {}).get("processing_info")

    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult:
        token = auth.access_token
        body: dict[str, Any] = {"text": content.caption}
        if content.media:
            body["media"] = {"media_ids": [await self._upload(token, m) for m in content.media]}
        res = await self._request("POST", f"{API}/tweets", json=body, headers=self._bearer(token))
        post_id = res["data"]["id"]
        username = auth.meta.get("username")
        return PublishResult(
            post_id, f"https://x.com/{username}/status/{post_id}" if username else None
        )
