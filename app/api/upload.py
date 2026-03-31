from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.config import Settings, get_settings
from app.models.upload import UploadResponse
from app.services.upload_service import UploadService

router = APIRouter()


def get_upload_service(settings: Settings = Depends(get_settings)) -> UploadService:
    return UploadService(settings.upload)


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: list[UploadFile] = File(...),
    service: UploadService = Depends(get_upload_service),
) -> UploadResponse:
    stored_files = await service.save_files(files)
    return UploadResponse(files=stored_files)
