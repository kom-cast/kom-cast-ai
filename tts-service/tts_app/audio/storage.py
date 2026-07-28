from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from tts_app.config import StorageSettings, get_storage_settings


class AudioStorage(ABC):
    """캐시된 브리핑 오디오/매니페스트의 조회·저장을 담당한다."""

    @abstractmethod
    def read_manifest(self, cache_key: str) -> dict | None:
        """캐시 히트 시 저장된 응답(JSON)을 그대로 반환하고, 없으면 None."""

    @abstractmethod
    def save(self, cache_key: str, audio_bytes: bytes, manifest: dict) -> str:
        """오디오와 매니페스트를 저장하고 audioUrl을 반환한다."""


class LocalAudioStorage(AudioStorage):
    def __init__(self, audio_dir: Path) -> None:
        self.audio_dir = audio_dir

    def _audio_path(self, cache_key: str) -> Path:
        return self.audio_dir / f"{cache_key}.mp3"

    def _manifest_path(self, cache_key: str) -> Path:
        return self.audio_dir / f"{cache_key}.json"

    def read_manifest(self, cache_key: str) -> dict | None:
        audio_path = self._audio_path(cache_key)
        manifest_path = self._manifest_path(cache_key)
        if audio_path.exists() and manifest_path.exists():
            return json.loads(manifest_path.read_text())
        return None

    def save(self, cache_key: str, audio_bytes: bytes, manifest: dict) -> str:
        audio_url = f"/static/audio/{cache_key}.mp3"
        full_manifest = {**manifest, "audioUrl": audio_url}

        self._audio_path(cache_key).write_bytes(audio_bytes)
        self._manifest_path(cache_key).write_text(
            json.dumps(full_manifest, ensure_ascii=False)
        )
        return audio_url


class NcpObjectStorage(AudioStorage):
    """네이버클라우드(금융) Object Storage, S3 호환 API.
    https://guide-fin.ncloud-docs.com/docs/storage-storage-8-2
    """

    def __init__(self, settings: StorageSettings) -> None:
        self.bucket = settings.ncp_bucket
        self.cdn_base_url = (settings.cdn_base_url or "").rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.ncp_endpoint_url,
            region_name=settings.ncp_region,
            aws_access_key_id=settings.ncp_access_key,
            aws_secret_access_key=settings.ncp_secret_key,
        )

    def _audio_key(self, cache_key: str) -> str:
        return f"{cache_key}.mp3"

    def _manifest_key(self, cache_key: str) -> str:
        return f"{cache_key}.json"

    def read_manifest(self, cache_key: str) -> dict | None:
        try:
            obj = self.client.get_object(
                Bucket=self.bucket, Key=self._manifest_key(cache_key)
            )
        except ClientError as error:
            # NCP/S3 호환 스토리지는 s3:ListBucket 권한이 없으면 존재하지 않는 키의
            # GetObject를 진짜 404(NoSuchKey) 대신 403(AccessDenied)으로 응답한다.
            # https://guide-fin.ncloud-docs.com/docs/storage-storage-8-2
            if error.response["Error"]["Code"] in ("NoSuchKey", "404", "AccessDenied"):
                return None
            raise
        return json.loads(obj["Body"].read())

    def save(self, cache_key: str, audio_bytes: bytes, manifest: dict) -> str:
        audio_url = f"{self.cdn_base_url}/{self._audio_key(cache_key)}"
        full_manifest = {**manifest, "audioUrl": audio_url}

        self.client.put_object(
            Bucket=self.bucket,
            Key=self._audio_key(cache_key),
            Body=audio_bytes,
            ContentType="audio/mpeg",
        )
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._manifest_key(cache_key),
            Body=json.dumps(full_manifest, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        return audio_url


@lru_cache
def get_audio_storage(audio_dir: Path) -> AudioStorage:
    settings = get_storage_settings()
    if settings.backend == "ncp":
        return NcpObjectStorage(settings)
    return LocalAudioStorage(audio_dir)
