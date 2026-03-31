# 文件上传功能实现方案

**项目**: JMI-AI-Solution (FastAPI + Claude Agent SDK)  
**版本**: v1.0  
**日期**: 2026-03-31  
**设计原则**: 简洁、安全、符合项目规范

---

## 一、设计概述

### 1.1 核心目标

为 FastAPI + Claude Agent SDK 应用提供文件上传与管理能力，支持：
- 会话级文件隔离存储
- Agent 通过 SDK 内置工具访问文件
- 安全的文件上传/下载/删除
- 自动注入文件上下文到 Agent

### 1.2 设计原则

✅ **优先使用 SDK 内置能力** - 使用 Read/Grep/Bash 等内置工具，不开发自定义 MCP  
✅ **简洁至上** - 两层路径设计（存储路径 + 下载 URL），无需虚拟路径  
✅ **安全第一** - 文件类型白名单、路径验证、API Key 认证  
✅ **会话隔离** - 每个 session_id 独立目录，互不干扰  
✅ **符合项目规范** - Pydantic v2、异步、类型注解、Ruff 格式化

### 1.3 不包含的功能

❌ 文档自动转换为 Markdown（简化版暂不需要）  
❌ MCP 自定义工具（使用 SDK 内置工具）  
❌ 用户级隔离（当前仅按 session_id，未来可扩展）  
❌ 分块上传和断点续传（MVP 阶段不需要）

---

## 二、架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                        前端层                            │
│  - 上传: POST /api/v1/files/upload                      │
│  - 下载: GET /api/v1/files/{session_id}/{filename}      │
│  - 列表: GET /api/v1/files/{session_id}                 │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI 层                            │
│  files.py: 文件上传/下载/删除端点                        │
│  deps.py: API Key 验证                                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   文件服务层                              │
│  file_service.py: 文件存储、验证、清理逻辑                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   文件系统存储                            │
│  .uploads/{session_id}/                                  │
│    ├── data.csv                                          │
│    ├── report.pdf                                        │
│    └── image.png                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Agent SDK 层                           │
│  executor.py: System Prompt 注入文件列表                 │
│  SDK 内置工具: read_file(), grep(), bash()               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 数据流程

```
【上传流程】
1. 前端上传 multipart/form-data (session_id + files)
   ↓
2. API 层验证 (API Key + 文件类型 + 大小)
   ↓
3. 文件服务层保存到 .uploads/{session_id}/{sanitized_filename}
   ↓
4. 返回文件元数据 (filename, size, storage_path, download_url)

【Agent 使用流程】
1. 用户发起 Agent 请求 (POST /api/v1/agent/messages)
   ↓
2. executor.py 查询 session_id 对应的文件列表
   ↓
3. 自动注入文件列表到 System Prompt (XML 格式)
   ↓
4. Agent 通过 SDK 内置 read_file() 读取文件
   例如: read_file(".uploads/abc-123/data.csv")
   ↓
5. Agent 处理文件内容并返回结果

【下载流程】
1. 前端请求 GET /api/v1/files/{session_id}/{filename}
   ↓
2. API 层验证 (API Key + 路径安全)
   ↓
3. 返回 FileResponse (支持 inline 预览 / attachment 下载)
```

---

## 三、API 接口设计

### 3.1 路由定义

**路由文件**: `app/api/v1/endpoints/files.py`

| HTTP 方法 | 路径 | 功能 | 认证 |
|-----------|------|------|------|
| POST | `/api/v1/files/upload` | 上传文件（支持多文件） | Required |
| GET | `/api/v1/files/{session_id}` | 列出会话所有文件 | Required |
| GET | `/api/v1/files/{session_id}/{filename}` | 下载/预览文件 | Required |
| DELETE | `/api/v1/files/{session_id}/{filename}` | 删除单个文件 | Required |
| DELETE | `/api/v1/files/{session_id}` | 清理会话所有文件 | Required |

### 3.2 请求/响应模型

#### 3.2.1 上传接口

**请求**:
```http
POST /api/v1/files/upload
Content-Type: multipart/form-data
X-API-Key: your_api_key

# Form 字段
session_id: abc-123 (必填, string)
files: [file1, file2, ...] (必填, 一个或多个文件)
```

