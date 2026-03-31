"""
文档验证测试 - 验证文档中描述的结构与实际代码一致
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestProjectStructure:
    """测试项目结构是否与 CLAUDE.md 描述一致"""

    def test_agents_directory_structure(self):
        """验证 agents 目录结构"""
        # 应该存在的文件
        assert Path("app/agents/client.py").exists(), "client.py 应该存在"
        assert Path("app/agents/__init__.py").exists(), "__init__.py 应该存在"

        # 不应该存在的文件（旧文档中错误描述的）
        assert not Path("app/agents/executor.py").exists(), "executor.py 不应该存在"
        assert not Path("app/agents/options.py").exists(), "options.py 不应该存在"
        assert not Path("app/agents/schema_registry.py").exists(), "schema_registry.py 不应该存在"
        assert not Path("app/agents/tools").is_dir(), "tools/ 目录不应该存在"

    def test_api_directory_structure(self):
        """验证 API 目录结构"""
        # 应该是平级组织，而非嵌套的 v1/endpoints
        assert Path("app/api/chat.py").exists(), "chat.py 应该存在"
        assert Path("app/api/upload.py").exists(), "upload.py 应该存在"
        assert Path("app/api/health.py").exists(), "health.py 应该存在"
        assert Path("app/api/__init__.py").exists(), "__init__.py 应该存在"

        # 不应该存在嵌套目录
        assert not Path("app/api/v1/endpoints").is_dir(), "不应该有 v1/endpoints/ 嵌套目录"

    def test_models_directory_structure(self):
        """验证模型目录结构"""
        # 应该是 models，而非 schemas
        assert Path("app/models").is_dir(), "models/ 目录应该存在"
        assert Path("app/models/chat.py").exists(), "chat.py 应该存在"
        assert Path("app/models/session.py").exists(), "session.py 应该存在"
        assert Path("app/models/upload.py").exists(), "upload.py 应该存在"

        # 不应该存在 schemas 目录
        assert not Path("app/schemas").is_dir(), "schemas/ 目录不应该存在"

    def test_core_directory_structure(self):
        """验证核心目录结构"""
        assert Path("app/core/config.py").exists(), "config.py 应该存在"
        assert Path("app/core/permissions.py").exists(), "permissions.py 应该存在"
        assert Path("app/core/session_manager.py").exists(), "session_manager.py 应该存在"

    def test_services_directory_structure(self):
        """验证服务层目录结构"""
        assert Path("app/services/skill_loader.py").exists()
        assert Path("app/services/upload_service.py").exists()
        assert Path("app/services/workspace_service.py").exists()
        assert Path("app/services/app_registry.py").exists()

    def test_configuration_files(self):
        """验证配置文件"""
        assert Path("conf/config.yaml").exists(), "config.yaml 应该存在"
        assert Path("pyproject.toml").exists(), "pyproject.toml 应该存在"

    def test_skills_directory(self):
        """验证技能目录"""
        assert Path(".claude/skills").is_dir(), "skills/ 目录应该存在"

        # 验证文档中提到的 5 个技能
        expected_skills = [
            "document-ocr-ai",
            "jmi-fresh-claim-doc-check",
            "jmi-intake-call-checkout",
            "image-by-intent",
            "local-rag",
        ]

        for skill in expected_skills:
            skill_path = Path(f".claude/skills/{skill}")
            assert skill_path.is_dir(), f"技能 {skill} 目录应该存在"

    def test_rules_directory(self):
        """验证开发规范目录"""
        assert Path(".claude/rules").is_dir(), "rules/ 目录应该存在"

        expected_rules = [
            "claude_agent_sdk.md",
            "fastapi_best_practices.md",
            "code_style_and_security.md",
            "prompt_engineering.md",
        ]

        for rule in expected_rules:
            assert Path(f".claude/rules/{rule}").exists(), f"规则文件 {rule} 应该存在"

    def test_documentation_files(self):
        """验证文档文件"""
        assert Path("CLAUDE.md").exists(), "CLAUDE.md 应该存在"
        assert Path("docs/QUICK_START.md").exists(), "QUICK_START.md 应该存在"
        assert Path("docs/FILE_UPLOAD_DESIGN.md").exists()
        assert Path("docs/FILE_UPLOAD_IMPLEMENTATION.md").exists()
        assert Path("docs/VERTEX_AI_SETUP.md").exists()


class TestImports:
    """测试关键模块可以正确导入"""

    def test_import_main_app(self):
        """测试可以导入主应用"""
        from app.main import app, create_app

        assert app is not None
        assert create_app is not None

    def test_import_agents_client(self):
        """测试可以导入 agent 客户端"""
        from app.agents.client import stream_chat

        assert stream_chat is not None

    def test_import_config(self):
        """测试可以导入配置"""
        from app.core.config import Settings, get_settings

        settings = get_settings()
        assert isinstance(settings.app.name, str)
        assert settings.app.version == "0.1.0"

    def test_import_models(self):
        """测试可以导入模型"""
        from app.models.chat import ChatRequest
        from app.models.session import SessionMapping, PermissionProfile
        from app.models.upload import UploadResponse

        assert ChatRequest is not None
        assert SessionMapping is not None
        assert PermissionProfile is not None
        assert UploadResponse is not None

    def test_import_services(self):
        """测试可以导入服务"""
        from app.services.skill_loader import SkillLoader
        from app.services.upload_service import UploadService
        from app.services.workspace_service import WorkspaceService

        assert SkillLoader is not None
        assert UploadService is not None
        assert WorkspaceService is not None


class TestConfiguration:
    """测试配置加载"""

    def test_config_yaml_is_valid(self):
        """测试 config.yaml 语法正确"""
        import yaml

        with open("conf/config.yaml") as f:
            config = yaml.safe_load(f)

        assert config is not None
        assert "app" in config
        assert "claude" in config
        assert "session" in config
        assert "upload" in config

    def test_config_structure(self):
        """测试配置结构符合文档描述"""
        from app.core.config import get_settings

        settings = get_settings()

        # 验证 app 配置
        assert settings.app.name == "Claude Agent Platform"
        assert settings.app.version == "0.1.0"

        # 验证 claude 配置
        assert settings.claude.model == "claude-sonnet-4-5"
        assert settings.claude.permission_mode in ["default", "strict", "permissive"]

        # 验证 session 配置
        assert settings.session.storage_dir == "runtime/sessions"

        # 验证 upload 配置
        assert settings.upload.temp_dir == "uploads/temp"
        assert settings.upload.max_file_size_mb == 20

    def test_default_allowed_tools(self):
        """测试默认工具列表"""
        from app.core.config import get_settings

        settings = get_settings()
        expected_tools = ["Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "LS"]

        for tool in expected_tools:
            assert tool in settings.claude.default_allowed_tools


class TestSkills:
    """测试技能加载"""

    def test_skill_loader_can_load_skills(self):
        """测试可以加载技能"""
        from app.services.skill_loader import SkillLoader

        loader = SkillLoader()

        # 测试加载一个已知的技能
        skill_content = loader.load("document-ocr-ai")
        assert isinstance(skill_content, str)
        assert len(skill_content) > 0

    def test_skill_loader_raises_for_missing_skill(self):
        """测试加载不存在的技能会抛出异常"""
        from fastapi import HTTPException

        from app.services.skill_loader import SkillLoader

        loader = SkillLoader()

        with pytest.raises(HTTPException) as exc_info:
            loader.load("non-existent-skill")

        assert exc_info.value.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
