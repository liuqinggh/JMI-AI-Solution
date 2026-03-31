# 文件上传与会话绑定实现方案 v2

**项目**: JMI-AI-Solution (FastAPI + Claude Agent SDK)  
**版本**: v2.0  
**日期**: 2026-03-31  
**状态**: 已按最新约束重设计

---

## 一、核心约束

本方案以以下约束为前提：

- 文件上传接口和 chat 接口必须拆开
- `session_id` 只能由 Claude Agent SDK 生成
- 文件保存在本地工作区
- 不再沿用当前 `ContentAddressedStore` 的 `.objects/.sessions/.pending` 文件模型
- Agent 仍通过本地工作区中的文件路径访问用户文件

结论：

- 上传接口不再接收 `session_id`
- 上传接口只生成 `upload_batch_id` 与 `file_ids`
- `POST /api/v1/agent/messages` 是唯一把文件绑定到 SDK `session_id` 的入口

---

## 二、设计目标

### 2.1 核心能力

提供一套清晰、可演进的文件上传体系，支持：

- 预上传文件，得到 `upload_batch_id`
- 首轮 chat 使用 `upload_batch_id`，由 SDK 返回 `session_id`
- 服务端在获得 `session_id` 后完成文件与会话绑定
- 后续会话继续读取同一批文件
- 任意轮次追加上传新文件
- 前端按会话列出、下载、删除文件

### 2.2 非目标

当前版本不包含：

- 对象存储
- 内容寻址去重
- 自定义 MCP 文件工具
- 文件内容直接塞入 prompt
- 文档转 Markdown
- 分块上传和断点续传

---

## 三、核心决策

### 3.1 两阶段绑定

文件绑定分为两个阶段：

1. **上传阶段**
   - 文件先进入 `upload_batch`
   - 此时还没有 `session_id`
   - 文件仅处于“待会话绑定”状态

2. **会话绑定阶段**
   - 首轮 chat 带上 `upload_batch_id`
   - 服务端创建临时工作区并调用 SDK
   - batch 文件先复制到临时工作区
   - SDK 返回 `session_id` 后，服务端将临时工作区原子迁移到会话目录

### 3.2 单次消费的 `upload_batch`

`upload_batch_id` 设计为单次消费：

- 一个 batch 只能首次绑定到一个 `session_id`
- 绑定成功后，batch 状态变为 `consumed`
- 后续若想追加文件，必须重新上传生成新 batch

这样可以避免一个上传批次被多个会话错误复用。

### 3.3 会话工作区即 Agent 工作目录

Agent 执行时，`cwd` 直接指向会话工作区：

- Agent 文件访问路径使用相对路径
- 服务端注入的文件路径统一写成 `./uploads/<safe_filename>`
- 不额外引入虚拟路径层

这比当前复杂的对象目录、软链接、别名目录更直接。

---

## 四、存储结构

### 4.1 工作区根目录

建议新增统一根目录：

```text
.workspace-data/
```

### 4.2 目录结构

```text
JMI-AI-Solution/
├── .workspace-data/
│   ├── upload-batches/
│   │   └── <upload_batch_id>/
│   │       ├── manifest.json
│   │       └── files/
│   │           ├── <file_id>__report.pdf
│   │           └── <file_id>__claim.csv
│   ├── pending-workspaces/
│   │   └── <request_id>/
│   │       ├── manifest.json
│   │       ├── uploads/
│   │       └── artifacts/
│   └── sessions/
│       └── <session_id>/
│           ├── manifest.json
│           ├── uploads/
│           └── artifacts/
```

### 4.3 三类路径

保留“路径分层”的思路，但比旧方案更简单：

| 路径类型 | 用途 | 示例 |
|---|---|---|
| 实际路径 | 服务端真实存储路径 | `.workspace-data/sessions/<session_id>/uploads/report.pdf` |
| Agent 路径 | 注入给 Agent 的相对路径 | `./uploads/report.pdf` |
| 下载 URL | 前端访问路径 | `/api/v1/files/sessions/<session_id>/<file_id>` |

说明：

- 前端永远不看到真实绝对路径
- Agent 永远不看到 batch 根目录
- Agent 只看到当前会话工作区里的相对路径

