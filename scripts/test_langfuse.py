#!/usr/bin/env python
"""测试 LangFuse 集成的脚本"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config, configure_sdk_environment
from src.tracing.langfuse_tracer import LangfuseTracer
from datetime import datetime


def main():
    """测试 LangFuse 集成"""
    print("🔍 测试 LangFuse 集成\n")

    # 1. 加载配置
    print("1. 加载配置...")
    config = configure_sdk_environment(get_config())
    print(f"   ✅ 配置加载成功")
    print(f"   - Enabled: {config.langfuse.enabled}")
    print(f"   - Host: {config.langfuse.get_host()}")

    # 2. 初始化 Tracer
    print("\n2. 初始化 LangFuse Tracer...")
    tracer = LangfuseTracer(config.langfuse)
    print(f"   ✅ Tracer 初始化成功")
    print(f"   - Tracer enabled: {tracer.enabled}")

    if not tracer.enabled:
        print("\n⚠️  LangFuse 未启用")
        print("   要启用 LangFuse，请:")
        print("   1. 在 conf/config.yaml 中设置 langfuse.enabled: true")
        print("   2. 确保配置了正确的 public_key 和 secret_key")
        return

    # 3. 测试创建 Trace
    print("\n3. 测试创建 Trace...")
    with tracer.trace_agent_execution(
        session_id="test_session_001",
        user_id="test_user",
        metadata={"test": True, "purpose": "integration_test"}
    ) as trace_id:
        print(f"   ✅ Trace 创建成功: {trace_id}")

        # 4. 测试记录 Event
        print("\n4. 测试记录 Event...")
        tracer.log_event(
            name="test_event",
            metadata={"event_type": "test"},
            input_data={"message": "Hello LangFuse"},
        )
        print(f"   ✅ Event 记录成功")

        # 5. 测试记录 Generation
        print("\n5. 测试记录 Generation...")
        start = datetime.now()
        tracer.log_agent_generation(
            name="test_generation",
            prompt="测试提示",
            model="claude-sonnet-4-5",
            start_time=start,
            end_time=datetime.now(),
            completion="测试回复",
            metadata={"test": True},
        )
        print(f"   ✅ Generation 记录成功")

        # 6. 测试更新 Trace
        print("\n6. 测试更新 Trace...")
        tracer.update_trace(
            output={"result": "success"},
            metadata={"completed": True},
            tags=["test", "integration"],
        )
        print(f"   ✅ Trace 更新成功")

        # 7. 测试评分
        print("\n7. 测试添加评分...")
        tracer.score_trace(
            name="quality",
            value=0.95,
            comment="测试评分",
        )
        print(f"   ✅ 评分添加成功")

    # 8. 刷新数据
    print("\n8. 刷新 LangFuse 数据...")
    tracer.shutdown()
    print(f"   ✅ 数据已刷新到 LangFuse 服务器")

    print("\n" + "="*50)
    print("✅ 所有测试通过！")
    print("="*50)
    print(f"\n📊 请访问 {config.langfuse.get_host()} 查看追踪数据")
    print(f"   在 Traces 页面应该能看到 session_id: test_session_001")


if __name__ == "__main__":
    main()
