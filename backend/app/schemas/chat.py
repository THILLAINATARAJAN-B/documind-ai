from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional


class AskRequest(BaseModel):
    file_id: int
    question: str
    session_id: Optional[int] = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        if len(v) > 2000:
            raise ValueError("Question must be 2000 characters or fewer")
        return v


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    timestamp_ref: Optional[float] = None
