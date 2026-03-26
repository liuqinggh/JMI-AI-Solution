# 存储优化方案

## 问题诊断

当前 uploads 目录存在以下问题：

1. **文件重复存储**：同一文件在多个目录重复存储
2. **目录混乱**：uploads 根目录混杂 UUID 符号链接和实际目录
3. **无清理机制**：`.pending` 下有大量旧请求目录未清理
4. **空间浪费**：179MB 存储，实际只有 59 个文件

## 优化方案：内容寻址存储

### 架构设计

```
uploads/
├── .objects/          # 内容寻址存储（按 hash 分片）
│   ├── ab/
│   │   └── abc123...  # 实际文件，以 SHA256 命名
│   └── cd/
│       └── cde456...
├── .sessions/         # session 工作目录
│   └── {session-id}/
│       └── file.png -> ../../.objects/ab/abc123...
├── .metadata/         # 元数据和引用计数
│   ├── storage.db     # SQLite 元数据（canonical）
│   └── refs.json      # 兼容/调试快照（legacy）
└── .pending/          # 临时目录（定期清理）
```

### 核心特性

1. **自动去重**：相同内容的文件只存储一份
2. **引用跟踪**：用 SQLite 跟踪每个文件的引用关系和 session 归属
3. **符号链接**：session 目录使用符号链接指向实际文件
4. **垃圾回收**：自动清理未被引用的孤立文件
5. **同 session 去重**：同名且同内容的重复上传直接复用已有链接

### 实现文件

- `src/storage/content_store.py` - 核心存储实现
- `scripts/migrate_to_content_store.py` - 迁移工具
- `scripts/cleanup_storage.py` - 清理工具

## 元数据模型

SQLite `storage.db` 作为唯一可信元数据源，建议至少包含：

- `objects`
  - `content_hash`
  - `filename`
  - `size`
  - `created_at`
- `refs`
  - `ref_path`
  - `content_hash`
  - `session_id`
  - `created_at`

说明：

- `.objects/<hash>` 负责唯一物理落盘
- `.sessions/<session_id>/<name>` 负责逻辑引用
- `refs.json` 仅用于兼容旧迁移数据或人工调试，不再作为长期 canonical source

## 迁移步骤

### 1. 备份现有数据

```bash
cd /Users/cd-la-067/project/Igloo-ai/iglooTech/01-Projects/agent-sdk-api-service
cp -r uploads uploads.backup
```

### 2. 执行迁移（dry-run）

```bash
python scripts/migrate_to_content_store.py
```

查看迁移计划和统计信息。

### 3. 执行实际迁移

```bash
python scripts/migrate_to_content_store.py --real
```

### 4. 验证迁移结果

```bash
python scripts/cleanup_storage.py --stats
```

### 5. 清理旧目录

```bash
# 检查旧目录
ls -la uploads/ | grep -v "^\."

# 确认无误后删除
rm -rf uploads/965326da-d556-4ffd-9ae5-e3b277224456
# ... 删除其他旧目录
```

## 日常维护

### 查看存储统计

```bash
python scripts/cleanup_storage.py --stats
```

### 清理孤立文件

```bash
# 清理 7 天前的孤立文件
python scripts/cleanup_storage.py --days 7

# 清理 30 天前的孤立文件
python scripts/cleanup_storage.py --days 30
```

### 定期清理（可选）

添加 cron 任务：

```bash
# 每天凌晨 2 点清理 30 天前的孤立文件
0 2 * * * cd /path/to/project && python scripts/cleanup_storage.py --days 30
```

## API 集成

### 修改 file_store.py

使用新的 `ContentAddressedStore` 替代现有的 `FileStore`：

```python
from src.storage.content_store import ContentAddressedStore

# 初始化
store = ContentAddressedStore(config.storage)

# 存储文件
content_hash, filename = await store.store_file(upload, temp_path)
link_path = store.create_session_link(session_id, content_hash, filename)

# 获取 session 目录
session_dir = store.get_session_dir(session_id)

# 清理 session
store.cleanup_session(session_id)
```

## 预期收益

基于当前数据（179MB，59 个文件）：

- **去重率**：预计节省 30-50% 空间
- **查找速度**：O(1) 查找时间
- **维护成本**：自动垃圾回收，无需手动清理

## 注意事项

1. **符号链接限制**：Windows 系统需要管理员权限创建符号链接
2. **备份重要性**：迁移前务必备份数据
3. **原子性**：文件上传过程中服务重启不会丢失数据
4. **兼容性**：现有代码需要适配新的存储接口

## 回滚方案

如果迁移出现问题：

```bash
# 停止服务
# 删除新目录
rm -rf uploads/.objects uploads/.sessions uploads/.metadata

# 恢复备份
rm -rf uploads
mv uploads.backup uploads

# 重启服务
```

## 性能优化建议

1. **分片策略**：使用 hash 前 2 位分片，避免单目录文件过多
2. **缓存**：对 refs.json 进行内存缓存
3. **批量操作**：支持批量上传和引用更新
4. **数据库**：当文件数超过 10万 时，考虑使用 SQLite 替代 JSON

## 扩展功能

未来可以添加：

- **压缩存储**：自动压缩大文件
- **CDN 集成**：高频文件推送到 CDN
- **版本控制**：支持文件版本历史
- **加密存储**：敏感文件加密存储
