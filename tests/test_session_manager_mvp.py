from __future__ import annotations

from app.core.config import AppDefinition, Settings
from app.core.permissions import resolve_permissions
from app.core.session_manager import SessionManager
from app.services.app_registry import AppRegistry
from app.services.skill_loader import SkillLoader


def test_session_manager_persists_mapping(tmp_path):
    manager = SessionManager(tmp_path / "runtime" / "sessions")

    manager.save_mapping(
        business_session_id="biz-1",
        sdk_session_id="sdk-1",
        app_id="default",
        skill_name="fastapi-dev",
    )

    record = manager.get_mapping("biz-1")

    assert record is not None
    assert record.sdk_session_id == "sdk-1"
    assert record.app_id == "default"
    assert record.skill_name == "fastapi-dev"


def test_session_manager_rejects_path_traversal_session_id(tmp_path):
    manager = SessionManager(tmp_path / "runtime" / "sessions")

    try:
        manager.save_mapping(
            business_session_id="../escape",
            sdk_session_id="sdk-1",
            app_id="default",
            skill_name="fastapi-dev",
        )
    except ValueError as exc:
        assert "business_session_id" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid business_session_id")


def test_app_registry_returns_configured_app():
    settings = Settings(
        apps={
            "default": AppDefinition(
                skill_name="fastapi-dev",
                cwd=".",
                permission_mode="default",
                allowed_tools=["Read", "Glob"],
            )
        }
    )

    registry = AppRegistry(settings)
    app_config = registry.get_app("default")

    assert app_config.app_id == "default"
    assert app_config.skill_name == "fastapi-dev"
    assert app_config.allowed_tools == ["Read", "Glob"]


def test_skill_loader_reads_skill_markdown(tmp_path, monkeypatch):
    skill_file = tmp_path / ".claude" / "skills" / "demo" / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text("# Demo Skill\n\nhello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    content = SkillLoader().load("demo")

    assert content == "# Demo Skill\n\nhello"


def test_resolve_permissions_prefers_app_over_platform_defaults():
    settings = Settings()
    settings.claude.permission_mode = "default"
    settings.claude.default_allowed_tools = ["Read", "Write"]

    resolved = resolve_permissions(
        settings=settings,
        app_definition=AppDefinition(
            skill_name="demo",
            permission_mode="read_only",
            allowed_tools=["Read"],
        ),
    )

    assert resolved.permission_mode == "read_only"
    assert resolved.allowed_tools == ["Read"]
