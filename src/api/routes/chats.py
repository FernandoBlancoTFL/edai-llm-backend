from fastapi import APIRouter, HTTPException

from api.schemas.chat_management import (
    CreateChatRequest,
    UpdateChatRequest
)

from services import chat_management_service

router = APIRouter()

@router.post("/")
def create_chat_endpoint(request: CreateChatRequest):

    return chat_management_service.create_chat(
        request.name
    )

@router.get("/")
def get_chats_endpoint():

    return chat_management_service.get_chats()

@router.put("/{chat_id}")
def update_chat_endpoint(
    chat_id: str,
    request: UpdateChatRequest
):

    chat = chat_management_service.update_chat_name(
        chat_id,
        request.name
    )

    if not chat:
        raise HTTPException(
            status_code=404,
            detail="Chat no encontrado"
        )

    return chat

@router.delete("/{chat_id}")
def delete_chat_endpoint(chat_id: str):

    deleted = chat_management_service.delete_chat(
        chat_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Chat no encontrado"
        )

    return {
        "message": "Chat eliminado"
    }

