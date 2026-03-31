"""Agent execution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

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
from app.api.v1.deps import ConfigDep, FileStoreDep, TracerDep
from app.schemas import AgentResponse, ExecutionResult, StructuredAgentResponse

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
    file_store: FileStoreDep,
    tracer: TracerDep,
    prompt: str = Form(...),
    session_id: str | None = Form(None),
    structured_output_profile: str | None = Form(None),
    final_answer_text_policy: str | None = Form(None),
    user_id: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
) -> AgentResponse | StructuredAgentResponse:
    """Execute agent with the given prompt and files.

    Args:
        config: Application configuration (injected)
        file_store: File storage (injected)
        tracer: Langfuse tracer (injected)
        prompt: User prompt/query
        session_id: Optional session ID for conversation continuation
        structured_output_profile: Optional profile for structured output validation
        final_answer_text_policy: How to assemble final answer text (full or last_assistant_turn)
        user_id: Optional user ID for tracing
        files: Optional uploaded files

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

    # Start LangFuse trace
    trace_metadata = {
        "prompt_length": len(prompt),
        "has_files": len(files) > 0,
        "file_count": len(files),
        "structured_output_profile": sop,
        "final_answer_policy": text_policy,
    }

    with tracer.trace_agent_execution(
        session_id=session_id,
        user_id=user_id,
        metadata=trace_metadata,
    ) as trace_id:
        try:
            if session_id:
                working_dir = file_store.ensure_session_dir(session_id)
                saved_files = await file_store.save_uploads(files, working_dir)
                prepared_prompt = file_store.build_prompt(
                    prompt=prompt,
                    saved_files=saved_files,
                    template=config.api.file_prompt_template,
                    target_dir=working_dir,
                )
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

            working_dir = file_store.create_pending_dir()
            saved_files = await file_store.save_uploads(files, working_dir)
            prepared_prompt = file_store.build_prompt(
                prompt=prompt,
                saved_files=saved_files,
                template=config.api.file_prompt_template,
                target_dir=working_dir,
            )
            result = await execute_agent_message(
                config=config,
                prompt=prepared_prompt,
                cwd=working_dir,
                output_format=output_fmt,
                final_answer_text_policy=text_policy,
                user_id=user_id,
            )
            file_store.finalize_pending_dir(working_dir, result.session_id)
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
