from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TYPECAST_", env_file=".env", extra="ignore"
    )

    api_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


class StorageSettings(BaseSettings):
    """오디오 저장소 설정. backend=local이면 static/audio 디스크에 저장하고,
    backend=ncp면 네이버클라우드(금융) Object Storage(S3 호환)에 저장한다.
    https://guide-fin.ncloud-docs.com/docs/storage-storage-8-2
    """

    model_config = SettingsConfigDict(
        env_prefix="AUDIO_", env_file=".env", extra="ignore"
    )

    backend: Literal["local", "ncp"] = "local"

    ncp_endpoint_url: str = "https://kr.object.fin-ncloudstorage.com"
    ncp_region: str = "fin-standard"
    ncp_access_key: str | None = None
    ncp_secret_key: str | None = None
    ncp_bucket: str | None = None
    # 버킷을 origin으로 붙인 CDN 도메인. audioUrl 조립에 사용.
    cdn_base_url: str | None = None

    @model_validator(mode="after")
    def _require_ncp_fields_when_selected(self) -> "StorageSettings":
        if self.backend != "ncp":
            return self

        missing = [
            name
            for name, value in (
                ("AUDIO_NCP_ACCESS_KEY", self.ncp_access_key),
                ("AUDIO_NCP_SECRET_KEY", self.ncp_secret_key),
                ("AUDIO_NCP_BUCKET", self.ncp_bucket),
                ("AUDIO_CDN_BASE_URL", self.cdn_base_url),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                f"AUDIO_BACKEND=ncp 사용 시 다음 환경변수가 필요합니다: {', '.join(missing)}"
            )
        return self


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()
