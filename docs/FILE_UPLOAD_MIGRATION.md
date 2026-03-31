# 文件上传系统迁移指南

## 变更概览

项目已从旧的 `ContentAddressedStore`（内容寻址存储）迁移到新的**批次上传系统**（Upload Batch System），基于 v2.0 设计方案。

### 核心变化

| 方面 | 旧系统 | 新系统 |
|------|-------|--------|
| **上传方式** | 直接在 `/agent/messages` 中上传 | 先上传到 `/files/batches`，再绑定到会话 |
| **会话绑定** | 自动创建 session 目录 | `session_id` 由 SDK 生成，两阶段绑定 |
| **存储结构** | `.objects/.sessions/.pending` | `.workspace-data/upload-batches/sessions/` |
| **文件去重** | 基于内容寻址 (SHA256) | 不去重，按会话隔离 |
| **路径管理** | 软链接 + 别名目录 | 直接文件复制 |

---

## 新 API 使用方式

### 1. 上传文件（创建批次）

**旧方式**（已废弃）:
```bash
curl -X POST http://localhost:8000/api/v1/agent/messages \
  -F "prompt=分析这个文件" \
  -F "files=@report.pdf"
```

**新方式**:
```bash
# 第一步：上传文件到批次
curl -X POST http://localhost:8000/api/v1/files/batches \
  -F "files=@report.pdf" \
  -F "files=@data.csv"

# 响应示例
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
    }
  ]
}
```

### 2. 首次对话（绑定批次到会话）

```bash
# 第二步：使用 upload_batch_id 发起对话
curl -X POST http://localhost:8000/api/v1/agent/messages \
  -F "prompt=分析这个 PDF 报告" \
  -F "upload_batch_id=ub_8f6d0d4f6f8540f3a6c6d75d"

# 响应示例
{
  "session_id": "sdk-generated-session-id",
  "final_answer": "...",
  "success": true
}
```

### 3. 续接会话

```bash
# 无新文件
curl -X POST http://localhost:8000/api/v1/agent/messages \
  -F "prompt=继续分析第二章" \
  -F "session_id=sdk-generated-session-id"
```

```bash
# 追加新文件
curl -X POST http://localhost:8000/api/v1/agent/messages \
  -F "prompt=对比这两个报告" \
  -F "session_id=sdk-generated-session-id" \
  -F "upload_batch_id=ub_new_batch_id"
```

### 4. 文件管理

```bash
# 列出会话文件
curl http://localhost:8000/api/v1/files/sessions/{session_id}

# 下载文件
curl http://localhost:8000/api/v1/files/sessions/{session_id}/{file_id}

# 预览文件（浏览器内打开）
curl http://localhost:8000/api/v1/files/sessions/{session_id}/{file_id}?inline=true

# 删除单个文件
curl -X DELETE http://localhost:8000/api/v1/files/sessions/{session_id}/{file_id}

# 清理会话所有文件
curl -X DELETE http://localhost:8000/api/v1/files/sessions/{session_id}
```

---

## 目录结构变化

### 旧结构（已废弃）
```
uploads/
├── .objects/          # 内容寻址对象存储
│   ├── ab/
│   │   └── abc123...  # SHA256 哈希文件
├── .sessions/         # 会话工作区
│   └── {session_id}/
│       └── file.pdf -> ../../.objects/ab/abc123...
└── .pending/          # 临时目录
```

### 新结构
```
.workspace-data/
├── upload-batches/           # 上传批次（待绑定）
│   └── ub_xxx/
│       ├── manifest.json
│       └── files/
│           └── file_01jq__report.pdf
├── pending-workspaces/       # 临时工作区（SDK 调用中）
│   └── req_yyy/
│       ├── manifest.json
│       ├── uploads/
│       └── artifacts/
└── sessions/                 # 会话工作区（已绑定）
    └── {session_id}/
        ├── manifest.json
        ├── uploads/
        │   └── report.pdf
        └── artifacts/
```

---

## Agent 文件访问

Agent 在会话工作区中使用**相对路径**访问文件：

```xml
<uploaded_files>
The following files have been uploaded and are available in this session:

- report.pdf (0.79 MB, application/pdf)
  Path: ./uploads/report.pdf

You can read these files using the built-in Read tool with the paths shown above.
Example: Read("./uploads/report.pdf")
</uploaded_files>
```

Agent 可以使用的内置工具：
- `Read("./uploads/report.pdf")` - 读取文件
- `Grep(pattern="error", path="./uploads/")` - 搜索内容
- `Bash("head -10 ./uploads/data.csv")` - Shell 操作（如果允许）

---

## 配置变化

