import json

import pytest
from botocore.exceptions import ClientError

from tts_app.audio.storage import LocalAudioStorage, NcpObjectStorage
from tts_app.config import StorageSettings


def test_local_storage_roundtrip(tmp_path):
    storage = LocalAudioStorage(tmp_path)

    assert storage.read_manifest("abc") is None

    result = storage.save("abc", b"fake-mp3-bytes", {"durationSec": 1.0})

    assert result.audio_url == "/static/audio/abc.mp3"
    assert result.audio_binary_id is None
    assert (tmp_path / "abc.mp3").read_bytes() == b"fake-mp3-bytes"
    assert storage.read_manifest("abc") == {
        "durationSec": 1.0,
        "audioUrl": result.audio_url,
    }


def test_storage_settings_requires_ncp_fields_when_backend_is_ncp():
    with pytest.raises(ValueError, match="AUDIO_NCP_ACCESS_KEY"):
        StorageSettings(backend="ncp")


def test_storage_settings_ncp_ok_with_all_fields():
    settings = StorageSettings(
        backend="ncp",
        ncp_access_key="key",
        ncp_secret_key="secret",
        ncp_bucket="bucket",
        cdn_base_url="https://cdn.example.com",
    )
    assert settings.backend == "ncp"


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803
        self.objects[Key] = Body if isinstance(Body, bytes) else Body.encode()

    def get_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": _FakeBody(self.objects[Key])}


def _ncp_storage(monkeypatch) -> tuple[NcpObjectStorage, _FakeS3Client]:
    settings = StorageSettings(
        backend="ncp",
        ncp_access_key="key",
        ncp_secret_key="secret",
        ncp_bucket="bucket",
        cdn_base_url="https://cdn.example.com/",
    )
    fake_client = _FakeS3Client()
    monkeypatch.setattr(
        "tts_app.audio.storage.boto3.client", lambda *args, **kwargs: fake_client
    )
    return NcpObjectStorage(settings), fake_client


def test_ncp_storage_roundtrip(monkeypatch):
    storage, fake_client = _ncp_storage(monkeypatch)

    assert storage.read_manifest("abc") is None

    result = storage.save("abc", b"fake-mp3-bytes", {"durationSec": 1.0})

    assert result.audio_url == "https://cdn.example.com/abc.mp3"
    assert result.audio_binary_id is None
    assert fake_client.objects["abc.mp3"] == b"fake-mp3-bytes"
    assert json.loads(fake_client.objects["abc.json"]) == {
        "durationSec": 1.0,
        "audioUrl": result.audio_url,
    }
    assert storage.read_manifest("abc") == {
        "durationSec": 1.0,
        "audioUrl": result.audio_url,
    }


def test_db_storage_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    from tts_app.config import get_database_settings

    get_database_settings.cache_clear()

    from tts_app.audio.storage import DbAudioStorage

    storage = DbAudioStorage()

    assert storage.read_manifest("abc") is None

    result = storage.save("abc", b"fake-mp3-bytes", {"durationSec": 1.0})

    assert result.audio_url == ""
    assert result.audio_binary_id is not None
    # 캐시 조회는 지원하지 않으므로 저장 후에도 여전히 미스로 처리된다.
    assert storage.read_manifest("abc") is None

    import uuid

    from tts_app.audio.db import SessionFactory
    from tts_app.audio.models import AudioBinary

    with SessionFactory() as session:
        row = session.get(AudioBinary, uuid.UUID(result.audio_binary_id))
        assert row is not None
        assert bytes(row.data) == b"fake-mp3-bytes"

    get_database_settings.cache_clear()
