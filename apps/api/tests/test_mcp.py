import json
from datetime import UTC, datetime, timedelta

import httpx

from app.db import SessionLocal
from app.services import media as media_svc
from tests.conftest import make_client

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


async def rpc(key: str | None, method: str, params: dict | None = None) -> httpx.Response:
    headers = {**HEADERS, **({"Authorization": f"Bearer {key}"} if key else {})}
    async with make_client() as c:
        return await c.post(
            "/mcp/",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )


def result(response: httpx.Response) -> dict:
    assert response.status_code == 200, response.text
    text = response.text
    if "text/event-stream" in response.headers.get("content-type", ""):
        text = next(l for l in text.splitlines() if l.startswith("data:"))[5:]
    return json.loads(text)["result"]


async def call(key: str, tool: str, **arguments) -> tuple[bool, object]:
    res = result(await rpc(key, "tools/call", {"name": tool, "arguments": arguments}))
    text = res["content"][0]["text"] if res.get("content") else ""
    if res.get("isError"):
        return False, text
    structured = res.get("structuredContent")
    if structured is None:
        return True, text
    # Lists and scalars are wrapped as {"result": ...}; dicts are returned as-is.
    return True, structured["result"] if set(structured) == {"result"} else structured


async def make_key(client) -> str:
    return (await client.post("/api/api-keys", json={"name": "Claude"})).json()["key"]


async def test_requires_a_valid_key(client):
    assert (await rpc(None, "tools/list")).status_code == 401
    assert (await rpc("cad_wrong", "tools/list")).status_code == 401
    key = await make_key(client)
    names = {t["name"] for t in result(await rpc(key, "tools/list"))["tools"]}
    assert {"list_accounts", "create_post", "schedule_post", "import_media_from_url"} <= names
    key_id = (await client.get("/api/api-keys")).json()[0]["id"]
    await client.delete(f"/api/api-keys/{key_id}")
    assert (await rpc(key, "tools/list")).status_code == 401


async def test_llm_posts_wait_for_approval_by_default(client, account_id, fake_fb):
    key = await make_key(client)
    ok, accounts = await call(key, "list_accounts")
    assert ok and accounts[0]["id"] == account_id and "access_token" not in json.dumps(accounts)

    when = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    ok, post = await call(
        key, "create_post", caption="Écrit par IA", account_ids=[account_id], scheduled_at=when
    )
    assert ok, post
    assert post["status"] == "draft" and "validation humaine" in post["note"]
    assert post["source"] == "mcp" and post["scheduled_at"] is not None

    # A human approves from the app, keeping the time the LLM proposed.
    r = await client.post(
        f"/api/posts/{post['id']}/schedule", json={"scheduled_at": post["scheduled_at"]}
    )
    assert r.json()["status"] == "scheduled"


async def test_direct_mode_and_tool_errors(client, account_id, fake_fb):
    key = await make_key(client)
    await client.patch("/api/workspace", json={"llm_publish_mode": "direct"})
    ok, post = await call(
        key, "create_post", caption="Direct", account_ids=[account_id], publish_now=True
    )
    assert ok and post["status"] == "scheduled" and "note" not in post

    ok, listed = await call(key, "list_posts", status="scheduled")
    assert ok and [p["id"] for p in listed] == [post["id"]]
    ok, post = await call(key, "unschedule_post", post_id=post["id"])
    assert ok and post["status"] == "draft"
    ok, post = await call(key, "update_post", post_id=post["id"], caption="Modifié")
    assert ok and post["caption"] == "Modifié" and len(post["targets"]) == 1

    ok, error = await call(key, "create_post", caption="x", account_ids=[], publish_now=True)
    assert not ok and "compte" in error
    ok, error = await call(key, "get_post", post_id="00000000-0000-0000-0000-000000000000")
    assert not ok and "introuvable" in error


async def test_import_media(client, workspace_id):
    def handler(request):
        return httpx.Response(200, content=b"img", headers={"content-type": "image/png"})

    async with SessionLocal() as session:
        media = await media_svc.import_from_url(
            session, workspace_id, "https://cdn.test/pic.png", httpx.MockTransport(handler)
        )
    assert (media.kind, media.status, media.size) == ("image", "ready", 3)
    assert (await client.get("/api/media")).json()[0]["filename"] == "pic.png"


async def test_import_refuses_private_addresses(client):
    key = await make_key(client)
    for url in ("http://127.0.0.1/a.png", "http://169.254.169.254/latest", "file:///etc/passwd"):
        ok, error = await call(key, "import_media_from_url", url=url)
        assert not ok, url
