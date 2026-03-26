from pathlib import Path

from fastapi.testclient import TestClient

from src.api import routes
from src.api.models import ExecutionResult
from src.config import StorageSettings
from src.storage.content_store import ContentAddressedStore


def test_test_page_is_available():
    client = TestClient(routes.app)
    response = client.get("/test")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Agent API 测试页" in response.text


def test_messages_endpoint_multipart_prompt_only_returns_sdk_session_id(monkeypatch, tmp_path):
    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    async def fake_execute_agent_message(*, config, prompt, cwd, session_id=None, **kwargs):
        assert session_id is None
        assert Path(cwd).exists()
        assert prompt == "hello"
        assert kwargs.get("final_answer_text_policy") == "full"
        return ExecutionResult(
            session_id="sdk-session-1",
            final_answer="done",
            steps=[],
            success=True,
            final_answer_text_policy="full",
        )

    monkeypatch.setattr(routes, "execute_agent_message", fake_execute_agent_message)

    client = TestClient(routes.app)
    response = client.post(
        "/v1/agent/messages",
        files={"prompt": (None, "hello")},
    )

    assert response.status_code == 200
    assert response.json()["final_answer_text_policy"] == "full"
    assert response.json()["session_id"] == "sdk-session-1"
    assert (tmp_path / "uploads" / ".sessions" / "sdk-session-1").exists()
    assert (tmp_path / "uploads" / "sdk-session-1").is_symlink()