**响应**:
```json
{
  "success": true,
  "session_id": "abc-123",
  "files": [
    {
      "filename": "data.csv",
      "size": 1234567,
      "content_type": "text/csv",
      "storage_path": ".uploads/abc-123/data.csv",
      "download_url": "/api/v1/files/abc-123/data.csv",
      "uploaded_at": "2026-03-31T10:30:00Z"
    }
  ],
  "total_size": 1234567,
  "message": "Successfully uploaded 1 file(s)"
}
```

#### 3.2.2 文件列表接口

**请求**:
```http
GET /api/v1/files/{session_id}
X-API-Key: your_api_key
```

**响应**:
```json
{
  "session_id": "abc-123",
  "total_files": 2,
  "total_size": 2048000,
  "files": [
    {
      "filename": "data.csv",
      "size": 1234567,
      "content_type": "text/csv",
      "storage_path": ".uploads/abc-123/data.csv",
      "download_url": "/api/v1/files/abc-123/data.csv",
      "uploaded_at": "2026-03-31T10:30:00Z"
    },
    {
      "filename": "report.pdf",
      "size": 813433,
      "content_type": "application/pdf",
      "storage_path": ".uploads/abc-123/report.pdf",
      "download_url": "/api/v1/files/abc-123/report.pdf",
      "uploaded_at": "2026-03-31T10:35:00Z"
    }
  ]
}
```

#### 3.2.3 下载接口

**请求**:
```http
GET /api/v1/files/{session_id}/{filename}?inline=true
X-API-Key: your_api_key

# Query 参数
inline: true/false (可选, 默认 false)
  - true: Content-Disposition: inline (浏览器预览)
  - false: Content-Disposition: attachment (强制下载)
```

**响应**:
```
Content-Type: {文件的 MIME 类型}
Content-Disposition: inline/attachment; filename="data.csv"

{文件二进制内容}
```

#### 3.2.4 删除接口

**请求**:
```http
DELETE /api/v1/files/{session_id}/{filename}
X-API-Key: your_api_key
```

**响应**:
```json
{
  "success": true,
  "message": "File 'data.csv' deleted successfully"
}
```

### 3.3 错误响应

```json
{
  "success": false,
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File size exceeds maximum limit of 10MB",
    "details": {
      "filename": "large_file.pdf",
      "size": 15728640,
      "max_size": 10485760
    }
  }
}
```

**错误码定义**:
- `FILE_TOO_LARGE` - 文件超过大小限制
- `INVALID_FILE_TYPE` - 不允许的文件类型
- `SESSION_NOT_FOUND` - 会话不存在
- `FILE_NOT_FOUND` - 文件不存在
- `QUOTA_EXCEEDED` - 会话存储配额超限
- `INVALID_FILENAME` - 非法文件名

---

## 四、数据模型设计

### 4.1 Pydantic 模型定义

**文件**: `app/schemas/file.py`

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class FileMetadata(BaseModel):
    """单个文件的元数据"""
    filename: str = Field(..., description="文件名")
    size: int = Field(..., ge=0, description="文件大小（字节）")
    content_type: str = Field(..., description="MIME 类型")
    storage_path: str = Field(..., description="服务器存储路径（Agent 使用）")
    download_url: str = Field(..., description="下载 URL")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, description="上传时间")

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """验证文件名安全性"""
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError("Filename contains invalid characters")
        return v


class UploadResponse(BaseModel):
    """上传响应"""
    success: bool = True
    session_id: str
    files: List[FileMetadata]
    total_size: int = Field(..., description="本次上传总大小")
    message: str = Field(default="Files uploaded successfully")


class FileListResponse(BaseModel):
    """文件列表响应"""
    session_id: str
    total_files: int
    total_size: int
    files: List[FileMetadata]


class DeleteResponse(BaseModel):
    """删除响应"""
    success: bool = True
    message: str


class ErrorDetail(BaseModel):
    """错误详情"""
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: ErrorDetail
```

### 4.2 配置模型

**文件**: `app/config.py` (扩展现有配置)

```python
class UploadConfig(BaseModel):
    """文件上传配置"""
    max_file_size: int = Field(default=10 * 1024 * 1024, description="单文件最大 10MB")
    max_session_size: int = Field(default=50 * 1024 * 1024, description="单会话最大 50MB")
    storage_path: str = Field(default=".uploads", description="存储根目录")
    allowed_content_types: List[str] = Field(
        default=[
            "application/pdf",
            "text/csv",
            "text/plain",
            "application/json",
            "image/png",
            "image/jpeg",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
        ],
        description="允许的文件类型"
    )
    auto_cleanup_days: int = Field(default=7, description="自动清理天数")
