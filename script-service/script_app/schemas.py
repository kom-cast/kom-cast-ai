from datetime import datetime

from pydantic import BaseModel, Field


class GenerateScriptsRequest(BaseModel):
    stock_ids: list[int] = Field(min_length=1)
    start_at: datetime
    end_at: datetime


class GenerateScriptsResponse(BaseModel):
    status: str
    generated_stock_ids: list[int]
    skipped_stock_ids: list[int]