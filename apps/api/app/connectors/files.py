"""Fetch a media file to disk for platforms that want the bytes, not a URL."""

import tempfile
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

from app.connectors.base import ConnectorError


@asynccontextmanager
async def downloaded(url: str, client: httpx.AsyncClient | None = None) -> AsyncIterator[Path]:
    """Stream `url` into a temporary file (videos do not fit in memory) and clean up after."""
    own = client is None
    client = client or httpx.AsyncClient(timeout=300)
    tmp = tempfile.NamedTemporaryFile(prefix="cadence-", delete=False)
    path = Path(tmp.name)
    try:
        try:
            async with client.stream("GET", url) as resp:
                if not resp.is_success:
                    raise ConnectorError(
                        f"Média introuvable dans le stockage (HTTP {resp.status_code}).",
                        retryable=resp.status_code >= 500,
                    )
                async for chunk in resp.aiter_bytes():
                    tmp.write(chunk)
        except httpx.HTTPError as e:
            raise ConnectorError(f"Stockage des médias injoignable : {e}", retryable=True) from e
        finally:
            tmp.close()
        yield path
    finally:
        path.unlink(missing_ok=True)
        if own:
            await client.aclose()


def read_range(path: Path, first: int, last: int) -> bytes:
    """Bytes `first`..`last` inclusive."""
    with path.open("rb") as f:
        f.seek(first)
        return f.read(last - first + 1)


def chunks(path: Path, size: int) -> Iterator[bytes]:
    with path.open("rb") as f:
        while chunk := f.read(size):
            yield chunk
