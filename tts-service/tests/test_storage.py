import json

import pytest
from botocore.exceptions import ClientError

from tts_app.audio.storage import LocalAudioStorage, NcpObjectStorage
from tts_app.config import StorageSettings


def test_local_storage_roundtrip(tmp_path):
    storage = LocalAudioStorage(tmp_path)

    assert storage.read_manifest("abc") is None

    audio_url = storage.save("abc", b"fake-mp3-bytes", {"durationSec": 1.0})

    assert audio_url == "/static/audio/abc.mp3"
    assert (tmp_path / "abc.mp3").read_bytes() == b"fake-mp3-bytes"
    assert storage.read_manifest("abc") == {"durationSec": 1.0, "audioUrl": audio_url}


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

    audio_url = storage.save("abc", b"fake-mp3-bytes", {"durationSec": 1.0})

    assert audio_url == "https://cdn.example.com/abc.mp3"
    assert fake_client.objects["abc.mp3"] == b"fake-mp3-bytes"
    assert json.loads(fake_client.objects["abc.json"]) == {
        "durationSec": 1.0,
        "audioUrl": audio_url,
    }
    assert storage.read_manifest("abc") == {"durationSec": 1.0, "audioUrl": audio_url}
