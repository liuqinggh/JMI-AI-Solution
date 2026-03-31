#!/bin/bash
# 快速测试脚本 - 演示主要功能

echo "=========================================="
echo "Claude Agent Platform - 快速测试"
echo "=========================================="
echo ""

# 1. 运行文档验证测试
echo "1️⃣  运行文档验证测试..."
.venv/bin/python -m pytest tests/test_documentation_validation.py -v --tb=line
echo ""

# 2. 运行 API 集成测试
echo "2️⃣  运行 API 集成测试..."
.venv/bin/python -m pytest tests/integration/test_api_endpoints.py -v --tb=line
echo ""

# 3. 生成测试报告
echo "3️⃣  生成测试报告..."
.venv/bin/python -m pytest tests/ --tb=line -v --junit-xml=test-results.xml
echo ""

echo "=========================================="
echo "✅ 测试完成！"
echo "=========================================="
echo ""
echo "测试报告已生成："
echo "  - 控制台输出（上方）"
echo "  - test-results.xml（JUnit 格式）"
echo "  - TEST_RESULTS.md（详细报告）"
echo ""
