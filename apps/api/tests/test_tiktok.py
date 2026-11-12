import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.config import get_settings
from app.connectors.base import AccountAuth, ConnectorError, MediaItem, PublishContent
from app.connectors.tiktok import TikTokConnector

AUTH = AccountAuth("open_1", "tt-token")
JPG = MediaItem("https://cdn.test/a.jpg", "image", "image/jpeg")
PNG = MediaItem("https://cdn.test/a.png", "image", "image/png")
VID = MediaItem("https://cdn.test/v.mp4", "video", "video/mp4")
OK = {"code": "ok", "message": "", "log_id": "x"}
CREATOR = {
    "creator_username": "monapp",
    "creator_nickname": "Mon App",
    "creator_avatar_url": "http://a",
    "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
    "comment_disabled": False,
    "duet_disabled": True,
    "stitch_disabled": False,
}


def connector(handler):
    calls: list[httpx.Request] = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    tt = TikTokConnector(httpx.AsyncClient(transport=httpx.MockTransport(wrapped)))
    tt.poll_interval = 0
    return tt, calls


def api(
    statuses: list[dict] | None = None, creator: dict | None = None, init_error: dict | None = None
):
    statuses = list(
        statuses or [{"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [777]}]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tt-token"
        path = request.url.path
        if path.endswith("/creator_info/query/"):
            return httpx.Response(200, json={"data": creator or CREATOR, "error": OK})
        if path.endswith("/init/"):
            if init_error:
                return httpx.Response(
                    init_error.pop("http", 403), json={"data": {}, "error": init_error}
                )
            return httpx.Response(200, json={"data": {"publish_id": "pub_1"}, "error": OK})
        assert json.loads(request.content) == {"publish_id": "pub_1"}
        return httpx.Response(
            200, json={"data": statuses.pop(0) if len(statuses) > 1 else statuses[0], "error": OK}
        )

    return handler


def body(request: httpx.Request) -> dict:
    return json.loads(request.content)


async def test_video_direct_post():
    tt, calls = connector(
        api(
            [
                {"status": "PROCESSING_DOWNLOAD"},
                {"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [777]},
            ]
        )
    )
    result = await tt.publish(AUTH, PublishContent("Ma vidéo #app", [VID]))
    init = next(c for c in calls if c.url.path.endswith("/video/init/"))
    assert body(init) == {
        "post_info": {
            "privacy_level": "SELF_ONLY",
            "disable_comment": False,
            "title": "Ma vidéo #app",
            "disable_duet": True,
            "disable_stitch": False,
        },
        "source_info": {"source": "PULL_FROM_URL", "video_url": VID.url},
    }
    assert sum(c.url.path.endswith("/status/fetch/") for c in calls) == 2
    assert result.external_post_id == "777"
    assert result.permalink == "https://www.tiktok.com/@monapp/video/777"


async def test_photo_post_splits_long_caption():
    tt, calls = connector(api())
    caption = "Première ligne courte\n" + "détail " * 30
    await tt.publish(AUTH, PublishContent(caption, [JPG, JPG]))
    sent = body(next(c for c in calls if c.url.path.endswith("/content/init/")))
    assert sent["media_type"] == "PHOTO" and sent["post_mode"] == "DIRECT_POST"
    assert sent["post_info"]["title"] == "Première ligne courte"
    assert sent["post_info"]["description"] == caption.strip()
    assert sent["source_info"] == {
        "source": "PULL_FROM_URL",
        "photo_cover_index": 0,
        "photo_images": [JPG.url, JPG.url],
    }


async def test_privacy_level_option_and_mismatch():
    tt, calls = connector(api())
    await tt.publish(AUTH, PublishContent("x", [VID], {"privacy_level": "PUBLIC_TO_EVERYONE"}))
    init = next(c for c in calls if c.url.path.endswith("/video/init/"))
    assert body(init)["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"

    private = {**CREATOR, "privacy_level_options": ["FOLLOWER_OF_CREATOR", "SELF_ONLY"]}
    tt, calls = connector(api(creator=private))
    with pytest.raises(ConnectorError) as e:
        await tt.publish(AUTH, PublishContent("x", [VID], {"privacy_level": "PUBLIC_TO_EVERYONE"}))
    assert "PUBLIC_TO_EVERYONE" in str(e.value)
    assert not any(c.url.path.endswith("/init/") for c in calls)


async def test_still_processing_is_accepted_not_failed():
    tt, _ = connector(api([{"status": "PROCESSING_DOWNLOAD"}]))
    tt.poll_timeout = 0
    result = await tt.publish(AUTH, PublishContent("x", [VID]))
    assert (result.external_post_id, result.permalink) == ("pub_1", None)


async def test_private_post_has_no_public_link():
    tt, _ = connector(api([{"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": []}]))
    result = await tt.publish(AUTH, PublishContent("x", [VID]))
    assert (result.external_post_id, result.permalink) == ("pub_1", None)


async def test_processing_failure():
    tt, _ = connector(api([{"status": "FAILED", "fail_reason": "file_format_check_failed"}]))
    with pytest.raises(ConnectorError) as e:
        await tt.publish(AUTH, PublishContent("x", [VID]))
    assert "file_format_check_failed" in str(e.value) and not e.value.retryable


@pytest.mark.parametrize(
    ("error", "retryable", "reauth", "fragment"),
    [
        (
            {"code": "unaudited_client_can_only_post_to_private_accounts"},
            False,
            False,
            "mode privé",
        ),
        ({"code": "url_ownership_unverified"}, False, False, "domaine"),
        ({"code": "rate_limit_exceeded", "http": 429}, True, False, ""),
        ({"code": "access_token_invalid", "http": 401}, False, True, ""),
        ({"code": "internal_error", "http": 500}, True, False, ""),
    ],
)
async def test_init_errors(error, retryable, reauth, fragment):
    tt, _ = connector(api(init_error=dict(error)))
    with pytest.raises(ConnectorError) as e:
        await tt.publish(AUTH, PublishContent("x", [VID]))
    assert (e.value.retryable, e.value.reauth) == (retryable, reauth)
    assert fragment in str(e.value)


async def test_connect_and_rotating_refresh(monkeypatch):
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "tt-key")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "tt-secret")
    get_settings.cache_clear()

    def handler(request):
        if request.url.path.endswith("/oauth/token/"):
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            assert form["client_key"] == "tt-key" and form["client_secret"] == "tt-secret"
            if form["grant_type"] == "refresh_token":
                if form["refresh_token"] != "r1":
                    return httpx.Response(
                        400, json={"error": "invalid_grant", "error_description": "expired"}
                    )
                return httpx.Response(
                    200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 7200}
                )
            assert form["code"] == "the-code" and form["redirect_uri"] == "https://api/cb"
            return httpx.Response(
                200,
                json={
                    "access_token": "a1",
                    "refresh_token": "r1",
                    "expires_in": 7200,
                    "open_id": "open_1",
                    "scope": "user.info.basic,video.publish",
                },
            )
        assert request.headers["authorization"] == "Bearer a1"
        return httpx.Response(200, json={"data": CREATOR, "error": OK})

    try:
        tt, _ = connector(handler)
        query = parse_qs(urlparse(tt.authorize_url("st", "https://api/cb")).query)
        assert query["client_key"] == ["tt-key"] and query["scope"] == [
            "user.info.basic,video.publish"
        ]

        [account] = await tt.exchange_code("the-code", "https://api/cb")
        assert (account.external_id, account.username, account.display_name) == (
            "open_1",
            "monapp",
            "Mon App",
        )
        assert (account.access_token, account.refresh_token) == ("a1", "r1")
        assert account.token_expires_at is not None

        tokens = await tt.refresh("a1", "r1")
        assert (tokens.access_token, tokens.refresh_token) == ("a2", "r2")
        with pytest.raises(ConnectorError) as e:
            await tt.refresh("a1", "stale")
        assert e.value.reauth
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


async def test_connect_refused_without_publish_scope():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "access_token": "a",
                "refresh_token": "r",
                "expires_in": 7200,
                "open_id": "o",
                "scope": "user.info.basic",
            },
        )

    tt, _ = connector(handler)
    with pytest.raises(ConnectorError):
        await tt.exchange_code("c", "https://api/cb")


def test_validate():
    tt = TikTokConnector()
    assert tt.validate(PublishContent("x", [VID])) == []
    assert tt.validate(PublishContent("", [JPG, JPG])) == []
    assert tt.validate(PublishContent("texte seul"))
    assert tt.validate(PublishContent("x", [JPG, VID]))
    assert tt.validate(PublishContent("x", [VID, VID]))
    assert tt.validate(PublishContent("x", [PNG]))
    assert tt.validate(PublishContent("x" * 2201, [VID]))
    assert tt.validate(PublishContent("x" * 2201, [JPG])) == []
