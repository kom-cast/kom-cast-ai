from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class DialogueLine(BaseModel):
    speaker: str
    text: str


class StockTarget(BaseModel):
    type: Literal["STOCK"]
    stock_id: int


class IndustryTarget(BaseModel):
    type: Literal["INDUSTRY"]
    industry_id: int


class OtherTarget(BaseModel):
    type: Literal["OTHER"]


BriefingTarget = Annotated[
    Union[StockTarget, IndustryTarget, OtherTarget],
    Field(discriminator="type"),
]


class Script(BaseModel):
    briefing_id: str
    target: BriefingTarget
    lines: list[DialogueLine]
