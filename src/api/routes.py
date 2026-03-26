from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from src.agent.executor import execute_agent_message
from src.agent.schema_registry import get_output_format
from src.api.jmi_fresh_claim_doc_check_output import (
    STRUCTURED_OUTPUT_PROFILE_JMI_FRESH_CLAIM,
    parse_jmi_fresh_claim_doc_check_final_answer,
)
from src.api.jmi_intake_checkout_output import (
    STRUCTURED_OUTPUT_PROFILE_JMI_INTAKE,
    parse_jmi_intake_checkout_final_answer,
    strip_markdown_json_fence,
)

ALLOWED_STRUCTURED_OUTPUT_PROFILES: frozenset[str | None] = frozenset(
    {
        None,
        STRUCTURED_OUTPUT_PROFILE_JMI_INTAKE,
        STRUCTURED_OUTPUT_PROFILE_JMI_FRESH_CLAIM,
    }
)
from src.api.models import AgentResponse, ConfigInfo, HealthResponse, StructuredAgentResponse
from src.config import configure_sdk_environment, get_config
from src.storage.content_store import ContentAddressedStore
from src.tracing.langfuse_tracer import LangfuseTracer
from src.agent.executor import set_tracer


config = configure_sdk_environment(get_config())
file_store = ContentAddressedStore(config.storage)

# Initialize LangFuse tracer
tracer = LangfuseTracer(config.langfuse)
set_tracer(tracer)

app = FastAPI(title="Agent SDK API Service", version="0.1.0")
TEST_PAGE_PATH = Path(__file__).resolve().parent / "static" / "test" / "index.html"


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    tracer.shutdown()


@app.get("/", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status="healthy",
        service="agent-sdk-api-service",
        version="0.1.0",
    )


@app.get("/config", response_model=ConfigInfo)
async def get_config_info():
    """获取当前配置信息"""
    use_vertex = config.sdk.env.get("CLAUDE_CODE_USE_VERTEX") == "1"
    use_bedrock = config.sdk.env.get("CLAUDE_CODE_USE_BEDROCK") == "1"
    use_foundry = config.sdk.env.get("CLAUDE_CODE_USE_FOUNDRY") == "1"

    provider = "Local Proxy"
    if use_vertex:
        provider = "Vertex AI"
    elif use_bedrock:
        provider = "AWS Bedrock"
    elif use_foundry:
        provider = "Anthropic Foundry"

    return ConfigInfo(
        model=config.sdk.model,
        provider=provider,
        max_turns=config.sdk.max_turns,
        permission_mode=config.sdk.permission_mode or "manual",
        vertex_project_id=config.sdk.env.get("ANTHROPIC_VERTEX_PROJECT_ID") if use_vertex else None,
        region=config.sdk.env.get("CLOUD_ML_REGION") if use_vertex else None,
    )


@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """测试页面"""
    return FileResponse(TEST_PAGE_PATH)


def _resolve_final_answer_text_policy(
    form_value: str | None,
    *,
    structured_profile: str | None,
    config_default: str,
) -> str:
    """
    未传表单时：若启用 structured_output_profile，默认 last_assistant_turn（避免多轮中间说明拼进 final_answer）。
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
    """
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


from src.api.models import ExecutionResult as _ER  # noqa: E402 (used only in type hint below)


def _build_response(
    result: _ER,
    sop: str | None,
) -> StructuredAgentResponse | AgentResponse:
    """
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


@app.post(
    "/v1/agent/messages",
    response_model=AgentResponse | StructuredAgentResponse,
)
async def create_agent_message(
    prompt: str = Form(...),
    session_id: str | None = Form(None),
    structured_output_profile: str | None = Form(None),
    final_answer_text_policy: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
):
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
                output_format=output_fmt,  # 传递给 SDK
                final_answer_text_policy=text_policy,
            )
            return _build_response(result, sop)

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
            output_format=output_fmt,  # 传递给 SDK
            final_answer_text_policy=text_policy,
        )
        file_store.finalize_pending_dir(working_dir, result.session_id)
        return _build_response(result, sop)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {exc}") from exc
