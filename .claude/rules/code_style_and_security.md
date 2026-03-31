# 代码风格与安全硬规则

## 代码风格（必须遵守）
- 使用 ruff format 格式化代码（配置见 `pyproject.toml`）
- 全面添加类型提示（Python 3.11+），使用 `from __future__ import annotations`
- 优先异步（async/await），同步代码仅用于极少数必要场景
- 函数和类命名清晰，必要时添加 docstring
- 导入顺序：标准库 → 第三方库 → 本地模块

## 安全规则（最高优先级）
- **用户输入验证**：所有用户输入必须通过 Pydantic 模型验证（见 `app/models/chat.py:15`）
- **会话隔离**：通过 `business_session_id` 验证确保会话不被跨用户访问（见 `app/core/session_id.py`）
- **API Key 管理**：
  - 禁止在代码中硬编码敏感信息
  - 通过 `conf/config.yaml` 或环境变量配置
  - 生产环境必须使用环境变量覆盖配置文件
- **Agent 工具权限**：
  - 必须通过 `permission_mode` 和 `allowed_tools` 显式限制（见 `app/core/permissions.py`）
  - 默认禁用 Bash 工具，除非明确需要
  - 配置示例见 `conf/config.yaml:12-20`
- **文件上传安全**：
  - 限制文件大小（`upload.max_file_size_mb`）
  - 限制文件类型（`upload.allowed_extensions`）
  - 文件存储在隔离的临时目录

## 配置与部署
- 配置管理：`conf/config.yaml` 作为默认配置，环境变量覆盖
- 敏感配置：`ANTHROPIC_API_KEY`、`GOOGLE_APPLICATION_CREDENTIALS` 等通过环境变量设置
- 生产环境清单：
  - 严格限制 `allowed_tools`（禁用 Bash/Write）
  - 设置 `permission_mode: strict`
  - 启用 `require_approval_for_write: true`
  - 配置 `max_turns` 限制防止无限循环
  - 添加 rate limiting（待实现）

## 日志规范
- 使用结构化日志记录关键操作
- 记录 tool call 和 SDK 事件，但脱敏敏感数据（文件内容、API Key）
- 日志级别通过 `conf/config.yaml:45` 配置

修改代码前，必须确保符合以上所有规则。