---

## 五、数据模型

### 5.1 Upload Batch

```json
{
  "upload_batch_id": "ub_8f6d0d4f6f8540f3a6c6d75d",
  "status": "pending",
  "created_at": "2026-03-31T10:00:00Z",
  "expires_at": "2026-04-01T10:00:00Z",
  "bound_session_id": null,
  "files": [
    {
      "file_id": "file_01jq...",
      "original_filename": "report.pdf",
      "safe_filename": "report.pdf",
      "stored_name": "file_01jq__report.pdf",
      "content_type": "application/pdf",
      "size": 813433,
      "sha256": "..."
    }
  ]
}
```

`status` 取值：

- `pending`
- `consumed`
- `expired`
- `deleted`

### 5.2 Session Manifest

```json
{
  "session_id": "sdk-generated-session-id",
  "created_at": "2026-03-31T10:05:00Z",
  "updated_at": "2026-03-31T10:20:00Z",
  "files": [
    {
      "file_id": "file_01jq...",
      "original_filename": "report.pdf",
      "safe_filename": "report.pdf",
      "relative_path": "./uploads/report.pdf",
      "download_url": "/api/v1/files/sessions/sdk-generated-session-id/file_01jq...",
      "content_type": "application/pdf",
      "size": 813433,
      "sha256": "...",
      "source_batch_id": "ub_8f6d0d4f6f8540f3a6c6d75d",
      "uploaded_at": "2026-03-31T10:00:00Z"
    }
  ]
}
```

---

## 六、API 设计

### 6.1 上传接口

#### `POST /api/v1/files/batches`

用途：

- 预上传文件
- 生成 `upload_batch_id`
- 返回本批次的 `file_ids`

请求：

```http
POST /api/v1/files/batches
Content-Type: multipart/form-data
X-API-Key: your_api_key

files: [file1, file2, ...]
```

响应：

```json
{
  "success": true,
  "upload_batch_id": "ub_8f6d0d4f6f8540f3a6c6d75d",
  "status": "pending",
  "files": [
    {
      "file_id": "file_01jq...",
      "filename": "report.pdf",
      "content_type": "application/pdf",
      "size": 813433
    },
    {
      "file_id": "file_01jr...",
      "filename": "claim.csv",
      "content_type": "text/csv",
      "size": 15200
    }
  ]
}
```

#### `GET /api/v1/files/batches/{upload_batch_id}`

用途：

- 查询上传批次状态
- 给前端做上传后确认

#### `DELETE /api/v1/files/batches/{upload_batch_id}`

用途：

- 删除尚未绑定会话的批次

限制：

- `consumed` 状态不允许删除

### 6.2 Chat 接口

#### `POST /api/v1/agent/messages`

用途：

- 新建会话或续接会话
- 可选携带一个待绑定的 `upload_batch_id`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `prompt` | string | 是 | 用户输入 |
| `session_id` | string | 否 | 续接已有 SDK 会话 |
| `upload_batch_id` | string | 否 | 本轮附带的新上传批次 |
| `file_ids` | string[] | 否 | 可选，仅绑定批次中的部分文件 |
| `structured_output_profile` | string | 否 | 维持现有结构化输出能力 |
| `final_answer_text_policy` | string | 否 | 维持现有答案拼接策略 |
| `user_id` | string | 否 | 追踪用途 |

关键变化：

- 不再接受 `files[]`
- 文件上传必须走 `/files/batches`

### 6.3 会话文件接口

#### `GET /api/v1/files/sessions/{session_id}`

用途：

- 列出会话已绑定文件

#### `GET /api/v1/files/sessions/{session_id}/{file_id}`

用途：

- 下载或预览某个会话文件

#### `DELETE /api/v1/files/sessions/{session_id}/{file_id}`

用途：

- 从会话工作区删除文件
- 更新会话 manifest

---

## 七、核心流程

### 7.1 首轮会话，无文件

1. 前端调用 `POST /api/v1/agent/messages`
2. 服务端创建空的 `pending-workspaces/<request_id>`
3. 调用 SDK
4. 获取 SDK 返回的 `session_id`
5. 将 `pending-workspaces/<request_id>` 迁移到 `sessions/<session_id>/`
6. 返回 `session_id`

