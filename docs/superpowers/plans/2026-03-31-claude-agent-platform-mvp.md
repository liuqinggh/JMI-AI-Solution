# Claude Agent Platform MVP 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在当前仓库中交付一个保留 `/api/v1` 前缀的 Claude Agent Platform MVP，覆盖配置加载、上传接口、对话接口、Skill/App 解析与 session resume。

**架构：** 使用 FastAPI 作为 API 外壳，Pydantic V2 管理配置与请求响应模型，本地文件系统承载上传存储和 business-session 映射，Claude Agent SDK 调用统一封装到 `app/agents/client.py`，API 只负责协议层与依赖注入。

**技术栈：** Python 3.11+, FastAPI, Pydantic v2, PyYAML, Claude Agent SDK, pytest, httpx

---

## 文件结构

### 新建

- `app/__init__.py`
- `app/main.py`
- `app/api/__init__.py`
- `app/api/chat.py`
- `app/api/health.py`
- `app/api/upload.py`
- `app/agents/__init__.py`
- `app/agents/client.py`
- `app/core/__init__.py`
- `app/core/config.py`
- `app/core/permissions.py`
- `app/core/session_manager.py`
- `app/models/__init__.py`
- `app/models/app.py`
- `app/models/chat.py`
- `app/models/session.py`
- `app/models/upload.py`
- `app/services/__init__.py`
- `app/services/app_registry.py`
- `app/services/skill_loader.py`
- `app/services/upload_service.py`
- `app/services/workspace_service.py`
- `conf/config.yaml`
- `tests/test_config_mvp.py`
- `tests/test_session_manager_mvp.py`
- `tests/test_upload_api_mvp.py`
- `tests/test_chat_api_mvp.py`

### 修改

- `pyproject.toml`

## 任务 1：搭建配置模型与应用入口

**文件：**
- 创建：`app/core/config.py`
- 创建：`app/main.py`
- 创建：`app/api/__init__.py`
- 创建：`app/api/health.py`
- 创建：`app/__init__.py`
- 创建：`app/core/__init__.py`
- 创建：`conf/config.yaml`
- 测试：`tests/test_config_mvp.py`

- [ ] **步骤 1：编写失败的配置测试**

```python
def test_get_settings_loads_default_yaml(tmp_path, monkeypatch):
    config_path = tmp_path / "conf" / "config.yaml"
    config_path.parent.mkdir()
    config_path.write_text("app:\n  name: test-platform\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = get_settings()

    assert settings.app.name == "test-platform"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`uv run pytest tests/test_config_mvp.py -v`
预期：FAIL，报错 `ModuleNotFoundError: No module named 'app'` 或 `get_settings` 不存在。

- [ ] **步骤 3：实现最小配置与应用入口**

```python
class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)
```

要求：
- 支持默认读取 `conf/config.yaml`
- 支持 `ENV` 环境变量覆盖 `conf/config.<env>.yaml`
- `create_app()` 返回 FastAPI 应用
- 暴露 `GET /api/v1/health`

- [ ] **步骤 4：运行配置测试验证通过**

运行：`uv run pytest tests/test_config_mvp.py -v`
预期：PASS

- [ ] **步骤 5：提交任务 1 变更**

运行：
```bash
git add app conf tests/test_config_mvp.py pyproject.toml
git commit -m "feat: add MVP config and health entrypoint (task 1/4)"
```

## 任务 2：实现本地 session mapping 与 App/Skill 解析

**文件：**
- 创建：`app/core/session_manager.py`
- 创建：`app/core/permissions.py`
- 创建：`app/models/app.py`
- 创建：`app/models/session.py`
- 创建：`app/services/app_registry.py`
- 创建：`app/services/skill_loader.py`
- 测试：`tests/test_session_manager_mvp.py`
- 测试：`tests/test_chat_api_mvp.py`

- [ ] **步骤 1：编写 session mapping 失败测试**

```python
def test_session_manager_persists_mapping(tmp_path):
    manager = SessionManager(tmp_path)
    manager.save_mapping("biz-1", "sdk-1", app_id="default", skill_name="fastapi-dev")

    record = manager.get_mapping("biz-1")

    assert record.sdk_session_id == "sdk-1"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`uv run pytest tests/test_session_manager_mvp.py -v`
预期：FAIL，报错 `SessionManager` 未定义。

- [ ] **步骤 3：实现最小 session 与 app/skill 服务**

```python
class SessionMapping(BaseModel):
    business_session_id: str
    sdk_session_id: str
    app_id: str | None = None
    skill_name: str
```

