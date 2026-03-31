# DeerFlow 文件上传与引用设计总结

## 核心设计理念

### 1. **线程隔离存储**
- 每个线程的文件独立存储在 `.deer-flow/threads/{thread_id}/user-data/uploads/`
- 确保不同对话会话的文件完全隔离,互不干扰
- 线程删除时自动清理相关文件

### 2. **智能文档转换**
- 自动识别并转换 Office 文档(PDF/PPT/Excel/Word)为 Markdown
- 同时保留原始文件和转换后的 Markdown 版本
- Agent 可选择使用更易处理的 Markdown 版本

### 3. **三层路径抽象**

| 路径类型 | 用途 | 示例 |
|---------|------|------|
| **实际路径** (`path`) | 服务端文件系统真实位置 | `.deer-flow/threads/abc/user-data/uploads/file.pdf` |
| **虚拟路径** (`virtual_path`) | Agent 沙箱中使用的路径 | `/mnt/user-data/uploads/file.pdf` |
| **HTTP URL** (`artifact_url`) | 前端 HTTP 访问接口 | `/api/threads/abc/artifacts/mnt/user-data/uploads/file.pdf` |

**设计意义:**
- Agent 与真实文件系统隔离,只看到虚拟路径
- 沙箱系统自动处理路径映射转换
- 前端通过统一的 artifacts API 访问文件

### 4. **双模式沙箱支持**
- **本地沙箱**: 直接使用线程目录,无需额外同步
- **容器沙箱**: 先写线程目录(权威存储),再同步到容器内
- 文件权限自动调整为沙箱可写,避免权限冲突

### 5. **自动感知机制**
- `UploadsMiddleware` 在每次 Agent 请求时自动注入文件列表
- Agent 无需手动查询,直接在对话上下文中看到可用文件
- 格式化的 XML 标签展示文件名、大小和虚拟路径

### 6. **统一的 Artifacts 系统**
- 上传文件和 Agent 生成的文件统一管理
- 同一个 `/api/threads/{id}/artifacts/{path}` 端点访问所有产物
- 支持文件预览(inline)和下载(attachment)两种模式

### 7. **安全防护**
- **路径安全**: 文件名规范化,防止路径遍历攻击
- **内容安全**: HTML/SVG 等活动内容强制下载,防止 XSS
- **权限隔离**: 线程间文件完全隔离,无法跨线程访问

## 完整工作流程

```
1. 前端上传 → multipart/form-data
             ↓
2. 后端接收 → 保存到线程目录 + 文档转换
             ↓
3. 沙箱同步 → (非本地模式) 同步到容器
             ↓
4. Agent 感知 → UploadsMiddleware 注入文件列表
             ↓
5. Agent 操作 → 使用虚拟路径读写文件
             ↓
6. 前端访问 → 通过 artifact_url 预览/下载
```

## 架构图示

```
┌─────────────────────────────────────────────────────────┐
│                        前端层                            │
│  - 使用 artifact_url 访问文件                           │
│  - 上传/列表/删除操作通过 /api/threads/{id}/uploads     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    Gateway API 层                        │
│  uploads.py:  处理上传、转换、删除                       │
│  artifacts.py: 统一的文件访问端点                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   线程目录 (权威存储)                     │
│  .deer-flow/threads/{thread_id}/user-data/uploads/       │
│    ├── document.pdf      (原始文件)                      │
│    └── document.md       (转换后的 Markdown)             │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
    ┌──────────┐            ┌──────────────┐
    │ 本地沙箱  │            │  容器沙箱     │
    │ 直接读取  │            │  同步到容器   │
    └──────────┘            └──────────────┘
          │                         │
          └────────────┬────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                      Agent 层                            │
│  - UploadsMiddleware 注入文件列表                        │
│  - 使用虚拟路径 /mnt/user-data/uploads/...              │
│  - 通过 read_file/write_file/bash 工具操作文件          │
└─────────────────────────────────────────────────────────┘
```

## 关键实现细节

### 路径映射机制
```python
# 实际路径 → 虚拟路径
实际: .deer-flow/threads/abc/user-data/uploads/file.pdf
虚拟: /mnt/user-data/uploads/file.pdf

# 虚拟路径 → HTTP URL
虚拟: /mnt/user-data/uploads/file.pdf
URL:  /api/threads/abc/artifacts/mnt/user-data/uploads/file.pdf
```

### 文件上传响应示例
```json
{
  "success": true,
  "files": [
    {
      "filename": "report.pdf",
      "size": "1234567",
      "path": ".deer-flow/threads/abc/user-data/uploads/report.pdf",
      "virtual_path": "/mnt/user-data/uploads/report.pdf",
      "artifact_url": "/api/threads/abc/artifacts/mnt/user-data/uploads/report.pdf",
      "markdown_file": "report.md",
      "markdown_path": ".deer-flow/threads/abc/user-data/uploads/report.md",
      "markdown_virtual_path": "/mnt/user-data/uploads/report.md",
      "markdown_artifact_url": "/api/threads/abc/artifacts/mnt/user-data/uploads/report.md"
    }
  ],
  "message": "Successfully uploaded 1 file(s)"
}
```

### Agent 接收的文件列表格式
```xml
<uploaded_files>
The following files have been uploaded and are available for use:

- report.pdf (1.2 MB)
  Path: /mnt/user-data/uploads/report.pdf

- report.md (45.3 KB)
  Path: /mnt/user-data/uploads/report.md

You can read these files using the `read_file` tool with the paths shown above.
</uploaded_files>
```

## 设计优势

✅ **清晰的职责分离** - 三种路径各司其职,互不干扰
✅ **强隔离性** - 线程/沙箱/虚拟路径三层隔离
✅ **自动化** - 文档转换、文件感知、路径映射全自动
✅ **安全性** - 多层防护机制,防止常见攻击
✅ **扩展性** - 支持本地和容器两种沙箱模式
✅ **易用性** - Agent 和前端都使用简洁的抽象接口

## 相关文档

- [FILE_UPLOAD.md](FILE_UPLOAD.md) - 文件上传功能详细文档和 API 参考
- [PATH_EXAMPLES.md](PATH_EXAMPLES.md) - 三种路径类型的使用示例和代码
- [ARCHITECTURE.md](ARCHITECTURE.md) - 整体架构文档
