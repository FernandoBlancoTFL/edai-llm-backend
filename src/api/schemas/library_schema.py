from pydantic import BaseModel
from datetime import datetime


class DatasetLibraryItem(BaseModel):
    dataset_id: str
    dataset_name: str
    total_visualizations: int


class VisualizationItem(BaseModel):
    id: str
    dataset_id: str
    cloudinary_url: str
    created_at: datetime