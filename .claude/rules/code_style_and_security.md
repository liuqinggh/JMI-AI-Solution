# 代码风格与安全硬规则

## 代码风格（必须遵守）
- 使用 ruff + black（或 ruff format）格式化代码
- 全面添加类型提示（Python 3.11+）
- 优先异步（async/await），同步代码仅用于极少数必要场景
- 函数和类命名清晰，添加必要的 docstring

## 安全规则（最高优先级）
- 用户输入必须经过验证和 sandbox 处理（尤其是 prompt 和工具参数）
- API Key 验证放在 dependencies.py 中，使用 FastAPI security
- 禁止在代码中硬编码敏感信息
- Agent 工具权限必须显式限制，禁用无限制 Bash 执行
- 日志中记录 tool call，但脱敏敏感数据

## 配置与部署
- 使用 .env.example 管理配置
- 生产环境严格限制工具集和 token 使用
- 添加 rate limiting 和 API Key 认证

修改代码前，必须确保符合以上所有规则。