from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class GenerateScriptsRequest(BaseModel):
    stock_ids: list[int] = Field(min_length=1)
    start_at: datetime
    end_at: datetime


class GenerateScriptsResponse(BaseModel):
    status: str
    generated_stock_ids: list[int]
    skipped_stock_ids: list[int]


class GenerateUserScriptsRequest(BaseModel):
    start_at: datetime
    end_at: datetime
    user_ids: list[UUID]

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone information is required")

        return value

    @field_validator("user_ids")
    @classmethod
    def remove_duplicate_user_ids(
        cls,
        value: list[UUID],
    ) -> list[UUID]:
        unique_user_ids = list(dict.fromkeys(value))

        if not unique_user_ids:
            raise ValueError("user_ids must not be empty")

        return unique_user_ids

    @model_validator(mode="after")
    def validate_period(self) -> "GenerateUserScriptsRequest":
        if self.start_at >= self.end_at:
            raise ValueError("start_at must be earlier than end_at")

        return self


class ScriptFailureCode(str, Enum):
    USER_NOT_FOUND = "USER_NOT_FOUND"
    NO_INTEREST_TARGET = "NO_INTEREST_TARGET"
    NO_NEWS_FOUND = "NO_NEWS_FOUND"
    AI_GENERATION_FAILED = "AI_GENERATION_FAILED"
    AI_RESPONSE_INVALID = "AI_RESPONSE_INVALID"
    DATABASE_ERROR = "DATABASE_ERROR"
    GENERATION_TIMEOUT = "GENERATION_TIMEOUT"


class GeneratedScriptResult(BaseModel):
    script_id: UUID
    user_id: UUID
    reused: bool


class ScriptFailureResult(BaseModel):
    user_id: UUID
    code: ScriptFailureCode
    message: str


class GenerateUserScriptsResponse(BaseModel):
    scripts: list[GeneratedScriptResult]
    failures: list[ScriptFailureResult]
