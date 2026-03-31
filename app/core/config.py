from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


class AppSettings(BaseModel):
    name: str = "Claude Agent Platform"
    version: str = "0.1.0"
    environment: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000


class ClaudeSettings(BaseModel):
    model: str = "claude-sonnet-4-5"
    permission_mode: str = "default"
    max_turns: int = 12
    setting_sources: list[str] = Field(default_factory=lambda: ["project", "user"])
    cli_path: str | None = None
    default_allowed_tools: list[str] = Field(
        default_factory=lambda: ["Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "LS"]
    )
    mcp_enabled: bool = False
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class SessionSettings(BaseModel):
    storage_dir: str = "runtime/sessions"
    mapping_ttl_seconds: int = 604800


class UploadSettings(BaseModel):
    temp_dir: str = "uploads/temp"
    max_file_size_mb: int = 20
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".txt", ".md", ".json", ".csv", ".pdf"]
    )


class SecuritySettings(BaseModel):
    can_use_tool_hook: bool = True
    require_approval_for_write: bool = True


class LoggingSettings(BaseModel):
    level: str = "INFO"


class AppDefinition(BaseModel):
    skill_name: str
    cwd: str = "."
    permission_mode: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    upload: UploadSettings = Field(default_factory=UploadSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    apps: dict[str, AppDefinition] = Field(default_factory=dict)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _resolve_config_paths() -> tuple[Path, Path | None]:
    root = Path.cwd()
    base_path = root / "conf" / "config.yaml"
    env_name = os.getenv("ENV", "").strip()
    env_path = root / "conf" / f"config.{env_name}.yaml" if env_name else None
    return base_path, env_path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    base_path, env_path = _resolve_config_paths()
    base_data = _load_yaml_file(base_path)
    env_data = _load_yaml_file(env_path) if env_path else {}
    merged = _deep_merge(base_data, env_data)
    settings = Settings.model_validate(merged)
    if os.getenv("ENV"):
        settings.app.environment = os.getenv("ENV", settings.app.environment)
    return settings


def reset_settings_cache() -> None:
    get_settings.cache_clear()
