"""TikTok connector (Content Posting API, direct post).

Media is pulled by TikTok from our public URLs: the media domain must be verified
in the TikTok developer portal, otherwise posts fail with `url_ownership_unverified`.
"""

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
    PublishContent,
    PublishResult,
    TokenSet,
)

API = "https://open.tiktokapis.com/v2"
SCOPES = ["user.info.basic", "video.publish"]
MAX_PHOTOS = 35
MAX_VIDEO_CAPTION = 2200
MAX_PHOTO_TITLE = 90
MAX_PHOTO_DESCRIPTION = 4000
PHOTO_TYPES = {"image/jpeg", "image/webp"}
RETRYABLE = {"rate_limit_exceeded", "internal_error"}
MESSAGES = {
    "unaudited_client_can_only_post_to_private_accounts": (
        "Tant que l'app TikTok n'est pas auditée, le compte TikTok doit être en mode privé."
    ),
    "url_ownership_unverified": (
        "Le domaine des médias n'est pas vérifié dans le portail développeur TikTok."
    ),
    "privacy_level_option_mismatch": "Cette visibilité n'est pas autorisée pour ce compte.",
    "spam_risk_too_many_posts": "TikTok limite ce compte : trop de publications récentes.",
    "spam_risk_user_banned_from_posting": "TikTok a suspendu la publication pour ce compte.",
    "reached_active_user_cap": "L'app TikTok a atteint son quota quotidien d'utilisateurs actifs.",
    "scope_not_authorized": "Autorisation de publier manquante : reconnecte ce compte.",
}


def _tokens(body: dict[str, Any]) -> TokenSet:
    return TokenSet(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        token_expires_at=datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 7200))),
    )


