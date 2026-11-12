import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.connectors.base import AccountAuth, ConnectorError, MediaItem, PublishContent
from app.connectors.facebook import FacebookConnector

AUTH = AccountAuth("page_1", "page-token")
IMG = MediaItem("https://cdn.test/a.jpg", "image", "image/jpeg")
VID = MediaItem("https://cdn.test/v.mp4", "video", "video/mp4")


def connector(handler) -> tuple[FacebookConnector, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    return FacebookConnector(httpx.AsyncClient(transport=httpx.MockTransport(wrapped))), calls


def form(request: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


def ok(request: httpx.Request) -> httpx.Response:
    if request.method == "GET":
        return httpx.Response(200, json={"permalink_url": "https://www.facebook.com/p/1"})
    path = request.url.path
    if path.endswith("/photos"):
        published = form(request).get("published") != "false"
        return httpx.Response(
            200, json={"id": "ph_1", **({"post_id": "page_1_99"} if published else {})}
        )
    return httpx.Response(200, json={"id": "page_1_99"})


async def test_text_post():
    fb, calls = connector(ok)
    result = await fb.publish(AUTH, PublishContent("Salut"))
    assert calls[0].url.path.endswith("/page_1/feed")
    assert form(calls[0]) == {"access_token": "page-token", "message": "Salut"}
    assert result.external_post_id == "page_1_99"
    assert result.permalink == "https://www.facebook.com/p/1"


async def test_single_photo():
    fb, calls = connector(ok)
    result = await fb.publish(AUTH, PublishContent("Légende", [IMG]))
    assert calls[0].url.path.endswith("/page_1/photos")
    assert form(calls[0])["url"] == IMG.url and form(calls[0])["caption"] == "Légende"
    assert result.external_post_id == "page_1_99"


async def test_multiple_photos_are_attached_to_one_post():
    fb, calls = connector(ok)
    await fb.publish(AUTH, PublishContent("Album", [IMG, IMG]))
    posts = [c for c in calls if c.method == "POST"]
    assert [c.url.path.rsplit("/", 1)[1] for c in posts] == ["photos", "photos", "feed"]
    assert form(posts[0])["published"] == "false"
    feed = form(posts[2])
    assert json.loads(feed["attached_media[0]"]) == {"media_fbid": "ph_1"}
    assert "attached_media[1]" in feed and feed["message"] == "Album"


async def test_video():
    fb, calls = connector(ok)
    await fb.publish(AUTH, PublishContent("Clip", [VID]))
    assert calls[0].url.path.endswith("/page_1/videos")
    assert form(calls[0])["file_url"] == VID.url and form(calls[0])["description"] == "Clip"


@pytest.mark.parametrize(
    ("status", "error", "retryable", "reauth"),
    [
        (400, {"code": 190, "message": "Token expired"}, False, True),
        (400, {"code": 4, "message": "Rate limit"}, True, False),
        (400, {"code": 100, "message": "Bad param"}, False, False),
        (503, None, True, False),
    ],
)
async def test_error_mapping(status, error, retryable, reauth):
    fb, _ = connector(lambda r: httpx.Response(status, json={"error": error} if error else {}))
    with pytest.raises(ConnectorError) as e:
        await fb.publish(AUTH, PublishContent("x"))
    assert (e.value.retryable, e.value.reauth) == (retryable, reauth)


async def test_network_error_is_retryable():
    def boom(request):
        raise httpx.ConnectError("down")

    fb, _ = connector(boom)
    with pytest.raises(ConnectorError) as e:
        await fb.publish(AUTH, PublishContent("x"))
    assert e.value.retryable


async def test_permalink_failure_does_not_fail_the_publish():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(400, json={"error": {"code": 100, "message": "nope"}})
        return httpx.Response(200, json={"id": "page_1_99"})

    fb, _ = connector(handler)
    result = await fb.publish(AUTH, PublishContent("x"))
    assert result.external_post_id == "page_1_99" and result.permalink is None


async def test_exchange_code_returns_every_page():
    def handler(request):
        q = request.url.params
        if request.url.path.endswith("/oauth/access_token"):
            if q.get("grant_type") == "fb_exchange_token":
                assert q["fb_exchange_token"] == "short"
                return httpx.Response(200, json={"access_token": "long"})
            assert q["code"] == "c" and q["redirect_uri"] == "https://api/cb"
            return httpx.Response(200, json={"access_token": "short"})
        if q.get("after") == "2":
            return httpx.Response(
                200, json={"data": [{"id": "2", "name": "B", "access_token": "tb"}]}
            )
        assert q["access_token"] == "long"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1",
                        "name": "A",
                        "access_token": "ta",
                        "picture": {"data": {"url": "http://pic"}},
                    },
                    {"id": "x", "name": "No token"},
                ],
                "paging": {"next": "https://graph.facebook.com/v24.0/me/accounts?after=2"},
            },
        )

    fb, _ = connector(handler)
    pages = await fb.exchange_code("c", "https://api/cb")
    assert [(p.external_id, p.access_token) for p in pages] == [("1", "ta"), ("2", "tb")]
    assert pages[0].avatar_url == "http://pic"


def test_validate():
    fb = FacebookConnector()
    assert fb.validate(PublishContent("x")) == []
    assert fb.validate(PublishContent("", [IMG])) == []
    assert fb.validate(PublishContent("  "))
    assert fb.validate(PublishContent("x", [IMG, VID]))
    assert fb.validate(PublishContent("x", [VID, VID]))
    assert fb.validate(PublishContent("x", [IMG] * 11))
