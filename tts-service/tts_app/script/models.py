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


class UserTarget(BaseModel):
    type: Literal["USER"]


BriefingTarget = Annotated[
    Union[StockTarget, IndustryTarget, UserTarget],
    Field(discriminator="type"),
]


class Script(BaseModel):
    script_id: str
    target: BriefingTarget
    lines: list[DialogueLine]
