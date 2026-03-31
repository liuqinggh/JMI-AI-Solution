# 测试指南

本文档提供完整的测试指南和测试案例。

## 📋 目录

- [测试概览](#测试概览)
- [快速开始](#快速开始)
- [测试案例](#测试案例)
- [测试结果](#测试结果)
- [故障排查](#故障排查)

---

## 测试概览

### 测试类型

| 类型 | 文件 | 测试数 | 说明 |
|-----|------|--------|------|
| 文档验证 | `tests/test_documentation_validation.py` | 19 | 验证项目结构与文档一致性 |
| API 集成 | `tests/integration/test_api_endpoints.py` | 11 | 验证 API 端点功能 |

### 最新测试结果

- ✅ **文档验证测试**: 19/19 通过（100%）
- ✅ **API 集成测试**: 11/11 通过（100%）
- ✅ **总计**: 30/30 通过（100%）

详细结果见 [TEST_RESULTS.md](./TEST_RESULTS.md)

---

## 快速开始

### 1. 一键运行所有测试

```bash
./scripts/quick_test.sh
```

### 2. 分别运行测试

```bash
# 文档验证测试
.venv/bin/python -m pytest tests/test_documentation_validation.py -v

# API 集成测试
.venv/bin/python -m pytest tests/integration/test_api_endpoints.py -v
```

---

## 测试案例

### 案例 1: 项目结构验证

**目的**: 验证实际代码结构与 CLAUDE.md 文档描述一致

**测试方法**:
```bash
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestProjectStructure -v
```

**验证项目**（9 个）:
- ✅ Agent 目录结构
- ✅ API 目录结构（平级组织）
- ✅ 模型目录（models vs schemas）
- ✅ 核心模块目录
- ✅ 服务层目录
- ✅ 配置文件
- ✅ 技能目录（5 个技能）
- ✅ 规则文件（4 个规则）
- ✅ 文档文件

**预期结果**: 所有文件路径与文档描述完全一致

---

### 案例 2: 模块导入验证

**目的**: 验证所有关键模块可以正确导入

**测试方法**:
```bash
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestImports -v
```

**验证模块**（5 个）:
- ✅ `app.main` - 主应用
- ✅ `app.agents.client` - Agent 客户端
- ✅ `app.core.config` - 配置管理
- ✅ `app.models.*` - 数据模型
- ✅ `app.services.*` - 服务层

**预期结果**: 所有模块导入成功，无 ModuleNotFoundError

---

### 案例 3: 配置验证

**目的**: 验证配置文件结构和内容

**测试方法**:
```bash
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestConfiguration -v
```

**验证内容**（3 个）:
- ✅ YAML 语法正确
- ✅ 配置结构符合文档
  - app.name = "Claude Agent Platform"
  - claude.model = "claude-sonnet-4-5"
  - session.storage_dir = "runtime/sessions"
  - upload.max_file_size_mb = 20
- ✅ 默认工具列表正确

**预期结果**: 配置加载成功，值与文档描述一致

---

### 案例 4: 技能加载验证

**目的**: 验证技能加载机制

**测试方法**:
```bash
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestSkills -v
```

**验证功能**（2 个）:
- ✅ 加载存在的技能返回内容
- ✅ 加载不存在的技能抛出 404

**测试代码**:
```python
from app.services.skill_loader import SkillLoader

loader = SkillLoader()

# 加载存在的技能
content = loader.load("document-ocr-ai")
assert len(content) > 0

# 加载不存在的技能
with pytest.raises(HTTPException):
    loader.load("non-existent-skill")
```

---

### 案例 5: 健康检查端点

**目的**: 验证健康检查端点功能

**测试方法**:
```bash
.venv/bin/python -m pytest tests/integration/test_api_endpoints.py::TestHealthEndpoint -v
```

**请求**:
```bash
curl http://localhost:8000/api/v1/health
```

**预期响应**:
```json
{
  "status": "healthy",
  "service": "Claude Agent Platform",
  "version": "0.1.0"
}
```

**验证点**:
- ✅ 状态码 200
- ✅ 返回 status 字段
- ✅ 返回 service 字段
- ✅ 返回 version 字段

---

### 案例 6: 文件上传功能

**目的**: 验证文件上传端点

**测试方法**:
```bash
.venv/bin/python -m pytest tests/integration/test_api_endpoints.py::TestUploadEndpoint -v
```

**场景 A: 单文件上传**

```bash
echo "test content" > test.txt
curl -X POST http://localhost:8000/api/v1/upload -F "files=@test.txt"
```

**预期响应**:
```json
{
  "files": [
    {
      "file_id": "abc123...",
      "original_name": "test.txt",
      "saved_path": "uploads/temp/...",
      "size": 12,
      "content_type": "text/plain"
    }
  ]
}
```

**场景 B: 多文件上传**

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "files=@test1.txt" \
  -F "files=@test2.json"
```

**场景 C: 无文件上传（错误处理）**

```bash
curl -X POST http://localhost:8000/api/v1/upload
```

**预期**: 422 验证错误

---

### 案例 7: 聊天端点验证

**目的**: 验证聊天端点的输入验证

**测试方法**:
```bash
.venv/bin/python -m pytest tests/integration/test_api_endpoints.py::TestChatEndpoint -v
```

**场景 A: 缺少必需字段**

```bash
# 缺少 message
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"business_session_id": "test", "skill_name": "document-ocr-ai"}'
```

**预期**: 422 验证错误

**场景 B: 无效的技能名称**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "business_session_id": "test",
    "skill_name": "non-existent-skill"
  }'
```

**预期**: 404 技能未找到

**场景 C: 会话 ID 验证**

```bash
# 空字符串
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "business_session_id": "",
    "skill_name": "document-ocr-ai"
  }'
```

**预期**: 422 验证错误

---

### 案例 8: API 路由验证

**目的**: 验证所有端点使用正确的路由前缀

**测试方法**:
```bash
.venv/bin/python -m pytest tests/integration/test_api_endpoints.py::TestAPIRouting -v
```

**验证点**:
- ✅ 所有端点都有 `/api/v1` 前缀
- ✅ 旧端点不存在：
  - `GET /` → 404
  - `GET /config` → 404
  - `POST /v1/agent/messages` → 404

**正确的端点**:
- ✅ `GET /api/v1/health`
- ✅ `POST /api/v1/upload`
- ✅ `POST /api/v1/chat`

---

## 测试结果

### 执行时间

- 文档验证测试: ~0.6 秒
- API 集成测试: ~0.6 秒
- **总计**: ~1.2 秒

### 覆盖的模块

- ✅ `app/main.py`
- ✅ `app/agents/client.py`
- ✅ `app/api/chat.py`
- ✅ `app/api/upload.py`
- ✅ `app/api/health.py`
- ✅ `app/core/config.py`
- ✅ `app/models/*`
- ✅ `app/services/*`

### 测试报告

完整测试报告见 [TEST_RESULTS.md](./TEST_RESULTS.md)

---

## 故障排查

### 问题 1: ModuleNotFoundError: No module named 'claude_agent_sdk'

**原因**: 使用了系统 Python 而非虚拟环境

**解决方案**:
```bash
# 使用虚拟环境中的 Python
.venv/bin/python -m pytest tests/

# 不要使用
pytest tests/  # 可能使用系统 Python
```

### 问题 2: 配置加载失败

**原因**: YAML 语法错误

**解决方案**:
```bash
# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('conf/config.yaml'))"

# 检查配置
python -c "from app.core.config import get_settings; print(get_settings())"
```

### 问题 3: 技能加载失败

**原因**: 技能文件不存在

**解决方案**:
```bash
# 检查技能目录
ls -la .claude/skills/

# 验证技能文件
ls .claude/skills/document-ocr-ai/SKILL.md
```

### 问题 4: API 测试失败

**原因**: 响应格式变化

**解决方案**:
1. 检查实际的响应结构
2. 更新测试断言以匹配实际响应

```bash
# 查看实际响应
curl -s http://localhost:8000/api/v1/upload \
  -F "files=@test.txt" | jq
```

---

## 高级用法

### 生成覆盖率报告

```bash
.venv/bin/python -m pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

### 运行特定测试

```bash
# 运行特定测试类
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestProjectStructure

# 运行特定测试用例
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestProjectStructure::test_agents_directory_structure

# 使用关键词过滤
.venv/bin/python -m pytest tests/ -k "upload"
```

### 调试模式

```bash
# 显示详细输出
.venv/bin/python -m pytest tests/ -vv

# 显示 print 输出
.venv/bin/python -m pytest tests/ -s

# 在第一个失败时停止
.venv/bin/python -m pytest tests/ -x

# 显示最慢的 10 个测试
.venv/bin/python -m pytest tests/ --durations=10
```

---

## 持续集成

### GitHub Actions 示例

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run tests
        run: |
          .venv/bin/python -m pytest tests/ -v --junit-xml=test-results.xml
      - name: Upload test results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test-results.xml
```

---

## 参考资料

- [pytest 文档](https://docs.pytest.org/)
- [FastAPI 测试](https://fastapi.tiangolo.com/tutorial/testing/)
- [TEST_RESULTS.md](./TEST_RESULTS.md) - 最新测试结果
- [scripts/README.md](./scripts/README.md) - 测试脚本说明

---

**最后更新**: 2026-03-31  
**维护者**: Claude Sonnet 4.5
