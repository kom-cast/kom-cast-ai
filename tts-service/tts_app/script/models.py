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
    sections: list[Section] = Field(min_length=1)
