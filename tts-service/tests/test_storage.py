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


def _db_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    from tts_app.config import get_database_settings

    get_database_settings.cache_clear()

    from tts_app.audio.storage import DbAudioStorage

    return DbAudioStorage()


def test_db_storage_roundtrip(tmp_path, monkeypatch):
    from tts_app.config import get_database_settings

    storage = _db_storage(tmp_path, monkeypatch)

    assert storage.read_manifest("abc") is None

    import uuid as uuid_module

    # 이 저장소의 DbAudioStorage는 모듈 임포트 시점에 엔진을 한 번만 만들어서
    # (tts_app/audio/db.py) monkeypatch로 세션마다 DB를 완전히 격리할 수 없다
    # (실제 tts-service/kom_cast.db를 같이 쓰는 다른 테스트도 있음). 그래서
    # user_id/script_id를 매 실행마다 새로 뽑아 충돌을 피한다.
    user_id = str(uuid_module.uuid4())
    script_id = str(uuid_module.uuid4())
    manifest = {
        "durationSec": 1.6,
        "segments": [
            {
                "speaker": "코스",
                "target": {"type": "STOCK", "stock_code": "005930"},
                "text": "삼성전자 얘기",
                "startSec": 0.0,
                "words": [{"text": "삼성전자", "startSec": 0.0, "endSec": 0.5}],
            },
            {
                "speaker": "코미",
                "target": {"type": "USER"},
                "text": "마무리 인사",
                "startSec": 0.8,
                "words": None,
            },
        ],
    }

    result = storage.save(
        "abc",
        b"fake-mp3-bytes",
        manifest,
        user_id=user_id,
        script_id=script_id,
        audio_type="DAILY_BRIEFING",
    )

    assert result.audio_url == ""
    assert result.audio_binary_id is not None
    # 캐시 조회는 지원하지 않으므로 저장 후에도 여전히 미스로 처리된다.
    assert storage.read_manifest("abc") is None

    import uuid

    from tts_app.audio.db import SessionFactory
    from tts_app.audio.models import Audio, AudioBinary, AudioSegment

    with SessionFactory() as session:
        binary_row = session.get(AudioBinary, uuid.UUID(result.audio_binary_id))
        assert binary_row is not None
        assert bytes(binary_row.data) == b"fake-mp3-bytes"

        audio_row = (
            session.query(Audio).filter_by(user_id=uuid.UUID(user_id)).one()
        )
        assert audio_row.script_id == uuid.UUID(script_id)
        assert audio_row.audio_type == "DAILY_BRIEFING"
        assert audio_row.audio_url == str(result.audio_binary_id)
        assert audio_row.duration_seconds == 2

        segment_rows = (
            session.query(AudioSegment)
            .filter_by(audio_id=audio_row.id)
            .order_by(AudioSegment.segment_order)
            .all()
        )
        assert [s.stock_code for s in segment_rows] == ["005930", None]
        assert [s.speaker for s in segment_rows] == ["코스", "코미"]

    get_database_settings.cache_clear()


def test_db_storage_requires_user_id(tmp_path, monkeypatch):
    from tts_app.config import get_database_settings

    storage = _db_storage(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="user_id"):
        storage.save("abc", b"fake-mp3-bytes", {"durationSec": 1.0, "segments": []})

    get_database_settings.cache_clear()
