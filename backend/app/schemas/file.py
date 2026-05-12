from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models.models import FileType


class FileResponse(BaseModel):
    
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    original_filename: str
    file_type: FileType
    uploaded_at: datetime



class TranscriptSegmentResponse(BaseModel):
    
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    start_seconds: float
    end_seconds: float
    segment_index: int



class SummaryResponse(BaseModel):
    file_id: int
    summary: str
    cached: bool = False