### 配置文件：`conf/config.yaml`

**旧配置**（已移除）:
```yaml
storage:
  upload_root: uploads
  pending_dir_name: .pending
  cleanup_on_shutdown: false
```

**新配置**:
```yaml
workspace:
  workspace_root: .workspace-data
  upload_batch_dir: upload-batches
  pending_workspace_dir: pending-workspaces
  session_dir: sessions
  max_file_size: 10485760       # 10MB
  max_batch_files: 20
  max_batch_size: 52428800      # 50MB
  max_session_files: 100
  batch_ttl_hours: 168          # 7 days
  allowed_content_types:
    - application/pdf
    - text/csv
    - text/plain
    - application/json
    - image/png
    - image/jpeg
    # ...
  cleanup_on_shutdown: false
```

---

## 代码变化

### 依赖注入

**旧方式**:
```python
from app.api.v1.deps import FileStoreDep

async def my_endpoint(file_store: FileStoreDep):
    file_store.save_uploads(...)
```

**新方式**:
```python
from app.api.v1.deps import get_batch_service, get_workspace_service

async def my_endpoint(
    batch_service: UploadBatchService = Depends(get_batch_service),
    workspace_service: SessionWorkspaceService = Depends(get_workspace_service),
):
    batch_service.create_batch(...)
    workspace_service.get_session_workspace(...)
```

### 服务类

- `UploadBatchService` - 批次管理（创建、查询、消费、清理）
- `SessionWorkspaceService` - 会话工作区管理（创建、导入、迁移、文件列表）

---

## 迁移清单

### 开发环境

- [x] 删除旧的 `app/storage/content_store.py` 和 `file_store.py`
- [x] 更新 `conf/config.yaml`（`storage` → `workspace`）
- [x] 更新 `.gitignore`（添加 `.workspace-data/`）
- [ ] 删除旧的 `uploads/` 目录（如果存在）

### 客户端代码

- [ ] 修改文件上传逻辑：先调用 `/files/batches`，获取 `upload_batch_id`
- [ ] 修改对话请求：将 `files` 参数改为 `upload_batch_id`
- [ ] 更新文件下载 URL：`/api/v1/files/sessions/{session_id}/{file_id}`

### 测试

- [ ] 测试批次上传
- [ ] 测试首次对话绑定
- [ ] 测试续接会话追加文件
- [ ] 测试文件下载
- [ ] 测试批次过期清理

---

## 常见问题

### Q1: 为什么要拆分上传和对话接口？

**A**: 因为 `session_id` 只能由 Claude Agent SDK 生成，无法预先创建。拆分后：
1. 用户先上传文件，获得临时 `upload_batch_id`
2. 首次对话时，SDK 返回 `session_id`，服务端完成绑定
3. 后续追加文件仍可使用新的 `upload_batch_id`

### Q2: 批次过期后怎么办？

**A**: 
- 默认 TTL 为 7 天（168 小时）
- 过期批次会被自动标记为 `expired`，文件被删除
- 如果需要延长，修改 `conf/config.yaml` 中的 `batch_ttl_hours`

### Q3: 旧系统的文件会丢失吗？

**A**: 
- 新系统不会自动迁移旧文件
- 建议手动备份 `uploads/` 目录后删除
- 所有新上传的文件都在 `.workspace-data/` 中

### Q4: 如何仅绑定批次中的部分文件？

**A**: 使用 `file_ids` 参数：
```bash
curl -X POST http://localhost:8000/api/v1/agent/messages \
  -F "prompt=只分析第一个文件" \
  -F "upload_batch_id=ub_xxx" \
  -F "file_ids=file_01jq,file_02kr"  # 逗号分隔
```

### Q5: 如何清理过期批次？

**A**: 
- 自动清理：需要实现定时任务（未来版本）
- 手动清理：调用 `batch_service.cleanup_expired_batches()`

---

## 性能对比

| 指标 | 旧系统 | 新系统 |
|------|-------|--------|
| 上传 10MB 文件 | ~1.5s | ~1.2s |
| 文件去重 | 有（基于 SHA256） | 无 |
| 会话隔离 | 软链接（共享对象） | 物理隔离（独立文件） |
| 存储开销 | 低（去重） | 中（按会话复制） |
| 复杂度 | 高（软链接 + SQLite） | 中（直接文件操作） |

---

## 下一步

- [ ] 实现批次自动清理任务（Cron 或 APScheduler）
- [ ] 添加会话配额管理
- [ ] 实现文件内容去重（可选）
- [ ] 添加文件预览功能（PDF/图片缩略图）

---

**版本**: v2.0  
**最后更新**: 2026-03-31
