from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.core.session_manager import SessionManager
from app.main import create_app


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_client(tmp_path: Path, monkeypatch) -> TestClient:
    write_yaml(
        tmp_path / "conf" / "config.yaml",
        """
claude:
  model: test-model
session:
  storage_dir: runtime/sessions
upload:
  temp_dir: uploads/temp
  max_file_size_mb: 1
  allowed_extensions:
    - .txt
apps:
  default:
    skill_name: demo
    cwd: .
    permission_mode: default
    allowed_tools:
      - Read
      - Write
""".strip(),
    )
    skill_file = tmp_path / ".claude" / "skills" / "demo" / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text("# Demo Skill", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    reset_settings_cache()
    return TestClient(create_app())


def test_chat_first_turn_stores_sdk_session_id(tmp_path, monkeypatch):
    client = create_client(tmp_path, monkeypatch)

    async def fake_stream_chat(**kwargs):
        yield {"event": "session_started", "sdk_session_id": "sdk-first"}
        yield {"event": "assistant_delta", "text": "hello"}
        yield {"event": "final", "final_answer": "done"}

    monkeypatch.setattr("app.agents.client.stream_chat", fake_stream_chat)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "hello",
            "business_session_id": "biz-1",
            "app_id": "default",
            "file_ids": [],
        },
    )

    assert response.status_code == 200
    assert "event: final" in response.text
    record = SessionManager(tmp_path / "runtime" / "sessions").get_mapping("biz-1")
    assert record is not None
    assert record.sdk_session_id == "sdk-first"


def test_chat_resumes_existing_sdk_session(tmp_path, monkeypatch):
    client = create_client(tmp_path, monkeypatch)
    SessionManager(tmp_path / "runtime" / "sessions").save_mapping(
        business_session_id="biz-2",
        sdk_session_id="sdk-existing",
        app_id="default",
        skill_name="demo",
    )
    captured: dict[str, str | None] = {}

    async def fake_stream_chat(**kwargs):
        captured["resume_session_id"] = kwargs["resume_session_id"]
        yield {"event": "session_started", "sdk_session_id": "sdk-existing"}
        yield {"event": "final", "final_answer": "done"}

    monkeypatch.setattr("app.agents.client.stream_chat", fake_stream_chat)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "resume me",
            "business_session_id": "biz-2",
            "app_id": "default",
            "file_ids": [],
        },
    )

    assert response.status_code == 200
    assert captured["resume_session_id"] == "sdk-existing"


def test_chat_copies_uploaded_files_into_workspace(tmp_path, monkeypatch):
    client = create_client(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    upload_response = client.post(
        "/api/v1/upload",
        files=[("files", ("note.txt", b"hello upload", "text/plain"))],
    )
    file_id = upload_response.json()["files"][0]["file_id"]

    async def fake_stream_chat(**kwargs):
        captured["message"] = kwargs["message"]
        captured["cwd"] = kwargs["cwd"]
        yield {"event": "session_started", "sdk_session_id": "sdk-file"}
        yield {"event": "final", "final_answer": "done"}

    monkeypatch.setattr("app.agents.client.stream_chat", fake_stream_chat)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "read the file",
            "business_session_id": "biz-file",
            "app_id": "default",
            "file_ids": [file_id],
        },
    )

    assert response.status_code == 200
    assert "note.txt" in str(captured["message"])
    workspace_upload = tmp_path / ".agent-platform" / "biz-file" / "uploads" / "note.txt"
    assert workspace_upload.exists()
