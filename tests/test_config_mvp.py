from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings, reset_settings_cache
from app.main import create_app


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_get_settings_loads_default_yaml(tmp_path, monkeypatch):
    write_yaml(
        tmp_path / "conf" / "config.yaml",
        """
app:
  name: Test Platform
  version: 0.2.0
""".strip(),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    reset_settings_cache()

    settings = get_settings()

    assert settings.app.name == "Test Platform"
    assert settings.app.version == "0.2.0"


def test_get_settings_merges_env_specific_yaml(tmp_path, monkeypatch):
    write_yaml(
        tmp_path / "conf" / "config.yaml",
        """
app:
  name: Base Platform
  version: 0.1.0
claude:
  model: base-model
""".strip(),
    )
    write_yaml(
        tmp_path / "conf" / "config.dev.yaml",
        """
app:
  version: 0.3.0-dev
claude:
  model: dev-model
""".strip(),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENV", "dev")
    reset_settings_cache()

    settings = get_settings()

    assert settings.app.name == "Base Platform"
    assert settings.app.version == "0.3.0-dev"
    assert settings.claude.model == "dev-model"


def test_health_endpoint_returns_platform_metadata(tmp_path, monkeypatch):
    write_yaml(
        tmp_path / "conf" / "config.yaml",
        """
app:
  name: Health Platform
  version: 1.0.0
""".strip(),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    reset_settings_cache()

    client = TestClient(create_app())
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "Health Platform",
        "version": "1.0.0",
    }


def test_get_settings_defaults_to_vertex_ai_provider(tmp_path, monkeypatch):
    write_yaml(
        tmp_path / "conf" / "config.yaml",
        """
claude:
  model: claude-sonnet-4-5
  env:
    CLAUDE_CODE_USE_VERTEX: "1"
    GOOGLE_APPLICATION_CREDENTIALS: /tmp/fake-adc.json
    ANTHROPIC_VERTEX_PROJECT_ID: ai-model-487001
    CLOUD_ML_REGION: global
""".strip(),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    reset_settings_cache()

    settings = get_settings()

    assert settings.claude.env["CLAUDE_CODE_USE_VERTEX"] == "1"
    assert settings.claude.env["ANTHROPIC_VERTEX_PROJECT_ID"] == "ai-model-487001"
