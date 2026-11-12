import base64
import hashlib
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.config import get_settings
from app.connectors import x as x_module
from app.connectors.base import AccountAuth, ConnectorError, MediaItem, PublishContent
from app.connectors.x import XConnector

AUTH = AccountAuth("42", "x-token", {"username": "monapp"})
JPG = MediaItem("https://cdn.test/a.jpg", "image", "image/jpeg")
MP4 = MediaItem("https://cdn.test/v.mp4", "video", "video/mp4")
VIDEO_BYTES = b"0123456789"


def connector(handler):
    calls: list[httpx.Request] = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    xc = XConnector(httpx.AsyncClient(transport=httpx.MockTransport(wrapped)))
    xc.poll_interval = 0
    return xc, calls


def api(states: list[str] | None = None):
    states = list(states or [])
    ids = iter(range(1, 50))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.host == "cdn.test":
            return httpx.Response(200, content=VIDEO_BYTES if path.endswith(".mp4") else b"img")
        assert request.headers["authorization"] == "Bearer x-token"
        if path.endswith("/media/upload/initialize"):
            return httpx.Response(200, json={"data": {"id": f"m{next(ids)}"}})
        if path.endswith("/append"):
            return httpx.Response(200, json={"data": {}})
        if path.endswith("/finalize"):
            info = (
                {"processing_info": {"state": "pending", "check_after_secs": 1}} if states else {}
            )
            return httpx.Response(200, json={"data": {"id": "m1", **info}})
        if path.endswith("/media/upload"):
            assert request.url.params["command"] == "STATUS"
            state = states.pop(0) if len(states) > 1 else states[0]
            return httpx.Response(200, json={"data": {"processing_info": {"state": state}}})
        return httpx.Response(201, json={"data": {"id": "1800", "text": "ok"}})

    return handler


def tweet(calls) -> dict:
    return json.loads(next(c for c in calls if c.url.path == "/2/tweets").content)


async def test_text_post():
    xc, calls = connector(api())
    result = await xc.publish(AUTH, PublishContent("Bonjour X"))
    assert tweet(calls) == {"text": "Bonjour X"}
    assert result.external_post_id == "1800"
    assert result.permalink == "https://x.com/monapp/status/1800"


async def test_images_are_uploaded_then_attached():
    xc, calls = connector(api())
    await xc.publish(AUTH, PublishContent("Photos", [JPG, JPG]))
    inits = [json.loads(c.content) for c in calls if c.url.path.endswith("/initialize")]
    assert (
        inits
        == [{"media_type": "image/jpeg", "total_bytes": 3, "media_category": "tweet_image"}] * 2
    )
    assert tweet(calls) == {"text": "Photos", "media": {"media_ids": ["m1", "m2"]}}


async def test_video_is_chunked_and_waits_for_processing(monkeypatch):
    monkeypatch.setattr(x_module, "CHUNK", 4)
    xc, calls = connector(api(["in_progress", "succeeded"]))
    await xc.publish(AUTH, PublishContent("Clip", [MP4]))
    init = json.loads(next(c for c in calls if c.url.path.endswith("/initialize")).content)
    assert init == {"media_type": "video/mp4", "total_bytes": 10, "media_category": "tweet_video"}
    appends = [c for c in calls if c.url.path.endswith("/m1/append")]
    assert len(appends) == 3  # 4 + 4 + 2 bytes
    assert b'name="segment_index"\r\n\r\n2' in appends[2].content and b"89" in appends[2].content
    order = [c.url.path.rsplit("/", 1)[1] for c in calls if c.url.host == "api.x.com"]
    assert order[-4:] == ["finalize", "upload", "upload", "tweets"]


async def test_processing_failure_and_timeout_post_nothing():
    xc, calls = connector(api(["failed"]))
    with pytest.raises(ConnectorError) as e:
        await xc.publish(AUTH, PublishContent("x", [MP4]))
    assert not e.value.retryable

    xc, calls = connector(api(["in_progress"]))
    xc.poll_timeout = 0
    with pytest.raises(ConnectorError) as e:
        await xc.publish(AUTH, PublishContent("x", [MP4]))
    assert e.value.retryable
    assert not any(c.url.path == "/2/tweets" for c in calls)


