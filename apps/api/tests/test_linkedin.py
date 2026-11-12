import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.config import get_settings
from app.connectors.base import AccountAuth, ConnectorError, MediaItem, PublishContent
from app.connectors.linkedin import LinkedInConnector, escape

AUTH = AccountAuth("abc123", "li-token")
JPG = MediaItem("https://cdn.test/a.jpg", "image", "image/jpeg")
WEBP = MediaItem("https://cdn.test/a.webp", "image", "image/webp")
MP4 = MediaItem("https://cdn.test/v.mp4", "video", "video/mp4")
MOV = MediaItem("https://cdn.test/v.mov", "video", "video/quicktime")
VIDEO_BYTES = b"0123456789"


def connector(handler):
    calls: list[httpx.Request] = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    return LinkedInConnector(httpx.AsyncClient(transport=httpx.MockTransport(wrapped))), calls


def api(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    if host == "cdn.test":
        return httpx.Response(200, content=VIDEO_BYTES if path.endswith(".mp4") else b"image-bytes")
    if host == "upload.test":
        return httpx.Response(200, headers={"etag": f'"etag-{request.url.params["part"]}"'})
    action = request.url.params.get("action")
    if path == "/rest/images":
        n = sum(1 for _ in [0]) and len(api.images) + 1
        api.images.append(n)
        return httpx.Response(
            200,
            json={
                "value": {
                    "uploadUrl": f"https://upload.test/img?part={n}",
                    "image": f"urn:li:image:{n}",
                }
            },
        )
    if path == "/rest/videos" and action == "initializeUpload":
        return httpx.Response(
            200,
            json={
                "value": {
                    "video": "urn:li:video:V1",
                    "uploadToken": "tok",
                    "uploadInstructions": [
                        {
                            "uploadUrl": "https://upload.test/vid?part=0",
                            "firstByte": 0,
                            "lastByte": 5,
                        },
                        {
                            "uploadUrl": "https://upload.test/vid?part=1",
                            "firstByte": 6,
                            "lastByte": 9,
                        },
                    ],
                }
            },
        )
    if path == "/rest/videos":
        return httpx.Response(200)
    return httpx.Response(201, headers={"x-restli-id": "urn:li:share:999"})


@pytest.fixture(autouse=True)
def reset():
    api.images = []


def post_body(calls) -> dict:
    return json.loads(next(c for c in calls if c.url.path == "/rest/posts").content)


async def test_text_post_escapes_reserved_characters_but_keeps_hashtags():
    li, calls = connector(api)
    result = await li.publish(AUTH, PublishContent("Lancement (v2) de mon_app ! #indiehacker"))
    request = next(c for c in calls if c.url.path == "/rest/posts")
    assert request.headers["linkedin-version"] == "202610"
    assert request.headers["x-restli-protocol-version"] == "2.0.0"
    assert request.headers["authorization"] == "Bearer li-token"
    body = post_body(calls)
    assert body["author"] == "urn:li:person:abc123"
    assert body["commentary"] == r"Lancement \(v2\) de mon\_app ! #indiehacker"
    assert body["lifecycleState"] == "PUBLISHED" and "content" not in body
    assert result.external_post_id == "urn:li:share:999"
    assert result.permalink == "https://www.linkedin.com/feed/update/urn:li:share:999/"


def test_escape():
    assert escape(r"a|b{c}@d[e](f)<g>*h_i~j\k") == r"a\|b\{c\}\@d\[e\]\(f\)\<g\>\*h\_i\~j\\k"


async def test_single_image_is_uploaded_as_bytes():
    li, calls = connector(api)
    await li.publish(AUTH, PublishContent("Photo", [JPG]))
    init = next(c for c in calls if c.url.path == "/rest/images")
    assert json.loads(init.content) == {
        "initializeUploadRequest": {"owner": "urn:li:person:abc123"}
    }
    upload = next(c for c in calls if c.url.host == "upload.test")
    assert upload.method == "PUT" and upload.content == b"image-bytes"
    assert post_body(calls)["content"] == {"media": {"id": "urn:li:image:1"}}


async def test_multiple_images():
    li, calls = connector(api)
    await li.publish(AUTH, PublishContent("Album", [JPG, JPG, JPG]))
    assert post_body(calls)["content"] == {
        "multiImage": {"images": [{"id": f"urn:li:image:{n}"} for n in (1, 2, 3)]}
    }


async def test_video_is_uploaded_in_the_parts_linkedin_asks_for():
    li, calls = connector(api)
    await li.publish(AUTH, PublishContent("Clip", [MP4]))
    init = next(c for c in calls if c.url.params.get("action") == "initializeUpload")
    assert json.loads(init.content)["initializeUploadRequest"]["fileSizeBytes"] == len(VIDEO_BYTES)
    parts = [c.content for c in calls if c.url.host == "upload.test"]
    assert parts == [b"012345", b"6789"]
    finalize = next(c for c in calls if c.url.params.get("action") == "finalizeUpload")
    assert json.loads(finalize.content) == {
        "finalizeUploadRequest": {
            "video": "urn:li:video:V1",
            "uploadToken": "tok",
            "uploadedPartIds": ["etag-0", "etag-1"],
        }
    }
    assert post_body(calls)["content"] == {"media": {"id": "urn:li:video:V1"}}


@pytest.mark.parametrize(
    ("status", "retryable", "reauth"),
    [(401, False, True), (429, True, False), (500, True, False), (422, False, False)],
)
async def test_error_mapping(status, retryable, reauth):
    li, _ = connector(lambda r: httpx.Response(status, json={"message": "nope", "status": status}))
    with pytest.raises(ConnectorError) as e:
        await li.publish(AUTH, PublishContent("x"))
    assert (e.value.retryable, e.value.reauth, str(e.value)) == (retryable, reauth, "nope")


async def test_missing_media_in_storage_is_reported():
    def handler(request):
        return httpx.Response(404) if request.url.host == "cdn.test" else api(request)

    li, calls = connector(handler)
    with pytest.raises(ConnectorError) as e:
        await li.publish(AUTH, PublishContent("x", [JPG]))
    assert "introuvable" in str(e.value)
    assert not any(c.url.path == "/rest/posts" for c in calls)


async def test_connect(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "li-id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "li-secret")
    get_settings.cache_clear()

    def handler(request):
        if request.url.path == "/oauth/v2/accessToken":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            assert form["client_secret"] == "li-secret" and form["code"] == "the-code"
            return httpx.Response(200, json={"access_token": "a1", "expires_in": 5184000})
        assert request.headers["authorization"] == "Bearer a1"
        return httpx.Response(
            200, json={"sub": "abc123", "name": "Thomas F", "picture": "http://p"}
        )

    try:
        li, _ = connector(handler)
        query = parse_qs(urlparse(li.authorize_url("st", "https://api/cb")).query)
        assert query["client_id"] == ["li-id"] and query["scope"] == [
            "openid profile w_member_social"
        ]
        [account] = await li.exchange_code("the-code", "https://api/cb", "st")
        assert (account.external_id, account.display_name) == ("abc123", "Thomas F")
        assert account.refresh_token is None and account.token_expires_at is not None
        # No refresh token: nothing to renew, the worker leaves the account alone.
        assert await li.refresh("a1", None) is None
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_validate():
    li = LinkedInConnector()
    assert li.validate(PublishContent("texte seul")) == []
    assert li.validate(PublishContent("", [JPG, JPG])) == []
    assert li.validate(PublishContent("x", [MP4])) == []
    assert li.validate(PublishContent(" "))
    assert li.validate(PublishContent("x", [WEBP]))
    assert li.validate(PublishContent("x", [MOV]))
    assert li.validate(PublishContent("x", [JPG, MP4]))
    assert li.validate(PublishContent("x", [JPG] * 21))
    assert li.validate(PublishContent("x" * 3001))