### 7.2 首轮会话，带上传批次

1. 前端先调用 `POST /api/v1/files/batches`
2. 获得 `upload_batch_id`
3. 前端调用 `POST /api/v1/agent/messages`，携带 `prompt + upload_batch_id`
4. 服务端创建 `pending-workspaces/<request_id>/`
5. 将 batch 文件复制到 `pending-workspaces/<request_id>/uploads/`
6. 组装文件上下文并注入 prompt
7. 调用 SDK
8. 获取 SDK 返回的 `session_id`
9. 将 `pending-workspaces/<request_id>` 原子迁移到 `sessions/<session_id>/`
10. 将 batch 标记为 `consumed`
11. 返回 `session_id`

### 7.3 续接会话，无新文件

1. 前端调用 `POST /api/v1/agent/messages`
2. 传入 `prompt + session_id`
3. 服务端直接使用 `sessions/<session_id>/` 作为 `cwd`
4. 从会话 manifest 读取文件列表并注入 prompt
5. 调用 SDK
6. 返回结果

### 7.4 续接会话，追加新文件

1. 前端先上传新 batch
2. 调用 `POST /api/v1/agent/messages`，传入 `prompt + session_id + upload_batch_id`
3. 服务端将 batch 文件导入现有 `sessions/<session_id>/uploads/`
4. 更新 session manifest
5. 注入最新文件列表
6. 调用 SDK
7. 将 batch 标记为 `consumed`
8. 返回结果

---

## 八、Prompt 注入策略

### 8.1 注入位置

文件信息注入不放在通用 HTTP middleware，而放在 Agent 请求准备层：

- 先解析本轮可用文件
- 再构造 prompt
- 最后调用 SDK

这样文件选择、权限校验、工作区准备都能在一个地方完成。

### 8.2 注入原则

- 只注入文件清单和可访问路径
- 不直接注入文件内容
- 注入路径必须是 Agent 在当前 `cwd` 下可访问的路径
- 图片仍可扩展为多模态 block，普通文件默认走路径清单

### 8.3 注入示例

```xml
<uploaded_files>
- report.pdf
  Path: ./uploads/report.pdf
- claim.csv
  Path: ./uploads/claim.csv

Use Read/Grep/Bash on these paths when needed.
</uploaded_files>
```

### 8.4 大量文件场景

为避免 prompt 过长，建议：

- 默认注入全部文件名和路径
- 当文件数超过阈值时，仅注入前 N 个文件和总数摘要
- 仍允许 Agent 通过 `ls ./uploads` 自行查看目录

---

## 九、配置设计

建议扩展 `conf/config.yaml`：

```yaml
storage:
  workspace_root: ".workspace-data"
  upload_batch_dir: "upload-batches"
  pending_workspace_dir: "pending-workspaces"
  session_dir: "sessions"
  max_file_size: 10485760
  max_batch_files: 20
  max_batch_size: 52428800
  max_session_files: 100
  batch_ttl_hours: 24
```

说明：

- `workspace_root` 统一管理上传批次、会话工作区和临时工作区
- 当前 `upload_root`、`pending_dir_name` 等旧字段应迁移或废弃

---

## 十、安全设计

### 10.1 文件名安全

- 使用 `Path(filename).name` 取基名
- 过滤路径分隔符和危险字符
- 同名文件加后缀避免覆盖

### 10.2 路径边界

- 所有读写路径必须落在 `workspace_root` 下
- 下载接口只能访问 `sessions/<session_id>/uploads/` 中已登记的文件
- 不允许通过文件名拼接直接访问任意路径

### 10.3 文件类型与大小

- 白名单 MIME 校验
- 限制单文件大小
- 限制单批次文件数和总大小

### 10.4 Batch 消费保护

- `upload_batch_id` 使用高熵随机 ID
- 批次绑定时加锁
- 已消费 batch 不可重复绑定

### 10.5 认证与授权

当前阶段可继续沿用 API Key 认证。

但要注意：

- 如果接口直接暴露给浏览器，仅凭全局 API Key + `session_id` 仍不足以表示会话归属
- 若未来进入多用户场景，必须补充用户认证与会话归属校验

