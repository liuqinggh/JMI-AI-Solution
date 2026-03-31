# 测试脚本说明

本目录包含项目的测试和验证脚本。

## 可用脚本

### 1. quick_test.sh - 快速测试

运行所有测试套件并生成报告。

```bash
./scripts/quick_test.sh
```

**包含的测试**：
- 文档验证测试（19 个）
- API 集成测试（11 个）

**输出**：
- 控制台输出
- `test-results.xml`（JUnit 格式）
- `TEST_RESULTS.md`（详细报告）

### 2. run_validation_tests.sh - 完整验证

运行完整的验证测试套件，包括文件结构检查、配置验证和 API 测试。

```bash
./scripts/run_validation_tests.sh
```

**检查项目**：
- 文件结构验证
- 配置文件验证
- 模块导入验证
- 单元测试
- 集成测试
- API 端点验证（需要服务运行）

## 测试命令快速参考

### 运行文档验证测试

```bash
.venv/bin/python -m pytest tests/test_documentation_validation.py -v
```

### 运行 API 集成测试

```bash
.venv/bin/python -m pytest tests/integration/test_api_endpoints.py -v
```

### 运行所有测试

```bash
.venv/bin/python -m pytest tests/ -v
```

### 运行特定测试类

```bash
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestProjectStructure -v
```

### 运行特定测试用例

```bash
.venv/bin/python -m pytest tests/test_documentation_validation.py::TestProjectStructure::test_agents_directory_structure -v
```

### 生成覆盖率报告

```bash
.venv/bin/python -m pytest tests/ --cov=app --cov-report=html
```

然后打开 `htmlcov/index.html` 查看报告。

## 测试结果

查看 [TEST_RESULTS.md](../TEST_RESULTS.md) 了解最新的测试结果。

## 故障排查

### 测试失败：ModuleNotFoundError

确保使用虚拟环境中的 Python：

```bash
.venv/bin/python -m pytest ...
```

而不是：

```bash
pytest ...  # 可能使用系统 Python
```

### 测试失败：配置文件错误

验证配置文件语法：

```bash
python -c "import yaml; yaml.safe_load(open('conf/config.yaml'))"
```

### 集成测试失败

某些集成测试需要特定的配置或依赖。检查测试文件中的前置条件。

## 添加新测试

1. 在 `tests/` 目录创建新的测试文件，命名为 `test_*.py`
2. 继承 `pytest` 测试类或使用函数风格
3. 运行 `pytest` 自动发现新测试

示例：

```python
# tests/test_my_feature.py
def test_my_feature():
    assert True
```

## 持续集成

这些脚本可以集成到 CI/CD 流水线：

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: ./scripts/quick_test.sh
```
