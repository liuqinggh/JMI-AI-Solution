"""Agent execution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException

from app.agents.executor import execute_agent_message
from app.agents.schema_registry import get_output_format
from app.api.jmi_fresh_claim_doc_check_output import (
    STRUCTURED_OUTPUT_PROFILE_JMI_FRESH_CLAIM,
    parse_jmi_fresh_claim_doc_check_final_answer,
)
from app.api.jmi_intake_checkout_output import (
    STRUCTURED_OUTPUT_PROFILE_JMI_INTAKE,
    parse_jmi_intake_checkout_final_answer,
    strip_markdown_json_fence,
)
from app.api.v1.deps import (
    ConfigDep,
    TracerDep,
    get_batch_service,
    get_workspace_service,
)
from app.schemas import AgentResponse, ExecutionResult, StructuredAgentResponse
from app.services.session_workspace_service import SessionWorkspaceService
from app.services.upload_batch_service import UploadBatchService

router = APIRouter()

ALLOWED_STRUCTURED_OUTPUT_PROFILES: frozenset[str | None] = frozenset(
    {
        None,
        STRUCTURED_OUTPUT_PROFILE_JMI_INTAKE,
        STRUCTURED_OUTPUT_PROFILE_JMI_FRESH_CLAIM,
    }
)


def _resolve_final_answer_text_policy(
    form_value: str | None,
    *,
    structured_profile: str | None,
    config_default: str,
) -> str:
    """Resolve final_answer_text_policy from form value or defaults.

    未传表单时：若启用 structured_output_profile，默认 last_assistant_turn
    （避免多轮中间说明拼进 final_answer）。
    """
    v = (form_value or "").strip()
    if v:
        if v not in ("full", "last_assistant_turn"):
            raise HTTPException(
                status_code=400,
                detail="final_answer_text_policy 须为 full 或 last_assistant_turn",
            )
        return v
    if structured_profile:
        return "last_assistant_turn"
    return config_default


def _apply_structured_output_profile(
    *,
    profile: str | None,
    final_answer: str,
) -> tuple[dict | None, bool | None, str | None, str]:
    """Apply structured output profile parsing.

    返回 (structured_output, structured_valid, structured_error, cleaned_final_answer)。
    当解析成功时用校验后的 JSON 覆盖 final_answer；失败时至少剥掉围栏。
    """
    p = (profile or "").strip() or None
    if p is None:
        return None, None, None, final_answer
    if p == STRUCTURED_OUTPUT_PROFILE_JMI_INTAKE:
        parsed, err = parse_jmi_intake_checkout_final_answer(final_answer)
        if parsed is not None:
            clean_json = parsed.model_dump_json(indent=2, exclude_none=False)
            return parsed.model_dump(), True, None, clean_json
        cleaned = strip_markdown_json_fence(final_answer)
        return None, False, err, cleaned
    if p == STRUCTURED_OUTPUT_PROFILE_JMI_FRESH_CLAIM:
        parsed, err = parse_jmi_fresh_claim_doc_check_final_answer(final_answer)
        if parsed is not None:
            clean_json = parsed.model_dump_json(indent=2, exclude_none=False)
            return parsed.model_dump(), True, None, clean_json
        cleaned = strip_markdown_json_fence(final_answer)
        return None, False, err, cleaned
    return None, None, None, final_answer


def _build_response(
    result: ExecutionResult,
    sop: str | None,
) -> StructuredAgentResponse | AgentResponse:
    """Build response based on structured output profile.

    根据是否启用 structured_output_profile 返回精简或完整响应。
    - 启用且有 SDK structured_output → StructuredAgentResponse（仅 session_id + structured_output）
    - 启用但校验失败 → AgentResponse（含 structured_error，便于排错）
    - 未启用          → AgentResponse（原有行为）
    """
    # 优先使用 SDK 原生的 structured_output
    if sop and result.structured_output is not None:
        return StructuredAgentResponse(
            session_id=result.session_id,
            structured_output=result.structured_output,
        )

    # 降级到后处理方案（兼容性或调试）
    out, valid, s_err, clean_fa = _apply_structured_output_profile(
        profile=sop,
        final_answer=result.final_answer,
    )
    if sop and valid and out is not None:
        return StructuredAgentResponse(
            session_id=result.session_id,
            structured_output=out,
        )
    payload = result.model_dump()
    payload["final_answer"] = clean_fa
    payload["structured_output"] = out
    payload["structured_valid"] = valid
    payload["structured_error"] = s_err
    return AgentResponse.model_validate(payload)


@router.post(
    "/agent/messages",
    response_model=AgentResponse | StructuredAgentResponse,
)
async def create_agent_message(
    config: ConfigDep,
    tracer: TracerDep,
    prompt: str = Form(...),
    session_id: str | None = Form(None),
    upload_batch_id: str | None = Form(None),
    file_ids: str | None = Form(None),
    structured_output_profile: str | None = Form(None),
    final_answer_text_policy: str | None = Form(None),
    user_id: str | None = Form(None),
    batch_service: UploadBatchService = Depends(get_batch_service),
    workspace_service: SessionWorkspaceService = Depends(get_workspace_service),
) -> AgentResponse | StructuredAgentResponse:
    """Execute agent with the given prompt and optional file batch.

    Args:
        config: Application configuration (injected)
        tracer: Langfuse tracer (injected)
        prompt: User prompt/query
        session_id: Optional session ID for conversation continuation
        upload_batch_id: Optional upload batch ID to bind to this message
        file_ids: Optional comma-separated file IDs (if only binding subset)
        structured_output_profile: Optional profile for structured output validation
        final_answer_text_policy: How to assemble final answer text (full or last_assistant_turn)
        user_id: Optional user ID for tracing
        batch_service: Batch service (injected)
        workspace_service: Workspace service (injected)

    Returns:
        Agent response (standard or structured)

    Raises:
        HTTPException: If validation fails or agent execution errors
    """
    sop = (structured_output_profile or "").strip() or None
    if sop not in ALLOWED_STRUCTURED_OUTPUT_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=(
                "structured_output_profile 无效；支持: "
                f"{STRUCTURED_OUTPUT_PROFILE_JMI_INTAKE!r}、"
                f"{STRUCTURED_OUTPUT_PROFILE_JMI_FRESH_CLAIM!r} 或留空"
            ),
        )
    text_policy = _resolve_final_answer_text_policy(
        final_answer_text_policy,
        structured_profile=sop,
        config_default=config.api.final_answer_text_policy,
    )
    output_fmt = get_output_format(sop)  # 动态获取 Schema

    # 解析 file_ids（如果提供）
    selected_file_ids = None
    if file_ids:
        selected_file_ids = [fid.strip() for fid in file_ids.split(",") if fid.strip()]

    # Start LangFuse trace
    trace_metadata = {
        "prompt_length": len(prompt),
        "has_batch": upload_batch_id is not None,
        "structured_output_profile": sop,
        "final_answer_policy": text_policy,
    }

    with tracer.trace_agent_execution(
        session_id=session_id,
        user_id=user_id,
        metadata=trace_metadata,
    ) as trace_id:
        try:
            # 续接会话
            if session_id:
                working_dir = workspace_service.get_session_workspace(session_id)

                # 如果有新批次，追加到会话
                if upload_batch_id:
                    workspace_service.import_batch_to_workspace(
                        working_dir,
                        upload_batch_id,
                        selected_file_ids,
                    )
                    batch_service.consume_batch(upload_batch_id, session_id)

                # 构建文件上下文
                files_context = workspace_service.build_files_context(session_id)
                prepared_prompt = f"{files_context}\n\n{prompt}" if files_context else prompt

                result = await execute_agent_message(
                    config=config,
                    prompt=prepared_prompt,
                    cwd=working_dir,
                    session_id=session_id,
                    output_format=output_fmt,
                    final_answer_text_policy=text_policy,
                    user_id=user_id,
                )
                response = _build_response(result, sop)

                # Update trace with final result
                if trace_id:
                    tracer.update_trace(
                        output={"final_answer": result.final_answer, "success": result.success},
                        metadata={"response_type": type(response).__name__},
                        tags=["session_continuation", sop] if sop else ["session_continuation"],
                    )
                return response

            # 新会话
            import uuid

            request_id = f"req_{uuid.uuid4().hex}"
            working_dir = workspace_service.create_pending_workspace(request_id)

            # 如果有批次，导入到 pending workspace
            if upload_batch_id:
                workspace_service.import_batch_to_workspace(
                    working_dir,
                    upload_batch_id,
                    selected_file_ids,
                )

            # 构建文件上下文（使用临时 request_id）
            manifest_path = working_dir / "manifest.json"
            files_context = ""
            if manifest_path.exists():
                from app.schemas.file import SessionManifest

                manifest = SessionManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
                if manifest.files:
                    file_lines = []
                    for file_meta in manifest.files:
                        size_mb = file_meta.size / (1024 * 1024)
                        file_lines.append(
                            f"- {file_meta.safe_filename} ({size_mb:.2f} MB, {file_meta.content_type})\n"
                            f"  Path: {file_meta.relative_path}"
                        )
                    files_list = "\n".join(file_lines)
                    files_context = f"""
