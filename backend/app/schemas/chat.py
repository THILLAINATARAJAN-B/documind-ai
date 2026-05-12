from pydantic import BaseModel,ConfigDict
from typing import Optional


class AskRequest(BaseModel):
    file_id: int
    question: str
    session_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    timestamp_ref: Optional[float] = None

