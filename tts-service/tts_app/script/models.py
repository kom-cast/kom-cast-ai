from pydantic import BaseModel


class DialogueLine(BaseModel):
    speaker: str
    stock: str
    text: str


class Script(BaseModel):
    briefing_id: str
    lines: list[DialogueLine]
