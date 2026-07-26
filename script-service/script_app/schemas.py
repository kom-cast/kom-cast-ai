from datetime import datetime
from enum import Enum
from typing import Annotated
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


class ScriptTalker(str, Enum):
    KOS = "코스"
    KOMI = "코미"


class AiScriptLine(BaseModel):
    talker: ScriptTalker
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped_value = value.strip()

        if not stripped_value:
            raise ValueError("content must not be empty")

        return stripped_value


class CommonSectionAiResponse(BaseModel):
    lines: list[AiScriptLine] = Field(min_length=1)


BridgeLines = Annotated[
    list[AiScriptLine],
    Field(min_length=1),
]


class PersonalSectionsAiResponse(BaseModel):
    opening: list[AiScriptLine] = Field(min_length=1)
    bridges: list[BridgeLines]
    closing: list[AiScriptLine] = Field(min_length=1)

    def validate_bridge_count(
        self,
        content_section_count: int,
    ) -> "PersonalSectionsAiResponse":
        if content_section_count < 1:
            raise ValueError(
                "content_section_count must be greater than 0"
            )

        expected_bridge_count = content_section_count - 1

        if len(self.bridges) != expected_bridge_count:
            raise ValueError(
                "bridge count must be one less than "
                "content section count"
            )

        return self
