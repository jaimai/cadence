"""HTTP helper shared by the Meta connectors (Facebook, Instagram): same error format."""

from typing import Any

import httpx

from app.connectors.base import ConnectorError

# Graph error codes worth retrying: unknown/service errors and rate limits.
RETRYABLE_CODES = {1, 2, 4, 17, 32, 341, 613}
AUTH_CODES = {102, 190}


async def graph_request(
    client: httpx.AsyncClient | None, label: str, method: str, url: str, **kw: Any
) -> dict[str, Any]:
    own = client is None
    client = client or httpx.AsyncClient(timeout=120)
    try:
        resp = await client.request(method, url, **kw)
    except httpx.HTTPError as e:
        raise ConnectorError(f"{label} injoignable : {e}", retryable=True) from e
    finally:
        if own:
            await client.aclose()
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if (
        resp.is_success
        and isinstance(body, dict)
        and "error" not in body
        and "error_type" not in body
    ):
        return body
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        # OAuth endpoints answer {"error_type", "code", "error_message"}.
        message = (body.get("error_message") if isinstance(body, dict) else None) or (
            f"Erreur {label} HTTP {resp.status_code}"
        )
        raise ConnectorError(message, retryable=resp.status_code >= 500)
    code = err.get("code")
    raise ConnectorError(
        err.get("error_user_msg")
        or err.get("message")
        or f"Erreur {label} HTTP {resp.status_code}",
        retryable=bool(err.get("is_transient"))
        or code in RETRYABLE_CODES
        or resp.status_code >= 500,
        reauth=code in AUTH_CODES,
    )
