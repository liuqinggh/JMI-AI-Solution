"""
API 端点集成测试
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """测试健康检查端点"""

    def test_health_check(self):
        """测试 GET /api/v1/health"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "Claude Agent Platform"
        assert data["version"] == "0.1.0"


class TestUploadEndpoint:
    """测试文件上传端点"""

    def test_upload_single_file(self):
        """测试上传单个文件"""
        files = {"files": ("test.txt", b"test content", "text/plain")}
        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()

        assert "files" in data
        assert len(data["files"]) == 1
        assert data["files"][0]["original_name"] == "test.txt"
        assert "file_id" in data["files"][0]
        assert "saved_path" in data["files"][0]
        assert data["files"][0]["size"] > 0

    def test_upload_multiple_files(self):
        """测试上传多个文件"""
        files = [
            ("files", ("test1.txt", b"content 1", "text/plain")),
            ("files", ("test2.json", b'{"key": "value"}', "application/json")),
        ]
        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()

        assert "files" in data
        assert len(data["files"]) == 2

    def test_upload_no_files(self):
        """测试不上传文件时应该返回错误"""
        response = client.post("/api/v1/upload")
        assert response.status_code == 422  # Validation error


class TestChatEndpoint:
    """测试聊天端点"""

    def test_chat_requires_message(self):
        """测试必须提供 message 字段"""
        response = client.post(
            "/api/v1/chat",
            json={
                "business_session_id": "test-session",
                "skill_name": "document-ocr-ai",
            },
        )
        assert response.status_code == 422

    def test_chat_requires_business_session_id(self):
        """测试必须提供 business_session_id"""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Hello",
                "skill_name": "document-ocr-ai",
            },
        )
        assert response.status_code == 422

    def test_chat_requires_skill_or_app_id(self):
        """测试必须提供 skill_name 或 app_id"""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Hello",
                "business_session_id": "test-session",
            },
        )
        assert response.status_code == 422

    def test_chat_with_invalid_skill_name(self):
        """测试使用不存在的技能名称"""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Hello",
                "business_session_id": "test-session",
                "skill_name": "non-existent-skill",
            },
        )
        assert response.status_code == 404

    def test_chat_session_id_validation(self):
        """测试会话 ID 验证"""
        # 空字符串应该被拒绝
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Hello",
                "business_session_id": "",
                "skill_name": "document-ocr-ai",
            },
        )
        assert response.status_code == 422


class TestAPIRouting:
    """测试 API 路由配置"""

    def test_api_v1_prefix_exists(self):
        """测试所有端点都有 /api/v1 前缀"""
        # 健康检查
        assert client.get("/api/v1/health").status_code == 200

        # 文件上传
        files = {"files": ("test.txt", b"test", "text/plain")}
        assert client.post("/api/v1/upload", files=files).status_code == 200

        # 聊天端点（即使参数错误，也应该返回 422 而非 404）
        response = client.post("/api/v1/chat", json={})
        assert response.status_code == 422

    def test_old_endpoints_not_exist(self):
        """测试旧的端点不应该存在"""
        # 旧的根路径健康检查
        response = client.get("/")
        assert response.status_code == 404

        # 旧的配置端点
        response = client.get("/config")
        assert response.status_code == 404

        # 旧的 v1/agent/messages 端点
        response = client.post("/v1/agent/messages")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
