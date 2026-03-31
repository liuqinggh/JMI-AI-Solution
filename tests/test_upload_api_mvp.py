from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.main import create_app


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_client(tmp_path: Path, monkeypatch) -> TestClient:
    write_yaml(
        tmp_path / "conf" / "config.yaml",
        """
upload:
  temp_dir: uploads/temp
  max_file_size_mb: 1
  allowed_extensions:
    - .txt
    - .md
apps:
  default:
    skill_name: demo
    cwd: .
""".strip(),
    )
    monkeypatch.chdir(tmp_path)
    reset_settings_cache()
    return TestClient(create_app())


def test_upload_returns_file_metadata(tmp_path, monkeypatch):
    client = create_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/upload",
        files=[("files", ("note.txt", b"hello world", "text/plain"))],
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["files"]) == 1
    assert payload["files"][0]["file_id"]
    assert payload["files"][0]["original_name"] == "note.txt"


def test_upload_rejects_disallowed_extension(tmp_path, monkeypatch):
    client = create_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/upload",
        files=[("files", ("bad.pdf", b"fake", "application/pdf"))],
    )

    assert response.status_code == 400
    assert "extension" in response.json()["detail"].lower()


def test_upload_rejects_large_file(tmp_path, monkeypatch):
    client = create_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/upload",
        files=[("files", ("big.txt", b"x" * (1024 * 1024 + 1), "text/plain"))],
    )

    assert response.status_code == 413
    assert "size" in response.json()["detail"].lower()
