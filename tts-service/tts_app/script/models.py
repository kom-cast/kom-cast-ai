from typing import Annotated, Literal

from pydantic import BaseModel, Field


class StockTarget(BaseModel):
    type: Literal["STOCK"]
    stock_code: str


class IndustryTarget(BaseModel):
    type: Literal["INDUSTRY"]
    industry_code: str


class UserTarget(BaseModel):
    type: Literal["USER"]


BriefingTarget = Annotated[
    StockTarget | IndustryTarget | UserTarget,
    Field(discriminator="type"),
]


class DialogueLine(BaseModel):
    speaker: str
    text: str


class Section(BaseModel):
    target: BriefingTarget
    lines: list[DialogueLine]


class Script(BaseModel):
    script_id: str
    # AUDIO_BACKEND=db일 때 tts-service가 audios/audio_segments 테이블에
    # 직접 저장하기 위해 필요하다(Spring의 audios.user_id는 not null FK).
    # local/ncp 백엔드에서는 쓰이지 않아 선택값으로 둔다.
    user_id: str | None = None
    audio_type: str = "DAILY_BRIEFING"
    sections: list[Section] = Field(min_length=1)