---

## 十一、代码改造建议

### 11.1 新增模块

建议新增：

- `app/services/upload_batch_service.py`
- `app/services/session_workspace_service.py`
- `app/services/file_context_service.py`
- `app/schemas/file_batch.py`
- `app/api/v1/endpoints/files.py`

### 11.2 调整现有模块

#### `app/api/v1/endpoints/agents.py`

修改点：

- 移除 `files: list[UploadFile] = File(default=[])`
- 新增 `upload_batch_id: str | None = Form(None)`
- 新增 `file_ids: list[str] | None = Form(None)`
- 在调用 SDK 前，通过服务层准备工作区和 prompt

#### `app/agents/executor.py`

保留现有职责：

- 调用 SDK
- 收集 `session_id`
- 组装最终响应

不要再在这里承担上传存储职责。

#### `app/config.py`

修改点：

- 新增新的 `StorageSettings`
- 废弃旧的内容寻址相关目录配置

### 11.3 废弃当前实现

本方案不再延续当前 `ContentAddressedStore` 的设计：

- 不再使用 `.objects`
- 不再使用 `.sessions`
- 不再使用 `.pending`
- 不再使用软链接和内容去重作为默认实现

如果需要迁移，应将其视为一次明确的存储方案切换，而不是兼容叠加。

---

## 十二、错误处理

建议统一错误码：

- `FILE_TOO_LARGE`
- `INVALID_FILE_TYPE`
- `BATCH_NOT_FOUND`
- `BATCH_ALREADY_CONSUMED`
- `FILE_NOT_FOUND`
- `SESSION_NOT_FOUND`
- `INVALID_FILE_SELECTION`
- `WORKSPACE_PREPARE_FAILED`
- `SDK_SESSION_NOT_RETURNED`

示例：

```json
{
  "success": false,
  "error": {
    "code": "BATCH_ALREADY_CONSUMED",
    "message": "Upload batch has already been bound to a session"
  }
}
```

---

## 十三、清理策略

### 13.1 未绑定批次

- `pending` 状态 batch 超过 TTL 自动清理
- 清理时同时删除批次目录和 manifest

### 13.2 挂起工作区

- SDK 调用失败且未获得 `session_id` 时，删除 `pending-workspaces/<request_id>/`
- batch 保持 `pending`，允许客户端重试 chat

### 13.3 会话工作区

- 默认不自动删除
- 后续可按业务需要增加手动清理或过期清理

---

## 十四、测试要求

### 14.1 单元测试

- 文件名清洗
- batch 创建与 manifest 写入
- batch 单次消费保护
- pending workspace 到 session workspace 的迁移
- prompt 注入内容正确性

### 14.2 集成测试

- 上传 batch 后首轮 chat 成功绑定
- 新会话失败时 batch 保持 `pending`
- 续接会话追加 batch 成功
- 会话文件列表、下载、删除正确
- 已消费 batch 重复使用返回 409

### 14.3 回归测试

- 结构化输出仍可用
- `final_answer_text_policy` 仍可用
- Langfuse tracing 不受影响

---

## 十五、实施顺序

### Phase 1

- 新增 `files.py` 路由
- 实现 `upload_batch_service`
- 实现 batch manifest 与本地存储

### Phase 2

- 改造 `agents.py`
- 接入 `upload_batch_id`
- 实现 pending workspace 和 session workspace 迁移

### Phase 3

- 实现会话文件列表、下载、删除
- 实现 batch 清理任务

### Phase 4

- 删除或下线旧的 `ContentAddressedStore` 依赖
- 更新 API 文档与测试

---

## 十六、最终结论

本方案的核心是：

- 上传和 chat 分离
- `session_id` 只由 SDK 生成
- 文件先进入 `upload_batch`
- 首轮 chat 成功后再绑定到 `session workspace`
- Agent 始终在会话工作区中通过相对路径访问文件

这版设计比当前实现更贴近真实业务流程，也更符合最新约束。它牺牲了内容寻址和去重能力，但换来了更清晰的状态机、更简单的目录模型和更稳定的会话绑定语义。
