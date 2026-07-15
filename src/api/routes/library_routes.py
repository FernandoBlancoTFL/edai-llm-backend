from fastapi import APIRouter

from src.services import library_service

router = APIRouter()

@router.get("/datasets")
def get_library_datasets():

    return library_service.get_library_datasets()

@router.get("/datasets/{dataset_id}/visualizations")
def get_visualizations(
    dataset_id: str
):

    return library_service.get_visualizations(
        dataset_id
    )