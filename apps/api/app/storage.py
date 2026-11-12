"""Media storage: Cloudflare R2 in production, local disk for development."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.config import get_settings


@dataclass
class UploadTarget:
    url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)


class Storage(Protocol):
    def upload_target(self, media_id: str, key: str, content_type: str) -> UploadTarget: ...
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def size(self, key: str) -> int | None: ...
    async def delete(self, key: str) -> None: ...
    def public_url(self, key: str) -> str: ...


class LocalStorage:
    def __init__(self) -> None:
        s = get_settings()
        self.root = Path(s.local_media_dir).resolve()

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError("invalid key")
        return p

    def upload_target(self, media_id: str, key: str, content_type: str) -> UploadTarget:
        return UploadTarget(url=f"/api/media/{media_id}/upload")

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_bytes, data)

    async def size(self, key: str) -> int | None:
        p = self.path(key)
        return p.stat().st_size if p.is_file() else None

    async def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def public_url(self, key: str) -> str:
        # Relative: served through the dev proxy. Platforms cannot fetch it, which
        # is why real publishing with media needs the R2 backend.
        return f"/media-files/{key}"


class R2Storage:
    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        s = get_settings()
        self.bucket = s.r2_bucket
        self.public_base = s.r2_public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def upload_target(self, media_id: str, key: str, content_type: str) -> UploadTarget:
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=3600,
        )
        return UploadTarget(url=url, headers={"Content-Type": content_type})

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def size(self, key: str) -> int | None:
        from botocore.exceptions import ClientError

        try:
            head = await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
        except ClientError:
            return None
        return int(head["ContentLength"])

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    def public_url(self, key: str) -> str:
        return f"{self.public_base}/{key}"


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = R2Storage() if get_settings().storage_backend == "r2" else LocalStorage()
    return _storage