要求：
- session 记录落到 `runtime/sessions/<business_session_id>.json`
- `AppRegistry` 支持从配置按 `app_id` 获取 app
- `SkillLoader` 从 `.claude/skills/<skill_name>/SKILL.md` 读取内容
- `permissions.py` 能返回最终 `allowed_tools` 和 `permission_mode`

- [ ] **步骤 4：运行 session 测试验证通过**

运行：`uv run pytest tests/test_session_manager_mvp.py -v`
预期：PASS

- [ ] **步骤 5：提交任务 2 变更**

运行：
```bash
git add app tests/test_session_manager_mvp.py tests/test_chat_api_mvp.py
git commit -m "feat: add session mapping and app registry (task 2/4)"
```

## 任务 3：实现上传服务与 `/api/v1/upload`

**文件：**
- 创建：`app/models/upload.py`
- 创建：`app/services/upload_service.py`
- 创建：`app/api/upload.py`
- 测试：`tests/test_upload_api_mvp.py`

- [ ] **步骤 1：编写上传接口失败测试**

```python
def test_upload_returns_file_metadata(client):
    response = client.post(
        "/api/v1/upload",
        files={"files": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["files"][0]["file_id"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`uv run pytest tests/test_upload_api_mvp.py -v`
预期：FAIL，报错路由不存在或响应结构不匹配。

- [ ] **步骤 3：实现最小上传服务**

```python
class UploadService:
    async def save_files(self, files: list[UploadFile]) -> list[StoredUpload]:
        ...
```

要求：
- 校验扩展名白名单
- 校验大小上限
- 安全化文件名
- 落盘到 `uploads/temp`
- 返回 `file_id`、`saved_path`、`original_name`、`size`、`content_type`

- [ ] **步骤 4：运行上传测试验证通过**

运行：`uv run pytest tests/test_upload_api_mvp.py -v`
预期：PASS

- [ ] **步骤 5：提交任务 3 变更**

运行：
```bash
git add app tests/test_upload_api_mvp.py
git commit -m "feat: add upload API for platform MVP (task 3/4)"
```

## 任务 4：实现 Claude SDK 客户端、`/api/v1/chat` 与文件注入

**文件：**
- 创建：`app/models/chat.py`
- 创建：`app/services/workspace_service.py`
- 创建：`app/agents/client.py`
- 创建：`app/api/chat.py`
- 修改：`app/main.py`
- 测试：`tests/test_chat_api_mvp.py`

- [ ] **步骤 1：编写 chat 接口失败测试**

```python
def test_chat_first_turn_stores_sdk_session_id(client, monkeypatch):
    monkeypatch.setattr("app.agents.client.stream_chat", fake_stream)

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
    assert "final" in response.text
```

- [ ] **步骤 2：运行测试验证失败**

运行：`uv run pytest tests/test_chat_api_mvp.py -v`
预期：FAIL，报错 `/api/v1/chat` 不存在或 `stream_chat` 未实现。

- [ ] **步骤 3：实现最小 chat 路径**

```python
async def stream_chat(request: ChatRequest, context: ChatContext) -> AsyncIterator[dict[str, Any]]:
    ...
```

要求：
- 支持 `app_id` 或 `skill_name`
- 首轮不传 `resume`，后续自动从 session mapping 取 `sdk_session_id`
- 引用 `file_ids` 时，将上传文件复制到工作目录的本轮上传目录
- 在 prompt 中明确列出可读取文件路径
- SSE 至少输出 `session_started`、`assistant_delta`、`final`
- 最终持久化 `business_session_id -> sdk_session_id`

- [ ] **步骤 4：运行 chat 测试验证通过**

运行：`uv run pytest tests/test_chat_api_mvp.py -v`
预期：PASS

- [ ] **步骤 5：运行目标测试集做集成验证**

运行：`uv run pytest tests/test_config_mvp.py tests/test_session_manager_mvp.py tests/test_upload_api_mvp.py tests/test_chat_api_mvp.py -v`
预期：PASS

- [ ] **步骤 6：提交任务 4 变更**

运行：
```bash
git add app tests
git commit -m "feat: add chat API and SDK session resume for MVP (task 4/4)"
```

## 审查与执行备注

- 当前工作区存在大量已删除但未提交的旧版 `app/` 与 `src/` 文件；执行时不要恢复这些旧文件，直接按 MVP 设计重建新结构。
- MVP 默认不兼容旧的 JMI 专用测试；只验证本计划新增的测试与最小健康接口。
- 若 Claude Agent SDK 本地不可用，`tests/test_chat_api_mvp.py` 必须使用 monkeypatch/mock 验证 API 编排而非真实外部调用。

## 执行方式

计划已保存到 `docs/superpowers/plans/2026-03-31-claude-agent-platform-mvp.md`。

默认执行方式：内联执行当前计划，不启用子代理。