class TikTokConnector(Connector):
    platform = "tiktok"
    label = "TikTok"
    # Access tokens are short-lived; the refresh token is rotated on every renewal.
    refresh_margin = timedelta(minutes=30)
    poll_interval = 5.0
    poll_timeout = 300.0

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    @property
    def _s(self):
        return get_settings()

    @property
    def configured(self) -> bool:
        return bool(self._s.tiktok_client_key and self._s.tiktok_client_secret)

    async def _request(self, method: str, url: str, **kw: Any) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=60)
        try:
            resp = await client.request(method, url, **kw)
        except httpx.HTTPError as e:
            raise ConnectorError(f"TikTok injoignable : {e}", retryable=True) from e
        finally:
            if self._client is None:
                await client.aclose()
        try:
            body = resp.json()
        except ValueError:
            body = {}
        err = body.get("error")
        if isinstance(err, str):  # OAuth endpoints: {"error": "...", "error_description": "..."}
            raise ConnectorError(
                body.get("error_description") or err,
                reauth=err in ("invalid_grant", "invalid_request"),
            )
        code = (err or {}).get("code", "ok" if resp.is_success else "")
        if resp.is_success and code == "ok":
            return body
        raise ConnectorError(
            MESSAGES.get(code)
            or (err or {}).get("message")
            or f"Erreur TikTok HTTP {resp.status_code}",
            retryable=code in RETRYABLE or resp.status_code >= 500,
            reauth=code in ("access_token_invalid", "scope_not_authorized"),
        )

    async def _api(
        self, token: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        res = await self._request(
            "POST",
            f"{API}{path}",
            json=body or {},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
        return res.get("data") or {}

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_key": self._s.tiktok_client_key,
                "response_type": "code",
                "scope": ",".join(SCOPES),
                "redirect_uri": redirect_uri,
                "state": state,
                # Always show the consent screen: it is where the user can switch account.
                "disable_auto_auth": "1",
            }
        )
        return f"https://www.tiktok.com/v2/auth/authorize/?{query}"

    async def _token(self, **grant: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"{API}/oauth/token/",
            data={
                "client_key": self._s.tiktok_client_key,
                "client_secret": self._s.tiktok_client_secret,
                **grant,
            },
        )

    async def exchange_code(
        self, code: str, redirect_uri: str, state: str = ""
    ) -> list[ConnectedAccount]:
        body = await self._token(
            grant_type="authorization_code", code=code, redirect_uri=redirect_uri
        )
        if "video.publish" not in body.get("scope", ""):
            raise ConnectorError("L'autorisation de publier a été refusée sur TikTok.")
        tokens = _tokens(body)
        creator = await self._api(tokens.access_token, "/post/publish/creator_info/query/")
        username = creator.get("creator_username")
        return [
            ConnectedAccount(
                external_id=body["open_id"],
                display_name=creator.get("creator_nickname") or username or "Compte TikTok",
                username=username,
                avatar_url=creator.get("creator_avatar_url"),
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_expires_at=tokens.token_expires_at,
            )
        ]

    async def refresh(self, access_token: str, refresh_token: str | None) -> TokenSet | None:
        if not refresh_token:
            raise ConnectorError("Session TikTok expirée.", reauth=True)
        return _tokens(await self._token(grant_type="refresh_token", refresh_token=refresh_token))

    def validate(self, content: PublishContent) -> list[str]:
        problems = []
        images = [m for m in content.media if m.kind == "image"]
        videos = [m for m in content.media if m.kind == "video"]
        if not content.media:
            problems.append("TikTok : une vidéo ou des photos sont obligatoires.")
        if images and videos:
            problems.append("TikTok : impossible de mélanger photos et vidéo dans un même post.")
        if len(videos) > 1:
            problems.append("TikTok : une seule vidéo par post.")
        if len(images) > MAX_PHOTOS:
            problems.append(f"TikTok : {MAX_PHOTOS} photos maximum par post.")
        if any(m.content_type not in PHOTO_TYPES for m in images):
            problems.append("TikTok : les photos doivent être au format JPG ou WebP.")
        limit = MAX_VIDEO_CAPTION if videos else MAX_PHOTO_DESCRIPTION
        if len(content.caption) > limit:
            problems.append(f"TikTok : {limit} caractères maximum.")
        return problems

    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult:
        token = auth.access_token
        creator = await self._api(token, "/post/publish/creator_info/query/")
        privacy = content.options.get("privacy_level") or self._s.tiktok_privacy_level
        allowed = creator.get("privacy_level_options") or []
        if privacy not in allowed:
            raise ConnectorError(
                f"TikTok : la visibilité {privacy} n'est pas disponible pour ce compte "
                f"(possibles : {', '.join(allowed) or 'aucune'})."
            )
        post_info: dict[str, Any] = {
            "privacy_level": privacy,
            # A creator who turned an interaction off must not have it turned back on.
            "disable_comment": bool(creator.get("comment_disabled")),
        }
        videos = [m for m in content.media if m.kind == "video"]
        if videos:
            post_info |= {
                "title": content.caption,
                "disable_duet": bool(creator.get("duet_disabled")),
                "disable_stitch": bool(creator.get("stitch_disabled")),
            }
            init = await self._api(
                token,
                "/post/publish/video/init/",
                {
                    "post_info": post_info,
                    "source_info": {"source": "PULL_FROM_URL", "video_url": videos[0].url},
                },
            )
        else:
            caption = content.caption.strip()
            short = len(caption) <= MAX_PHOTO_TITLE
            post_info |= {
                "title": caption if short else caption.splitlines()[0][:MAX_PHOTO_TITLE],
                "description": "" if short else caption,
            }
            init = await self._api(
                token,
                "/post/publish/content/init/",
                {
                    "media_type": "PHOTO",
                    "post_mode": "DIRECT_POST",
                    "post_info": post_info,
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "photo_cover_index": 0,
                        "photo_images": [m.url for m in content.media],
                    },
                },
            )
        publish_id = init["publish_id"]
        post_id = await self._wait_published(token, publish_id)
        username = creator.get("creator_username")
        permalink = (
            f"https://www.tiktok.com/@{username}/{'video' if videos else 'photo'}/{post_id}"
            if post_id and username
            else None
        )
        return PublishResult(str(post_id or publish_id), permalink)

    async def _wait_published(self, token: str, publish_id: str) -> str | None:
        """Wait for TikTok to download and process the media. Returns the public post id."""
        deadline = asyncio.get_running_loop().time() + self.poll_timeout
        while True:
            try:
                data = await self._api(
                    token, "/post/publish/status/fetch/", {"publish_id": publish_id}
                )
            except ConnectorError as e:
                # TikTok accepted the post at init: a failed status check must not
                # be reported as a failed publication (a retry would post twice).
                if not e.retryable:
                    return None
                data = {}
            status = data.get("status")
            if status == "PUBLISH_COMPLETE":
                ids = data.get("publicaly_available_post_id") or []  # sic, TikTok's spelling
                return str(ids[0]) if ids else None
            if status == "FAILED":
                reason = data.get("fail_reason") or "raison inconnue"
                raise ConnectorError(f"TikTok a refusé le contenu : {reason}.")
            if asyncio.get_running_loop().time() >= deadline:
                return None  # still processing: accepted, TikTok will finish on its side
            await asyncio.sleep(self.poll_interval)