```

---

## 五、文件存储方案

### 5.1 目录结构

```
JMI-AI-Solution/
├── .uploads/                        # 存储根目录（必须加入 .gitignore）
│   ├── session-abc-123/
│   │   ├── data.csv
│   │   ├── report.pdf
│   │   └── .metadata.json           # 可选：存储文件元数据
│   ├── session-def-456/
│   │   └── image.png
│   └── .cleanup.log                 # 清理日志（可选）
```

### 5.2 文件命名规范

**规范化处理**:
```python
import re
from pathlib import Path

def sanitize_filename(filename: str) -> str:
    """
    文件名安全化处理
    - 移除路径分隔符，防止路径遍历
    - 移除特殊字符
    - 限制长度
    """
    # 只保留文件名部分
    filename = Path(filename).name
    
    # 移除或替换危险字符
    filename = re.sub(r'[^\w\s.-]', '_', filename)
    
    # 防止隐藏文件
    if filename.startswith('.'):
        filename = 'file_' + filename[1:]
    
    # 限制长度（保留扩展名）
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    if len(name) > 200:
        name = name[:200]
    
    return f"{name}.{ext}" if ext else name
```

**冲突处理**:
- 同名文件自动重命名: `data.csv` → `data_1.csv` → `data_2.csv`
- 或覆盖策略（根据业务需求）

### 5.3 元数据存储

**方案 A: 文件系统 + JSON**（推荐 MVP 阶段）
```json
// .uploads/session-abc-123/.metadata.json
{
  "session_id": "abc-123",
  "created_at": "2026-03-31T10:00:00Z",
  "files": [
    {
      "filename": "data.csv",
      "original_filename": "原始数据.csv",
      "size": 1234567,
      "content_type": "text/csv",
      "uploaded_at": "2026-03-31T10:30:00Z",
      "checksum": "sha256:abcd1234..."
    }
  ],
  "total_size": 1234567
}
```

**方案 B: 数据库**（未来扩展）
```sql
CREATE TABLE uploaded_files (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    size BIGINT NOT NULL,
    content_type VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_session (session_id)
);
```

---

## 六、安全设计

### 6.1 文件类型验证

**白名单策略**（严格模式）:
```python
ALLOWED_CONTENT_TYPES = {
    # 文档类
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/json",
    
    # Office 文档
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    
    # 图片类
    "image/png",
    "image/jpeg",
    "image/gif",
}

def validate_file_type(file: UploadFile) -> bool:
    """验证文件类型（基于 Content-Type）"""
    return file.content_type in ALLOWED_CONTENT_TYPES
```

**增强验证**（可选）:
```python
import magic

def validate_file_type_strict(file_path: str) -> bool:
    """验证文件真实类型（基于文件头）"""
    mime = magic.from_file(file_path, mime=True)
    return mime in ALLOWED_CONTENT_TYPES
```

### 6.2 路径安全

**防止路径遍历攻击**:
```python
from pathlib import Path

def validate_file_path(session_id: str, filename: str, base_path: str = ".uploads") -> Path:
    """
    验证文件路径，防止路径遍历
    Returns: 安全的绝对路径
    Raises: ValueError if path is invalid
    """
    # 规范化输入
    session_id = sanitize_filename(session_id)
    filename = sanitize_filename(filename)
    
    # 构建路径
    base = Path(base_path).resolve()
    target = (base / session_id / filename).resolve()
    
    # 确保目标路径在 base_path 内
    if not str(target).startswith(str(base)):
        raise ValueError("Invalid file path: path traversal detected")
    
    return target
```

### 6.3 大小限制

```python
async def validate_file_size(
    file: UploadFile,
    max_size: int = 10 * 1024 * 1024
) -> None:
    """验证文件大小"""
    # 读取文件头检查大小（不加载到内存）
    file.file.seek(0, 2)  # 移动到文件末尾
    size = file.file.tell()
    file.file.seek(0)  # 重置位置
    
    if size > max_size:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"File size ({size} bytes) exceeds limit ({max_size} bytes)",
                "details": {"size": size, "max_size": max_size}
            }
        )
