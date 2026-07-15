from src.api.repositories import library_repository
from src.api.repositories.library_repository import (
    create_visualization
)

def get_library_datasets():
    return library_repository.get_library_datasets()


def get_visualizations(dataset_id: str):
    return library_repository.get_visualizations_by_dataset(
        dataset_id
    )

def save_visualization(
    user_id,
    chat_id,
    dataset_id,
    dataset_name,
    filename,
    cloudinary_url,
    cloudinary_public_id
):
    """
    Guarda una visualización generada por el usuario
    en la librería.

    Esta función actúa como capa de servicio
    entre el agente y el repository.
    """

    visualization_data = {
        "user_id": user_id,
        "chat_id": chat_id,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "filename": filename,
        "cloudinary_url": cloudinary_url,
        "cloudinary_public_id": cloudinary_public_id
    }


    return create_visualization(
        visualization_data
    )