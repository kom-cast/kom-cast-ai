from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from tts_app.config import StorageSettings, get_storage_settings


@dataclass
class StorageResult:
    audio_url: str
    # db 백엔드에서만 채워진다. 백엔드(Spring Boot)가 이 id로 audio_binaries
    # 테이블을 조회해 오디오를 스트리밍한다.
    audio_binary_id: str | None = None


class AudioStorage(ABC):
    """캐시된 브리핑 오디오/매니페스트의 조회·저장을 담당한다."""

    @abstractmethod
    def read_manifest(self, cache_key: str) -> dict | None:
        """캐시 히트 시 저장된 응답(JSON)을 그대로 반환하고, 없으면 None."""

    @abstractmethod
    def save(
        self,
        cache_key: str,
        audio_bytes: bytes,
        manifest: dict,
        *,
        user_id: str | None = None,
        script_id: str | None = None,
        audio_type: str = "DAILY_BRIEFING",
    ) -> StorageResult:
        """오디오와 매니페스트를 저장하고 결과(audioUrl 등)를 반환한다.

        user_id/script_id/audio_type은 AUDIO_BACKEND=db일 때만 쓰인다
        (Spring의 audios 테이블에 직접 부모 레코드를 만들기 위함)."""


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

    def save(
        self,
        cache_key: str,
        audio_bytes: bytes,
        manifest: dict,
        *,
        user_id: str | None = None,
        script_id: str | None = None,
        audio_type: str = "DAILY_BRIEFING",
    ) -> StorageResult:
        audio_url = f"/static/audio/{cache_key}.mp3"
        full_manifest = {**manifest, "audioUrl": audio_url}

        self._audio_path(cache_key).write_bytes(audio_bytes)
        self._manifest_path(cache_key).write_text(
            json.dumps(full_manifest, ensure_ascii=False)
        )
        return StorageResult(audio_url=audio_url)


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

    def save(
        self,
        cache_key: str,
        audio_bytes: bytes,
        manifest: dict,
        *,
        user_id: str | None = None,
        script_id: str | None = None,
        audio_type: str = "DAILY_BRIEFING",
    ) -> StorageResult:
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
        return StorageResult(audio_url=audio_url)


class DbAudioStorage(AudioStorage):
    """Object Storage 장애 기간 임시 대안. MP3 바이너리를 Postgres
    audio_binaries 테이블에 직접 저장하고, 백엔드(Spring Boot)가 audio_binary_id로
    조회해 스트리밍하도록 audioUrl 대신 audio_binary_id를 반환한다.
    Object Storage 복구 후에는 AUDIO_BACKEND를 ncp로 되돌리면 된다."""

    def __init__(self) -> None:
        # 지연 임포트: AUDIO_BACKEND=db가 아니면 DB 연결을 만들 필요가 없다.
        from tts_app.audio.db import SessionFactory, create_tables

        create_tables()
        self._session_factory = SessionFactory

    def read_manifest(self, cache_key: str) -> dict | None:
        # audio_binaries 테이블은 바이너리만 담고 매니페스트는 캐시하지 않으므로
        # 항상 캐시 미스로 처리한다(Object Storage 복구 전까지 임시).
        return None

    def save(
        self,
        cache_key: str,
        audio_bytes: bytes,
        manifest: dict,
        *,
        user_id: str | None = None,
        script_id: str | None = None,
        audio_type: str = "DAILY_BRIEFING",
    ) -> StorageResult:
        from tts_app.audio.models import Audio, AudioBinary, AudioSegment

        if user_id is None:
            raise ValueError(
                "AUDIO_BACKEND=db는 audios.user_id(not null)를 채워야 해서 "
                "Script 요청에 user_id가 반드시 있어야 합니다."
            )

        audio_binary_id = uuid.uuid4()
        audio_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        with self._session_factory() as session:
            session.add(AudioBinary(id=audio_binary_id, data=audio_bytes))
            session.add(
                Audio(
                    id=audio_id,
                    user_id=uuid.UUID(user_id),
                    script_id=uuid.UUID(script_id) if script_id else None,
                    audio_type=audio_type,
                    # 정식 파일 URL이 없으므로 audio_binary_id를 그대로 넣어둔다.
                    # audio_binaries.id로 스트리밍하도록 소비 측(Spring)과 맞춰야 한다.
                    audio_url=str(audio_binary_id),
                    duration_seconds=round(manifest["durationSec"]),
                    created_at=now,
                )
            )
            for order, segment in enumerate(manifest.get("segments", [])):
                target = segment.get("target") or {}
                session.add(
                    AudioSegment(
                        id=uuid.uuid4(),
                        audio_id=audio_id,
                        segment_order=order,
                        speaker=segment["speaker"],
                        stock_code=(
                            target.get("stock_code")
                            if target.get("type") == "STOCK"
                            else None
                        ),
                        industry_code=(
                            target.get("industry_code")
                            if target.get("type") == "INDUSTRY"
                            else None
                        ),
                        text=segment["text"],
                        start_sec=segment["startSec"],
                        words=json.dumps(segment["words"]),
                        created_at=now,
                    )
                )
            session.commit()
        return StorageResult(audio_url="", audio_binary_id=str(audio_binary_id))


@lru_cache
def get_audio_storage(audio_dir: Path) -> AudioStorage:
    settings = get_storage_settings()
    if settings.backend == "ncp":
        return NcpObjectStorage(settings)
    if settings.backend == "db":
        return DbAudioStorage()
    return LocalAudioStorage(audio_dir)