<uploaded_files>
The following files have been uploaded and are available in this session:

{files_list}

You can read these files using the built-in Read tool with the paths shown above.
Example: Read("{manifest.files[0].relative_path}")
</uploaded_files>
"""

            prepared_prompt = f"{files_context}\n\n{prompt}" if files_context else prompt

            result = await execute_agent_message(
                config=config,
                prompt=prepared_prompt,
                cwd=working_dir,
                output_format=output_fmt,
                final_answer_text_policy=text_policy,
                user_id=user_id,
            )

            # 将 pending workspace 迁移到 session workspace
            workspace_service.finalize_pending_workspace(working_dir, result.session_id)

            # 消费批次
            if upload_batch_id:
                batch_service.consume_batch(upload_batch_id, result.session_id)

            response = _build_response(result, sop)

            # Update trace with final result
            if trace_id:
                tracer.update_trace(
                    output={"final_answer": result.final_answer, "success": result.success},
                    metadata={"response_type": type(response).__name__},
                    tags=["new_session", sop] if sop else ["new_session"],
                )
            return response
        except HTTPException:
            raise
        except Exception as exc:
            # Log error to trace
            if trace_id:
                tracer.log_event(
                    name="api_error",
                    metadata={"error_type": type(exc).__name__, "error": str(exc)},
                    level="ERROR",
                )
            raise HTTPException(status_code=500, detail=f"Agent 执行失败: {exc}") from exc