```

### 6.4 内容安全策略

**危险文件类型强制下载**:
```python
FORCE_DOWNLOAD_TYPES = {
    "text/html",
    "application/javascript",
    "image/svg+xml",
}

def get_content_disposition(filename: str, content_type: str, inline: bool = False) -> str:
    """
    生成 Content-Disposition 头
    - HTML/JS/SVG 强制下载，防止 XSS
    - 其他类型根据 inline 参数决定
    """
    if content_type in FORCE_DOWNLOAD_TYPES:
        inline = False
    
    disposition = "inline" if inline else "attachment"
    return f'{disposition}; filename="{filename}"'
```

### 6.5 API Key 验证

**依赖注入**:
```python
# app/api/v1/deps.py
from fastapi import Header, HTTPException
from app.config import settings

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """验证 API Key"""
    if x_api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )
    return x_api_key
```

---

## 七、Agent SDK 集成

### 7.1 System Prompt 注入

**实现位置**: `app/agents/executor.py`

```python
from app.services.file_service import FileService

async def build_agent_context(
    base_system_prompt: str,
    session_id: str,
    file_service: FileService
) -> str:
    """
    构建 Agent 系统提示，注入文件列表
    """
    # 查询该会话的文件
    files = await file_service.list_files(session_id)
    
    if not files:
        return base_system_prompt
    
    # 格式化文件列表
    file_list_items = []
    for file in files:
        size_mb = file.size / (1024 * 1024)
        file_list_items.append(
            f"- {file.filename} ({size_mb:.2f} MB, {file.content_type})\n"
            f"  Path: {file.storage_path}"
        )
    
    files_context = f"""
<uploaded_files>
The following files have been uploaded and are available in this session:

{chr(10).join(file_list_items)}

You can read these files using the built-in read_file tool with the paths shown above.
Example: read_file("{files[0].storage_path}")
</uploaded_files>
"""
    
    return base_system_prompt + "\n\n" + files_context
```

### 7.2 Agent 使用示例

**Agent 接收到的 System Prompt**:
```xml
<uploaded_files>
The following files have been uploaded and are available in this session:

- sales_data.csv (2.34 MB, text/csv)
  Path: .uploads/session-abc-123/sales_data.csv

- report.pdf (0.79 MB, application/pdf)
  Path: .uploads/session-abc-123/report.pdf

You can read these files using the built-in read_file tool with the paths shown above.
Example: read_file(".uploads/session-abc-123/sales_data.csv")
</uploaded_files>
```

**Agent 自动调用 SDK 内置工具**:
```python
# Agent SDK 会自动执行这些工具调用
{
  "tool": "read_file",
  "parameters": {
    "path": ".uploads/session-abc-123/sales_data.csv",
    "limit": 100  # 只读取前 100 行
  }
}

{
  "tool": "grep",
  "parameters": {
    "pattern": "error|exception",
    "path": ".uploads/session-abc-123/",
    "type": "csv"
  }
}

{
  "tool": "bash",
  "parameters": {
    "command": "head -10 .uploads/session-abc-123/sales_data.csv"
  }
}
```

### 7.3 工具权限配置

**确保 Agent 能访问上传目录**:
```python
# app/agents/options.py
from anthropic_agent_sdk import AgentOptions

def build_agent_options(session_id: str) -> AgentOptions:
    return AgentOptions(
        # 允许 Agent 使用的内置工具
        allowed_tools=["read_file", "grep", "bash"],
        
        # Bash 工具的工作目录限制（可选）
        working_directory=".",
        
        # 权限模式
        permission_mode="auto",  # 或 "manual" 需要人工审批
        
        # 可选：限制文件访问范围
        # file_access_patterns=[".uploads/**"]
    )
```

---

## 八、服务层实现

### 8.1 文件服务接口

**文件**: `app/services/file_service.py`

```python
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from fastapi import UploadFile
from app.schemas.file import FileMetadata
from app.config import settings

