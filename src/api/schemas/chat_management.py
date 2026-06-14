from pydantic import BaseModel
from datetime import datetime


class CreateChatRequest(BaseModel):
    name: str


class UpdateChatRequest(BaseModel):
    name: str


class ChatInfo(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class CreateChatResponse(BaseModel):
    id: str
    name: str