@pytest.mark.parametrize(
    ("status", "body", "retryable", "reauth", "message"),
    [
        (401, {"title": "Unauthorized", "detail": "Unauthorized"}, False, True, "Unauthorized"),
        (429, {"title": "Too Many Requests"}, True, False, "Too Many Requests"),
        (
            403,
            {"detail": "You are not allowed to create a Tweet with duplicate content."},
            False,
            False,
            "You are not allowed to create a Tweet with duplicate content.",
        ),
        (400, {"errors": [{"message": "Invalid media"}]}, False, False, "Invalid media"),
        (503, {}, True, False, "Erreur X HTTP 503"),
    ],
)
async def test_error_mapping(status, body, retryable, reauth, message):
    xc, _ = connector(lambda r: httpx.Response(status, json=body))
    with pytest.raises(ConnectorError) as e:
        await xc.publish(AUTH, PublishContent("x"))
    assert (e.value.retryable, e.value.reauth, str(e.value)) == (retryable, reauth, message)


async def test_connect_with_pkce_and_refresh(monkeypatch):
    monkeypatch.setenv("X_CLIENT_ID", "x-id")
    monkeypatch.setenv("X_CLIENT_SECRET", "x-secret")
    get_settings.cache_clear()
    seen = {}

    def handler(request):
        if request.url.path == "/2/oauth2/token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            basic = base64.b64encode(b"x-id:x-secret").decode()
            assert request.headers["authorization"] == f"Basic {basic}"
            if form["grant_type"] == "refresh_token":
                if form["refresh_token"] != "r1":
                    return httpx.Response(
                        400, json={"error": "invalid_grant", "error_description": "revoked"}
                    )
                return httpx.Response(
                    200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 7200}
                )
            seen["verifier"] = form["code_verifier"]
            return httpx.Response(
                200, json={"access_token": "a1", "refresh_token": "r1", "expires_in": 7200}
            )
        assert request.headers["authorization"] == "Bearer a1"
        return httpx.Response(
            200, json={"data": {"id": "42", "name": "Mon App", "username": "monapp"}}
        )

    try:
        xc, _ = connector(handler)
        query = parse_qs(urlparse(xc.authorize_url("state-1", "https://api/cb")).query)
        assert query["client_id"] == ["x-id"] and query["code_challenge_method"] == ["S256"]
        assert "media.write" in query["scope"][0] and "offline.access" in query["scope"][0]

        [account] = await xc.exchange_code("the-code", "https://api/cb", "state-1")
        # The verifier sent at exchange matches the challenge sent at authorization.
        digest = hashlib.sha256(seen["verifier"].encode()).digest()
        assert base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == query["code_challenge"][0]
        assert xc._verifier("state-2") != seen["verifier"]
        assert (account.external_id, account.username, account.meta) == (
            "42",
            "monapp",
            {"username": "monapp"},
        )
        assert (account.access_token, account.refresh_token) == ("a1", "r1")

        tokens = await xc.refresh("a1", "r1")
        assert (tokens.access_token, tokens.refresh_token) == ("a2", "r2")
        with pytest.raises(ConnectorError) as e:
            await xc.refresh("a1", "old")
        assert e.value.reauth
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_validate():
    xc = XConnector()
    assert xc.validate(PublishContent("texte seul")) == []
    assert xc.validate(PublishContent("", [JPG] * 4)) == []
    assert xc.validate(PublishContent("x", [MP4])) == []
    assert xc.validate(PublishContent(" "))
    assert xc.validate(PublishContent("x" * 281))
    assert xc.validate(PublishContent("x", [JPG] * 5))
    assert xc.validate(PublishContent("x", [JPG, MP4]))
    assert xc.validate(PublishContent("x", [MP4, MP4]))