def test_messages_endpoint_saves_files_and_builds_prompt(monkeypatch, tmp_path):
    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    async def fake_execute_agent_message(*, config, prompt, cwd, session_id=None, **kwargs):
        assert session_id is None
        assert "report.pdf" in prompt
        assert Path(cwd, "report.pdf").exists()
        return ExecutionResult(
            session_id="sdk-session-2",
            final_answer="uploaded",
            steps=[],
            success=True,
        )

    monkeypatch.setattr(routes, "execute_agent_message", fake_execute_agent_message)

    client = TestClient(routes.app)
    response = client.post(
        "/v1/agent/messages",
        data={"prompt": "请分析文件"},
        files={"files": ("report.pdf", b"demo", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sdk-session-2"
    stored_file = tmp_path / "uploads" / ".sessions" / "sdk-session-2" / "report.pdf"
    assert stored_file.exists()
    assert stored_file.is_symlink()


def test_messages_endpoint_builds_multimodal_prompt_for_images(monkeypatch, tmp_path):
    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    async def fake_execute_agent_message(*, config, prompt, cwd, session_id=None, **kwargs):
        assert session_id is None
        assert isinstance(prompt, list)
        assert prompt[0]["type"] == "text"
        assert "sample.png" in prompt[0]["text"]
        assert prompt[1]["type"] == "image"
        assert prompt[1]["source"]["media_type"] == "image/png"
        assert Path(cwd, "sample.png").exists()
        return ExecutionResult(
            session_id="sdk-session-3",
            final_answer="image uploaded",
            steps=[],
            success=True,
        )

    monkeypatch.setattr(routes, "execute_agent_message", fake_execute_agent_message)

    client = TestClient(routes.app)
    response = client.post(
        "/v1/agent/messages",
        data={"prompt": "请分析这张图片"},
        files={"files": ("sample.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sdk-session-3"


def test_messages_endpoint_uses_session_workspace_for_session_resume(monkeypatch, tmp_path):
    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    first_cwd: Path | None = None

    async def fake_execute_agent_message(*, config, prompt, cwd, session_id=None, **kwargs):
        nonlocal first_cwd
        cwd_path = Path(cwd)

        if session_id is None:
            first_cwd = cwd_path
            return ExecutionResult(
                session_id="sdk-session-4",
                final_answer="first",
                steps=[],
                success=True,
            )

        assert session_id == "sdk-session-4"
        assert first_cwd is not None
        assert first_cwd.parent.name == ".pending"
        assert cwd_path == tmp_path / "uploads" / ".sessions" / "sdk-session-4"
        return ExecutionResult(
            session_id="sdk-session-4",
            final_answer="second",
            steps=[],
            success=True,
        )

    monkeypatch.setattr(routes, "execute_agent_message", fake_execute_agent_message)

    client = TestClient(routes.app)
    first = client.post("/v1/agent/messages", files={"prompt": (None, "hello")})
    second = client.post(
        "/v1/agent/messages",
        files={
            "prompt": (None, "again"),
            "session_id": (None, "sdk-session-4"),
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (tmp_path / "uploads" / "sdk-session-4").is_symlink()


def test_messages_structured_profile_validation_fail_returns_full_response(monkeypatch, tmp_path):
    """structured_output_profile 启用但 JSON 校验失败 → 返回完整 AgentResponse 含 structured_error。"""
    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    async def fake_execute_agent_message(*, config, prompt, cwd, session_id=None, **kwargs):
        pol = kwargs.get("final_answer_text_policy")
        assert pol == "last_assistant_turn"
        return ExecutionResult(
            session_id="sdk-session-sop",
            final_answer="{}",
            steps=[],
            success=True,
            final_answer_text_policy=pol or "full",
        )

    monkeypatch.setattr(routes, "execute_agent_message", fake_execute_agent_message)

    client = TestClient(routes.app)
    response = client.post(
        "/v1/agent/messages",
        data={
            "prompt": "x",
            "structured_output_profile": "jmi_intake_call_checkout",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("structured_valid") is False
    assert body.get("structured_error") is not None
    assert "final_answer" in body


def test_messages_structured_profile_success_returns_slim_response(monkeypatch, tmp_path):
    """structured_output_profile 启用且校验成功 → 仅返回 session_id + structured_output。"""
    import json as _json

    golden_path = (
        Path(__file__).resolve().parent
        / "jmi-intake-call-checkout"
        / "cases"
        / "fnol-0001-6805-03399"
        / "output"
        / "intake-checkout-result.json"
    )
    golden_text = golden_path.read_text(encoding="utf-8")

    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    async def fake_execute_agent_message(*, config, prompt, cwd, session_id=None, **kwargs):
        return ExecutionResult(
            session_id="sdk-session-slim",
            final_answer=golden_text,
            steps=[{"type": "x", "content": "should not appear"}],
            success=True,
            final_answer_text_policy="last_assistant_turn",
        )

    monkeypatch.setattr(routes, "execute_agent_message", fake_execute_agent_message)

    client = TestClient(routes.app)
    response = client.post(
        "/v1/agent/messages",
        data={
            "prompt": "x",
            "structured_output_profile": "jmi_intake_call_checkout",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"session_id", "structured_output"}
    assert body["session_id"] == "sdk-session-slim"
    assert body["structured_output"]["checklist"] == "intake_call_checkout"
    assert len(body["structured_output"]["items"]) == 4


def test_messages_structured_profile_fresh_claim_success_returns_slim_response(monkeypatch, tmp_path):
    """structured_output_profile=jmi_fresh_claim_doc_check 且校验成功 → 精简响应。"""
    golden_path = (
        Path(__file__).resolve().parent
        / "jmi-fresh-claim-doc-check"
        / "cases"
        / "fnol-0001-6805-03399"
        / "output"
        / "fresh-claim-doc-check-result.json"
    )
    golden_text = golden_path.read_text(encoding="utf-8")

    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    async def fake_execute_agent_message(*, config, prompt, cwd, session_id=None, **kwargs):
        return ExecutionResult(
            session_id="sdk-session-fresh",
            final_answer=golden_text,
            steps=[{"type": "x", "content": "should not appear"}],
            success=True,
            final_answer_text_policy="last_assistant_turn",
        )

    monkeypatch.setattr(routes, "execute_agent_message", fake_execute_agent_message)

    client = TestClient(routes.app)
    response = client.post(
        "/v1/agent/messages",
        data={
            "prompt": "x",
            "structured_output_profile": "jmi_fresh_claim_doc_check",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"session_id", "structured_output"}
    assert body["session_id"] == "sdk-session-fresh"
    assert body["structured_output"]["checklist"] == "fresh_claim_documents"
    assert len(body["structured_output"]["documents"]) == 7


def test_messages_invalid_final_answer_text_policy_returns_400(tmp_path):
    routes.file_store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )
    client = TestClient(routes.app)
    response = client.post(
        "/v1/agent/messages",
        data={
            "prompt": "x",
            "final_answer_text_policy": "invalid",
        },
    )
    assert response.status_code == 400
