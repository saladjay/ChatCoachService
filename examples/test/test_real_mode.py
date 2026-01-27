"""测试真实模式下的服务调用"""
import asyncio
from app.core.container import ServiceContainer, ServiceMode
from app.models.api import GenerateReplyRequest


async def test_real_mode():
    """测试真实 API 调用"""
    print("=" * 80)
    print("测试真实模式 (ServiceMode.REAL)")
    print("=" * 80)
    
    # 创建服务容器（真实模式）
    container = ServiceContainer(mode=ServiceMode.REAL)
    orchestrator = container.create_orchestrator()
    
    # 准备测试数据
    dialogs = [
        {'speaker': 'jlx 8:13 PM', 'text': 'I am very happy I have finished all my work', 'timestamp': None},
        {'speaker': 'user', 'text': 'sounds good', 'timestamp': None},
        {'speaker': 'jlx 8:14 PM', 'text': 'Yeah I am free now', 'timestamp': None},
        {'speaker': 'ddddddy 8:14 PM', 'text': 'how about your vocation', 'timestamp': None},
        {'speaker': 'jlx 8:14 PM', 'text': 'I have been to China Visited guangzhou city', 'timestamp': None},
    ]
    
    request = GenerateReplyRequest(
        user_id="test_user",
        target_id="jlx",
        conversation_id="test_conv_001",
        dialogs=dialogs,
        quality="normal",
        language="en",
        intimacy_value=50,
    )
    
    print("\n输入数据:")
    print(f"  用户ID: {request.user_id}")
    print(f"  对话ID: {request.conversation_id}")
    print(f"  对话条数: {len(request.dialogs)}")
    print(f"  质量: {request.quality}")
    print(f"  语言: {request.language}")
    print()
    
    try:
        # 调用生成服务
        print("开始生成回复...")
        response = await orchestrator.generate_reply(request)
        
        print("\n" + "=" * 80)
        print("生成结果:")
        print("=" * 80)
        print(f"回复文本: {response.reply_text}")
        print(f"置信度: {response.confidence}")
        print(f"亲密度(前): {response.intimacy_level_before}")
        print(f"亲密度(后): {response.intimacy_level_after}")
        print(f"模型: {response.model}")
        print(f"提供商: {response.provider}")
        print(f"成本: ${response.cost_usd:.4f}")
        print(f"是否降级: {response.fallback}")
        print("=" * 80)
        
        return response
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(test_real_mode())
