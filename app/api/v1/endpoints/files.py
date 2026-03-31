"""File upload and management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.v1.deps import ConfigDep, get_batch_service, get_workspace_service
from app.schemas.file import (
    BatchStatusResponse,
    DeleteResponse,
    SessionFileListResponse,
    UploadBatchFileResponse,
    UploadBatchResponse,
)
from app.services.session_workspace_service import SessionWorkspaceService
from app.services.upload_batch_service import UploadBatchService

router = APIRouter()


@router.post("/files/batches", response_model=UploadBatchResponse)
async def create_upload_batch(
    batch_service: UploadBatchService = Depends(get_batch_service),
    files: list[UploadFile] = File(...),
) -> UploadBatchResponse:
    """创建文件上传批次.

    Args:
        batch_service: 批次服务（注入）
        files: 上传的文件列表

    Returns:
        上传批次响应
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "NO_FILES",
                "message": "No files provided",
            },
        )

    metadata = await batch_service.create_batch(files)

    return UploadBatchResponse(
        success=True,
        upload_batch_id=metadata.upload_batch_id,
        status=metadata.status,
        files=[
            UploadBatchFileResponse(
                file_id=f.file_id,
                filename=f.safe_filename,
                content_type=f.content_type,
                size=f.size,
            )
            for f in metadata.files
        ],
    )


@router.get("/files/batches/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    batch_service: UploadBatchService = Depends(get_batch_service),
) -> BatchStatusResponse:
    """查询上传批次状态.

    Args:
        batch_id: 批次 ID
        batch_service: 批次服务（注入）

    Returns:
        批次状态响应
    """
    metadata = batch_service.get_batch(batch_id)

    return BatchStatusResponse(
        upload_batch_id=metadata.upload_batch_id,
        status=metadata.status,
        created_at=metadata.created_at,
        expires_at=metadata.expires_at,
        bound_session_id=metadata.bound_session_id,
        files=metadata.files,
    )


@router.delete("/files/batches/{batch_id}", response_model=DeleteResponse)
async def delete_batch(
    batch_id: str,
    batch_service: UploadBatchService = Depends(get_batch_service),
) -> DeleteResponse:
    """删除上传批次.

    Args:
        batch_id: 批次 ID
        batch_service: 批次服务（注入）

    Returns:
        删除响应
    """
    batch_service.delete_batch(batch_id)

    return DeleteResponse(
        success=True,
        message=f"Batch {batch_id} deleted successfully",
    )


@router.get("/files/sessions/{session_id}", response_model=SessionFileListResponse)
async def list_session_files(
    session_id: str,
    workspace_service: SessionWorkspaceService = Depends(get_workspace_service),
) -> SessionFileListResponse:
    """列出会话的所有文件.

    Args:
        session_id: 会话 ID
        workspace_service: 工作区服务（注入）

    Returns:
        文件列表响应
    """
    files = workspace_service.list_session_files(session_id)
    total_size = sum(f.size for f in files)

    return SessionFileListResponse(
        session_id=session_id,
        total_files=len(files),
        total_size=total_size,
        files=files,
    )


@router.get("/files/sessions/{session_id}/{file_id}")
async def download_session_file(
    session_id: str,
    file_id: str,
    inline: bool = False,
    workspace_service: SessionWorkspaceService = Depends(get_workspace_service),
) -> FileResponse:
    """下载或预览会话文件.

    Args:
        session_id: 会话 ID
        file_id: 文件 ID
        inline: 是否内联预览（默认下载）
        workspace_service: 工作区服务（注入）

    Returns:
        文件响应
    """
    file_path = workspace_service.get_session_file_path(session_id, file_id)
    manifest = workspace_service.get_session_manifest(session_id)

    # 查找文件元数据
    file_meta = None
    for f in manifest.files:
        if f.file_id == file_id:
            file_meta = f
            break

    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    # 危险文件类型强制下载
    force_download_types = {
        "text/html",
        "application/javascript",
        "image/svg+xml",
    }

    disposition = "inline" if inline and file_meta.content_type not in force_download_types else "attachment"

    return FileResponse(
        path=file_path,
        media_type=file_meta.content_type,
        filename=file_meta.safe_filename,
        headers={"Content-Disposition": f'{disposition}; filename="{file_meta.safe_filename}"'},
    )


@router.delete("/files/sessions/{session_id}/{file_id}", response_model=DeleteResponse)
async def delete_session_file(
    session_id: str,
    file_id: str,
    workspace_service: SessionWorkspaceService = Depends(get_workspace_service),
) -> DeleteResponse:
    """删除会话文件.

    Args:
        session_id: 会话 ID
        file_id: 文件 ID
        workspace_service: 工作区服务（注入）

    Returns:
        删除响应
    """
    workspace_service.delete_session_file(session_id, file_id)

    return DeleteResponse(
        success=True,
        message=f"File {file_id} deleted successfully",
    )


@router.delete("/files/sessions/{session_id}", response_model=DeleteResponse)
async def delete_session_all_files(
    session_id: str,
    workspace_service: SessionWorkspaceService = Depends(get_workspace_service),
) -> DeleteResponse:
    """清理会话所有文件.

    Args:
        session_id: 会话 ID
        workspace_service: 工作区服务（注入）

    Returns:
        删除响应
    """
    workspace_service.delete_session(session_id)

    return DeleteResponse(
        success=True,
        message=f"All files in session {session_id} deleted successfully",
    )
