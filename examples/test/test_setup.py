"""测试环境配置

这个脚本用于验证环境是否正确配置。

运行方法:
    python test_setup.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 80)
print("环境配置测试")
print("=" * 80)
print()

# 测试 1: 导入核心模块
print("测试 1: 导入核心模块")
print("-" * 40)
try:
    from app.core.container import ServiceContainer, ServiceMode
    print("✓ app.core.container 导入成功")
except ImportError as e:
    print(f"✗ app.core.container 导入失败: {e}")
    sys.exit(1)

try:
    from app.models.api import GenerateReplyRequest
    print("✓ app.models.api 导入成功")
except ImportError as e:
    print(f"✗ app.models.api 导入失败: {e}")
    sys.exit(1)

try:
    from app.services.orchestrator import Orchestrator
    print("✓ app.services.orchestrator 导入成功")
except ImportError as e:
    print(f"✗ app.services.orchestrator 导入失败: {e}")
    sys.exit(1)

print()

# 测试 2: 创建服务容器
print("测试 2: 创建服务容器")
print("-" * 40)
try:
    container = ServiceContainer(mode=ServiceMode.MOCK)
    print(f"✓ 服务容器创建成功 (模式: {container.mode.value})")
except Exception as e:
    print(f"✗ 服务容器创建失败: {e}")
    sys.exit(1)

print()

# 测试 3: 创建 Orchestrator
print("测试 3: 创建 Orchestrator")
print("-" * 40)
try:
    orchestrator = container.create_orchestrator()
    print(f"✓ Orchestrator 创建成功: {type(orchestrator).__name__}")
except Exception as e:
    print(f"✗ Orchestrator 创建失败: {e}")
    sys.exit(1)

print()

# 测试 4: 测试 Mock 模式生成
print("测试 4: 测试 Mock 模式生成")
print("-" * 40)

import asyncio

async def test_mock_generation():
    try:
        request = GenerateReplyRequest(
            user_id="test_user",
            target_id="test_target",
            conversation_id="test_conv",
            quality="normal",
        )
        
        response = await orchestrator.generate_reply(request)
        
        print(f"✓ Mock 生成成功")
        print(f"  - 回复: {response.reply_text[:50]}...")
        print(f"  - 模型: {response.provider}/{response.model}")
        print(f"  - 成本: ${response.cost_usd:.4f}")
        
        return True
    except Exception as e:
        print(f"✗ Mock 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False

success = asyncio.run(test_mock_generation())

print()

# 测试 5: 检查依赖
print("测试 5: 检查依赖")
print("-" * 40)

dependencies = [
    ("pydantic", "Pydantic"),
    ("fastapi", "FastAPI"),
    ("sqlalchemy", "SQLAlchemy"),
    ("httpx", "HTTPX"),
]

all_deps_ok = True
for module_name, display_name in dependencies:
    try:
        __import__(module_name)
        print(f"✓ {display_name} 已安装")
    except ImportError:
        print(f"✗ {display_name} 未安装")
        all_deps_ok = False

print()

# 总结
print("=" * 80)
print("测试总结")
print("=" * 80)
print()

if success and all_deps_ok:
    print("✓ 所有测试通过！环境配置正确。")
    print()
    print("你现在可以运行示例:")
    print("  python examples/complete_flow_example.py")
    print()
else:
    print("✗ 部分测试失败。请检查:")
    print("  1. 是否从项目根目录运行")
    print("  2. 是否安装了所有依赖: pip install -r requirements.txt")
    print("  3. Python 版本是否 >= 3.10")
    print()
    sys.exit(1)
