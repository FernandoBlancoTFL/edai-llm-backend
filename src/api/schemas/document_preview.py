from pydantic import BaseModel
from typing import List, Dict, Any


class DocumentPreview(BaseModel):
    file_id: str
    filename: str
    created_at: str
    row_count: int
    column_count: int
    headers: List[str]
    sample_rows: List[Dict[str, Any]]