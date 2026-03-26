from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from typing import Literal

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "conf" / "config.yaml"


def _is_truthy_env(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _use_managed_provider(env: dict[str, str]) -> bool:
    # Claude Code 的托管 provider（Vertex/Bedrock/Foundry）开启时，不应强制注入本地代理 URL/API Key
    keys = (
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
    )
    return any(_is_truthy_env(os.environ.get(key) or env.get(key)) for key in keys)


class AppSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True


class SdkSettings(BaseModel):
    base_url: str = "http://localhost:4000"
    api_key: str = "sk-1234"
    model: str = "claude-sonnet-4-5"
    max_turns: int = 25
    continue_conversation: bool = True
    permission_mode: str | None = "acceptEdits"
    setting_sources: list[str] = Field(default_factory=lambda: ["project", "user"])
    allowed_tools: list[str] = Field(
        default_factory=lambda: [
            "Read",
            "Write",
            "Edit",
            "MultiEdit",
            "Bash",
            "Skill",
            "Glob",
            "Grep",
            "WebSearch",
        ]
    )
    # 传入 Claude Code 子进程的环境变量（会覆盖同名父进程变量），例如 ANTHROPIC_API_KEY
    env: dict[str, str] = Field(default_factory=dict)
    # 非空则使用该路径启动 CLI，否则使用 SDK 内置查找逻辑（which claude 等）
    cli_path: str | None = None


class AgentSettings(BaseModel):
    system_prompt: str = (
        "你是一个专业、严谨的工程师 Agent。"
        "优先使用 Skill 指导流程，结合用户 prompt 给出有用建议。"
    )


class StorageSettings(BaseModel):
    upload_root: str = "uploads"
    pending_dir_name: str = ".pending"
    cleanup_on_shutdown: bool = False


class LangfuseSettings(BaseModel):
    enabled: bool = False
    public_key: str | None = None
    secret_key: str | None = None
    host: str = "https://cloud.langfuse.com"
    # 从环境变量读取配置
    def get_public_key(self) -> str | None:
        return os.environ.get("LANGFUSE_PUBLIC_KEY") or self.public_key

    def get_secret_key(self) -> str | None:
        return os.environ.get("LANGFUSE_SECRET_KEY") or self.secret_key

    def get_host(self) -> str:
        return os.environ.get("LANGFUSE_HOST") or self.host


class ApiSettings(BaseModel):
    return_steps: bool = True
    max_step_preview_chars: int = 800
    # full: 拼接每一轮助手文本；last_assistant_turn: 仅保留最后一轮（避免中间分析拼进 final_answer）
    final_answer_text_policy: Literal["full", "last_assistant_turn"] = "full"
    file_prompt_template: str = (
        "用户上传了以下文件：{files}\n\n{prompt}\n\n"
        "请先使用 Read 工具读取这些文件，然后按要求回复。"
    )


class AppConfig(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    sdk: SdkSettings = Field(default_factory=SdkSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)


@lru_cache(maxsize=1)
def get_config(config_path: str | Path | None = None) -> AppConfig:
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)


def configure_sdk_environment(config: AppConfig | None = None) -> AppConfig:
    config = config or get_config()
    if _use_managed_provider(config.sdk.env):
        return config

    # Claude Code CLI 主要读取 ANTHROPIC_* 变量，保留 OPENAI_* 兼容旧配置。
    if "ANTHROPIC_BASE_URL" not in os.environ:
        os.environ["ANTHROPIC_BASE_URL"] = config.sdk.base_url
    if "ANTHROPIC_API_KEY" not in os.environ:
        os.environ["ANTHROPIC_API_KEY"] = config.sdk.api_key
    if "OPENAI_BASE_URL" not in os.environ:
        os.environ["OPENAI_BASE_URL"] = config.sdk.base_url
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = config.sdk.api_key
    return config
