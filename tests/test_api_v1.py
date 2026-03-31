"""Tests for API v1 endpoints with new architecture."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.v1.deps import init_dependencies
from app.config import AppConfig, LangfuseSettings, StorageSettings
from app.schemas import ExecutionResult
from app.storage.content_store import ContentAddressedStore
from app.tracing.langfuse_tracer import LangfuseTracer


def create_test_app(tmp_path: Path) -> TestClient:
    """Create test FastAPI app with temporary storage."""
    storage_settings = StorageSettings(
        upload_root=str(tmp_path / "uploads"),
        pending_dir_name=".pending",
    )
    file_store = ContentAddressedStore(storage_settings)

    # Disable Langfuse for tests
    langfuse_settings = LangfuseSettings(enabled=False)
    tracer = LangfuseTracer(langfuse_settings)

    config = AppConfig(storage=storage_settings, langfuse=langfuse_settings)

    init_dependencies(config, file_store, tracer)

    app = create_app(config)
    return TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "agent-sdk-api-service"


def test_config_endpoint():
    """Test config info endpoint."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/config")

    assert response.status_code == 200
    data = response.json()
    assert "model" in data
    assert "provider" in data


def test_test_page_is_available():
    """Test that test page HTML is served."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/test")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_messages_endpoint_basic(tmp_path):
    """Test basic message endpoint with prompt only."""
    client = create_test_app(tmp_path)

    with patch("app.api.v1.endpoints.agents.execute_agent_message", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ExecutionResult(
            session_id="test-session-1",
            final_answer="test response",
            steps=[],
            success=True,
        )

        response = client.post(
            "/api/v1/agent/messages",
            data={"prompt": "hello"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-1"
        assert data["final_answer"] == "test response"
        assert mock_exec.called


def test_messages_endpoint_with_files(tmp_path):
    """Test message endpoint with file uploads."""
    client = create_test_app(tmp_path)

    with patch("app.agents.executor.execute_agent_message", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ExecutionResult(
            session_id="test-session-2",
            final_answer="file processed",
            steps=[],
            success=True,
        )

        response = client.post(
            "/api/v1/agent/messages",
            data={"prompt": "analyze this file"},
            files={"files": ("test.txt", b"test content", "text/plain")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-2"


def test_messages_endpoint_structured_output(tmp_path):
    """Test structured output profile."""
    client = create_test_app(tmp_path)

    with patch("app.agents.executor.execute_agent_message", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ExecutionResult(
            session_id="test-session-3",
            final_answer="result",
            steps=[],
            success=True,
            structured_output={"result": "test"},
        )

        response = client.post(
            "/api/v1/agent/messages",
            data={
                "prompt": "test",
                "structured_output_profile": "jmi-intake-checkout",
            },
        )

        # Should succeed even with invalid profile (handled in endpoint)
        assert response.status_code in (200, 400)


def test_messages_endpoint_invalid_policy(tmp_path):
    """Test invalid final_answer_text_policy."""
    client = create_test_app(tmp_path)

    response = client.post(
        "/api/v1/agent/messages",
        data={
            "prompt": "test",
            "final_answer_text_policy": "invalid_policy",
        },
    )

    assert response.status_code == 400
    assert "final_answer_text_policy" in response.json()["detail"]