class FileService:
    """文件存储服务"""
    
    def __init__(self, storage_path: str = ".uploads"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
    
    async def save_file(
        self,
        session_id: str,
        file: UploadFile
    ) -> FileMetadata:
        """保存上传的文件"""
        # 验证文件类型
        if file.content_type not in settings.upload.allowed_content_types:
            raise ValueError(f"File type {file.content_type} not allowed")
        
        # 创建会话目录
        session_dir = self.storage_path / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 规范化文件名
        safe_filename = sanitize_filename(file.filename)
        file_path = session_dir / safe_filename
        
        # 处理文件名冲突
        file_path = self._resolve_filename_conflict(file_path)
        
        # 保存文件
        with file_path.open("wb") as f:
            content = await file.read()
            f.write(content)
        
        # 构建元数据
        return FileMetadata(
            filename=file_path.name,
            size=file_path.stat().st_size,
            content_type=file.content_type,
            storage_path=str(file_path),
            download_url=f"/api/v1/files/{session_id}/{file_path.name}",
            uploaded_at=datetime.utcnow()
        )
    
    async def list_files(self, session_id: str) -> List[FileMetadata]:
        """列出会话的所有文件"""
        session_dir = self.storage_path / session_id
        if not session_dir.exists():
            return []
        
        files = []
        for file_path in session_dir.glob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                files.append(self._file_to_metadata(session_id, file_path))
        
        return sorted(files, key=lambda f: f.uploaded_at, reverse=True)
    
    async def get_file_path(self, session_id: str, filename: str) -> Path:
        """获取文件路径（带安全验证）"""
        file_path = validate_file_path(session_id, filename, str(self.storage_path))
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        return file_path
    
    async def delete_file(self, session_id: str, filename: str) -> None:
        """删除文件"""
        file_path = await self.get_file_path(session_id, filename)
        file_path.unlink()
    
    async def delete_session(self, session_id: str) -> int:
        """删除会话的所有文件"""
        session_dir = self.storage_path / session_id
        if not session_dir.exists():
            return 0
        
        file_count = len(list(session_dir.glob("*")))
        shutil.rmtree(session_dir)
        return file_count
    
    def _resolve_filename_conflict(self, file_path: Path) -> Path:
        """处理文件名冲突"""
        if not file_path.exists():
            return file_path
        
        name = file_path.stem
        ext = file_path.suffix
        counter = 1
        
        while True:
            new_path = file_path.parent / f"{name}_{counter}{ext}"
            if not new_path.exists():
                return new_path
            counter += 1
    
    def _file_to_metadata(self, session_id: str, file_path: Path) -> FileMetadata:
        """文件路径转元数据"""
        import mimetypes
        content_type, _ = mimetypes.guess_type(str(file_path))
        
        return FileMetadata(
            filename=file_path.name,
            size=file_path.stat().st_size,
            content_type=content_type or "application/octet-stream",
            storage_path=str(file_path),
            download_url=f"/api/v1/files/{session_id}/{file_path.name}",
            uploaded_at=datetime.fromtimestamp(file_path.stat().st_mtime)
        )
```

---

## 九、实施计划

### Phase 1: 核心功能（优先级 P0）

**目标**: 实现基础的文件上传、下载、列表功能

- [ ] **数据模型** (`app/schemas/file.py`)
  - FileMetadata
  - UploadResponse
  - FileListResponse
  - ErrorResponse

- [ ] **配置扩展** (`app/config.py`)
  - UploadConfig 配置类
  - 加载到 settings

- [ ] **文件服务** (`app/services/file_service.py`)
  - FileService 类实现
  - 文件名规范化函数
  - 路径验证函数

- [ ] **API 端点** (`app/api/v1/endpoints/files.py`)
  - POST /upload
  - GET /{session_id}
  - GET /{session_id}/{filename}
  - DELETE /{session_id}/{filename}

- [ ] **路由注册** (`app/api/v1/__init__.py` 或 `app/main.py`)
  - 注册 files router

- [ ] **环境配置**
  - 创建 .uploads/ 目录
  - 添加到 .gitignore
  - 更新 conf/config.yaml

### Phase 2: Agent 集成（优先级 P0）

- [ ] **System Prompt 注入** (`app/agents/executor.py`)
  - build_agent_context() 函数
  - 集成到 Agent 初始化流程

- [ ] **工具权限配置** (`app/agents/options.py`)
  - 确保 read_file/grep/bash 可用
  - 设置合适的权限模式

- [ ] **测试 Agent 文件访问**
  - 上传测试文件
  - 验证 Agent 能读取

### Phase 3: 安全加固（优先级 P1）

- [ ] **文件类型验证**
  - Content-Type 白名单
  - 可选：文件头验证（python-magic）

- [ ] **大小限制**
  - 单文件大小限制
  - 会话总大小限制

- [ ] **路径安全**
  - 路径遍历防护测试
  - 文件名规范化测试

- [ ] **API Key 集成**
  - 所有端点添加 Depends(verify_api_key)
  - 测试认证流程

- [ ] **内容安全**
  - 危险文件类型强制下载
  - Content-Disposition 正确设置

### Phase 4: 运维功能（优先级 P2）

- [ ] **自动清理**
  - 定期清理过期文件的后台任务
  - Cron 配置或 APScheduler

- [ ] **监控日志**
  - 文件上传/下载/删除日志
  - 异常情况告警

- [ ] **配额管理**
  - 会话配额检查
  - 配额超限提示

- [ ] **元数据持久化**
  - .metadata.json 或数据库
  - 文件校验（checksum）

### Phase 5: 测试与文档（优先级 P1）

- [ ] **单元测试** (`tests/test_file_service.py`)
  - FileService 各方法测试
  - 安全验证函数测试

- [ ] **集成测试** (`tests/test_file_endpoints.py`)
  - API 端点测试
  - 错误处理测试

- [ ] **API 文档更新** (`docs/API_REFERENCE.md`)
  - 添加文件上传 API 文档
  - 请求/响应示例

- [ ] **用户文档** (`docs/QUICK_START.md`)
  - 文件上传使用指南
  - Agent 文件访问示例

---

## 十、配置文件示例

### 10.1 conf/config.yaml

```yaml
# 文件上传配置
upload:
  # 单文件最大大小（字节）
  max_file_size: 10485760  # 10MB
  
  # 单会话最大存储（字节）
  max_session_size: 52428800  # 50MB
  
  # 存储路径
  storage_path: ".uploads"
  
  # 允许的文件类型
  allowed_content_types:
    - "application/pdf"
    - "text/csv"
    - "text/plain"
    - "application/json"
    - "image/png"
    - "image/jpeg"
    - "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    - "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  
  # 自动清理天数
  auto_cleanup_days: 7
```

### 10.2 .gitignore

```gitignore
# 文件上传目录
.uploads/
```

---

## 十一、使用示例

### 11.1 前端上传文件（JavaScript）

```javascript
async function uploadFiles(sessionId, files) {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  
  // 支持多文件上传
  for (const file of files) {
    formData.append('files', file);
  }
  
  const response = await fetch('/api/v1/files/upload', {
    method: 'POST',
    headers: {
      'X-API-Key': 'your_api_key_here'
    },
    body: formData
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log('上传成功:', result.files);
    // result.files[0].storage_path → Agent 使用的路径
    // result.files[0].download_url → 前端预览/下载 URL
  } else {
    console.error('上传失败:', result.error);
  }
  
  return result;
}

// 使用示例
const fileInput = document.querySelector('input[type="file"]');
uploadFiles('session-abc-123', fileInput.files);
```

### 11.2 下载/预览文件

```javascript
// 下载文件
function downloadFile(sessionId, filename) {
  const url = `/api/v1/files/${sessionId}/${filename}`;
  window.open(url, '_blank');
}

// 预览文件（如果浏览器支持）
function previewFile(sessionId, filename) {
  const url = `/api/v1/files/${sessionId}/${filename}?inline=true`;
  window.open(url, '_blank');
}
```

### 11.3 Agent 使用文件

**用户请求**:
```
"请分析上传的 sales_data.csv 文件，统计每月销售总额"
```

**Agent 自动收到的上下文**:
```xml
<uploaded_files>
The following files have been uploaded and are available in this session:

- sales_data.csv (2.34 MB, text/csv)
  Path: .uploads/session-abc-123/sales_data.csv

You can read these files using the built-in read_file tool with the paths shown above.
Example: read_file(".uploads/session-abc-123/sales_data.csv")
</uploaded_files>
```

**Agent 执行过程**:
```
1. Thinking: 用户要分析 sales_data.csv，我先读取文件内容
2. Action: read_file(".uploads/session-abc-123/sales_data.csv", limit=50)
3. Observation: [前 50 行数据]
4. Thinking: 数据格式是 日期,产品,金额。我需要按月统计
5. Action: bash("awk -F, '{...}' .uploads/session-abc-123/sales_data.csv")
6. Result: 返回统计结果给用户
```

---

## 十二、安全检查清单

在上线前，确保以下安全措施已实施：

- [ ] ✅ 文件类型白名单验证（Content-Type）
- [ ] ✅ 文件大小限制（单文件 + 会话总量）
- [ ] ✅ 文件名规范化（防止路径遍历）
- [ ] ✅ 路径验证（确保在 .uploads 内）
- [ ] ✅ API Key 认证（所有端点）
- [ ] ✅ 危险文件类型强制下载（HTML/JS/SVG）
- [ ] ✅ 会话隔离（不同 session_id 无法互访）
- [ ] ✅ 错误信息不暴露敏感路径
- [ ] ✅ .uploads/ 目录不在 Web 静态目录中
- [ ] ✅ 日志记录（上传/下载/删除操作）

---

## 十三、未来扩展方向

### 13.1 短期扩展（3 个月内）

1. **用户级隔离**
   - 路径: `.uploads/{user_id}/{session_id}/`
   - API 增加用户认证
   - 防止跨用户访问

2. **文档自动转换**
   - 集成 Pandoc/pdfplumber
   - PDF → Markdown
   - Office → Markdown
   - Agent 优先读取 Markdown 版本

3. **文件搜索功能**
   - 全文搜索接口
   - 跨文件关键词搜索
   - 集成到 Agent 工具

### 13.2 中期扩展（6 个月内）

1. **对象存储支持**
   - S3/OSS/GCS 后端
   - 本地存储作为缓存
   - 大文件直传

2. **文件版本管理**
   - 同名文件保留历史版本
   - 版本回滚
   - 版本对比

3. **分块上传**
   - 支持大文件（>100MB）
   - 断点续传
   - 上传进度跟踪

### 13.3 长期扩展（1 年内）

1. **智能文档理解**
   - OCR 图片文字提取
   - 表格结构化识别
   - 文档摘要生成

2. **协作功能**
   - 文件共享链接
   - 多用户协作标注
   - 评论和审阅

3. **性能优化**
   - CDN 加速下载
   - 缩略图生成
   - 流式传输

---

## 十四、参考资料

- **FastAPI 文件上传官方文档**: https://fastapi.tiangolo.com/tutorial/request-files/
- **Claude Agent SDK 文档**: https://docs.anthropic.com/claude/agent-sdk
- **OWASP 文件上传安全**: https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
- **DeerFlow 文件上传设计**: `docs/FILE_UPLOAD_DESIGN.md`

---

## 附录

### A. 关键技术选型

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| Web 框架 | FastAPI | 项目已使用，异步支持 |
| 文件存储 | 本地文件系统 | MVP 阶段足够，易于开发 |
| 元数据存储 | JSON 文件 | 简单轻量，无需额外依赖 |
| 文件类型检测 | Content-Type | 快速，可选增强为 python-magic |
| Agent 工具 | SDK 内置 | Read/Grep/Bash，无需自定义 |
| 安全验证 | API Key | 与现有认证体系一致 |

### B. 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 单文件上传时间 | < 2s (10MB) | 本地网络环境 |
| 文件列表查询 | < 100ms | 单会话 < 100 个文件 |
| 下载响应时间 | < 500ms | 小文件 (< 1MB) |
| 并发上传支持 | 10 req/s | 单实例 |

### C. 文件大小建议

| 文件类型 | 建议大小 | 最大大小 |
|---------|---------|---------|
| 文本文件 (txt, csv, json) | < 5MB | 10MB |
| PDF 文档 | < 10MB | 20MB |
| 图片 | < 5MB | 10MB |
| Office 文档 | < 10MB | 20MB |
| 单会话总量 | < 30MB | 50MB |

---

**文档版本**: v1.0  
**最后更新**: 2026-03-31  
**维护者**: JMI-AI-Solution Team
