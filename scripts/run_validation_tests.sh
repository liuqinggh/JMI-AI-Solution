#!/bin/bash
# 文档验证测试脚本

set -e

echo "=========================================="
echo "文档验证测试套件"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查项计数
PASSED=0
FAILED=0

# 辅助函数
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ==========================================
# 1. 文件结构验证
# ==========================================
echo "1️⃣  验证项目文件结构..."
echo ""

# 应该存在的文件
if [ -f "app/agents/client.py" ]; then
    check_pass "app/agents/client.py 存在"
else
    check_fail "app/agents/client.py 缺失"
fi

if [ -f "app/api/chat.py" ]; then
    check_pass "app/api/chat.py 存在"
else
    check_fail "app/api/chat.py 缺失"
fi

if [ -d "app/models" ]; then
    check_pass "app/models/ 目录存在"
else
    check_fail "app/models/ 目录缺失"
fi

# 不应该存在的文件（旧文档中错误描述的）
if [ ! -f "app/agents/executor.py" ]; then
    check_pass "app/agents/executor.py 正确不存在"
else
    check_fail "app/agents/executor.py 不应该存在"
fi

if [ ! -d "app/api/v1/endpoints" ]; then
    check_pass "app/api/v1/endpoints/ 正确不存在"
else
    check_fail "app/api/v1/endpoints/ 不应该存在（应该平级组织）"
fi

if [ ! -d "app/schemas" ]; then
    check_pass "app/schemas/ 正确不存在（应该是 app/models/）"
else
    check_fail "app/schemas/ 不应该存在"
fi

# 技能目录
SKILLS_COUNT=$(ls -1 .claude/skills/ 2>/dev/null | wc -l | xargs)
if [ "$SKILLS_COUNT" -eq 5 ]; then
    check_pass "技能数量正确：$SKILLS_COUNT 个"
else
    check_warn "技能数量为 $SKILLS_COUNT，预期 5 个"
fi

echo ""

# ==========================================
# 2. 配置文件验证
# ==========================================
echo "2️⃣  验证配置文件..."
echo ""

# 验证 YAML 语法
if python -c "import yaml; yaml.safe_load(open('conf/config.yaml'))" 2>/dev/null; then
    check_pass "config.yaml 语法正确"
else
    check_fail "config.yaml 语法错误"
fi

# 验证配置加载
if python -c "from app.core.config import get_settings; s = get_settings(); assert s.app.name == 'Claude Agent Platform'" 2>/dev/null; then
    check_pass "配置加载成功"
else
    check_fail "配置加载失败"
fi

echo ""

# ==========================================
# 3. 模块导入验证
# ==========================================
echo "3️⃣  验证模块导入..."
echo ""

# 测试关键模块导入
if python -c "from app.main import app, create_app" 2>/dev/null; then
    check_pass "主应用模块导入成功"
else
    check_fail "主应用模块导入失败"
fi

if python -c "from app.agents.client import stream_chat" 2>/dev/null; then
    check_pass "Agent 客户端导入成功"
else
    check_fail "Agent 客户端导入失败"
fi

if python -c "from app.models.chat import ChatRequest" 2>/dev/null; then
    check_pass "模型导入成功"
else
    check_fail "模型导入失败"
fi

if python -c "from app.services.skill_loader import SkillLoader" 2>/dev/null; then
    check_pass "服务层导入成功"
else
    check_fail "服务层导入失败"
fi

echo ""

# ==========================================
# 4. 运行单元测试
# ==========================================
echo "4️⃣  运行单元测试..."
echo ""

if pytest tests/test_documentation_validation.py -v --tb=short; then
    check_pass "文档验证测试通过"
else
    check_fail "文档验证测试失败"
fi

echo ""

# ==========================================
# 5. 运行集成测试
# ==========================================
echo "5️⃣  运行集成测试..."
echo ""

if [ -f "tests/integration/test_api_endpoints.py" ]; then
    if pytest tests/integration/test_api_endpoints.py -v --tb=short; then
        check_pass "API 端点测试通过"
    else
        check_fail "API 端点测试失败"
    fi
else
    check_warn "集成测试文件不存在，跳过"
fi

echo ""

# ==========================================
# 6. API 端点验证（需要服务运行）
# ==========================================
echo "6️⃣  API 端点验证（需要服务运行）..."
echo ""

# 检查服务是否运行
if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    check_pass "服务正在运行"

    # 测试健康检查
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/api/v1/health)
    if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
        check_pass "健康检查端点正常"
    else
        check_fail "健康检查端点异常"
    fi

    # 测试文件上传
    echo "test content" > /tmp/test_doc_validation.txt
    UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/upload -F "files=@/tmp/test_doc_validation.txt")
    if echo "$UPLOAD_RESPONSE" | grep -q "file_id"; then
        check_pass "文件上传端点正常"
    else
        check_fail "文件上传端点异常"
    fi
    rm -f /tmp/test_doc_validation.txt

else
    check_warn "服务未运行，跳过 API 端点测试"
    check_warn "启动服务: python -m uvicorn app.main:app --reload"
fi

echo ""

# ==========================================
# 总结
# ==========================================
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo -e "${GREEN}通过：$PASSED${NC}"
echo -e "${RED}失败：$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有验证测试通过！${NC}"
    exit 0
else
    echo -e "${RED}✗ 有 $FAILED 项测试失败${NC}"
    exit 1
fi
