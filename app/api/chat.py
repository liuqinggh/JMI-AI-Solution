from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

import app.agents.client as agent_client
from app.core.config import AppDefinition, Settings, get_settings
from app.core.permissions import resolve_permissions
from app.core.session_manager import SessionManager
from app.models.app import RegisteredApp
from app.models.chat import ChatRequest
from app.services.app_registry import AppRegistry
from app.services.skill_loader import SkillLoader
from app.services.upload_service import UploadService
from app.services.workspace_service import WorkspaceService

router = APIRouter()


def _session_manager(settings: Settings) -> SessionManager:
    return SessionManager(Path.cwd() / settings.session.storage_dir)


def _upload_service(settings: Settings) -> UploadService:
    return UploadService(settings.upload)


def _resolve_registered_app(settings: Settings, request: ChatRequest) -> RegisteredApp:
    if request.app_id:
        registered = AppRegistry(settings).get_app(request.app_id)
        if request.skill_name and request.skill_name != registered.skill_name:
            raise HTTPException(status_code=400, detail="skill_name does not match app_id")
        return registered

    return RegisteredApp(
        app_id="adhoc",
        skill_name=request.skill_name or "",
        cwd=".",
        permission_mode=settings.claude.permission_mode,
        allowed_tools=[],
    )


def _format_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    registered_app = _resolve_registered_app(settings, request)
    skill_prompt = SkillLoader().load(registered_app.skill_name)
    permission = resolve_permissions(
        settings=settings,
        app_definition=AppDefinition(
            skill_name=registered_app.skill_name,
            cwd=registered_app.cwd,
            permission_mode=registered_app.permission_mode,
            allowed_tools=registered_app.allowed_tools,
        ),
    )

    session_manager = _session_manager(settings)
    existing_mapping = session_manager.get_mapping(request.business_session_id)
    resume_session_id = existing_mapping.sdk_session_id if existing_mapping else None

    upload_service = _upload_service(settings)
    uploads = [upload_service.get_file(file_id) for file_id in request.file_ids]
    workspace_service = WorkspaceService()
    cwd, relative_paths = workspace_service.prepare_workspace(
        business_session_id=request.business_session_id,
        app_cwd=registered_app.cwd,
        uploads=uploads,
    )
    composed_message = workspace_service.build_message(
        message=request.message,
        relative_paths=relative_paths,
    )

    async def event_stream() -> AsyncIterator[str]:
        resolved_session_id = resume_session_id
        try:
            async for event in agent_client.stream_chat(
                settings=settings,
                message=composed_message,
                skill_prompt=skill_prompt,
                cwd=cwd,
                permission=permission,
                resume_session_id=resume_session_id,
            ):
                candidate_session_id = event.get("sdk_session_id")
                if isinstance(candidate_session_id, str) and candidate_session_id:
                    resolved_session_id = candidate_session_id
                    session_manager.save_mapping(
                        business_session_id=request.business_session_id,
                        sdk_session_id=resolved_session_id,
                        app_id=request.app_id or registered_app.app_id,
                        skill_name=registered_app.skill_name,
                    )
                event_name = str(event["event"])
                payload = {key: value for key, value in event.items() if key != "event"}
                yield _format_sse(event_name, payload)
        except Exception as exc:
            yield _format_sse("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
