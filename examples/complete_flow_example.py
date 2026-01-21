"""完整流程示例 - 演示如何使用整个对话生成服务

这个示例展示了：
1. 初始化服务容器和所有依赖
2. 创建用户画像并设置显式标签
3. 分析对话场景
4. 通过 Orchestrator 生成回复
5. 查看完整的执行流程和结果

Requirements: 演示完整的对话生成流程
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
import re

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.container import ServiceContainer, ServiceMode
from app.core.config import settings
from app.models.api import GenerateReplyRequest
from app.models.schemas import Message
from app.services.user_profile_impl import UserProfileService
from app.services.llm_adapter import create_llm_adapter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """主函数 - 演示完整的对话生成流程"""
    
    print("=" * 80)
    print("对话生成服务 - 完整流程示例")
    print("=" * 80)
    print()

    # ========== 步骤 1: 初始化服务容器 ==========
    print("步骤 1: 初始化服务容器")
    print("-" * 80)

    settings.trace.enabled = True
    settings.trace.level = "debug"
    settings.trace.log_llm_prompt = True
    print(f"✓ Trace enabled: file={settings.trace.file_path}")
    print("✓ LLM prompt files will be written to logs/llm_prompts/<call_id>.txt")
    
    # 创建服务容器（使用 MOCK 模式以避免需要真实的 LLM API）
    container = ServiceContainer(mode=ServiceMode.REAL)
    
    # 获取各个服务实例
    llm_adapter = container.get_llm_adapter()
    user_profile_service = container.get_user_profile_service()
    orchestrator = container.create_orchestrator()
    
    print(f"✓ 服务容器模式: {container.mode.value}")
    print(f"✓ LLM Adapter: {type(llm_adapter).__name__}")
    print(f"✓ UserProfile Service: {type(user_profile_service).__name__}")
    print(f"✓ Orchestrator: {type(orchestrator).__name__}")
    print()
    
    # ========== 步骤 2: 设置用户画像 ==========
    print("步骤 2: 设置用户画像")
    print("-" * 80)
    
    user_id = "user_001"
    target_id = "target_001"
    conversation_id = "conv_001"
    
    # 设置用户的显式标签
    profile = await user_profile_service.set_explicit_tags(
        user_id=user_id,
        role=["恋爱教练", "情感顾问"],
        style=["幽默", "理性"],
        forbidden=["粗俗语言", "过度调侃"],
        intimacy=60.0,  # 亲密度 60/100
    )
    
    print(f"✓ 用户ID: {user_id}")
    print(f"✓ 角色人设: {profile.core_profile.explicit.role}")
    print(f"✓ 回复风格: {profile.core_profile.explicit.style}")
    print(f"✓ 禁止事项: {profile.core_profile.explicit.forbidden}")
    print(f"✓ 亲密度: {profile.core_profile.explicit.intimacy}/100")
    print()
    
    # ========== 步骤 3: 准备对话历史 ==========
    print("步骤 3: 准备对话历史")
    print("-" * 80)
    
    # 模拟一段对话历史
    messages = [
        Message(
            id="msg_001",
            speaker="user",
            content='''Hey Sarah, I noticed you have a photo with a copy of "Sapiens" on your bookshelf. Great book! What did you think of the author’s take on collective imagination?''',
            timestamp=datetime.now()
        ),
        Message(
            id="msg_002",
            speaker="Sarah",
            content='''Oh, wow, someone actually zoomed in! Most people just comment on the travel pics. I found that part fascinating—how stories and myths built human cooperation. Did you read the sequel, "Homo Deus," too?''',
            timestamp=datetime.now()
        ),
        Message(
            id="msg_003",
            speaker="user",
            content=''' I did, though it made me a bit anxious about the future, to be honest. Your travel pictures are amazing, by the way. The one in Iceland looks surreal. Was that the Golden Circle?''',
            timestamp=datetime.now()
        ),
        Message(
            id="msg_004",
            speaker="Sarah",
            content='''Good eye! Yes, that was Þingvellir National Park. The landscape feels like another planet. Do you travel often?''',
            timestamp=datetime.now()
        ),
        Message(
            id="msg_005",
            speaker="user",
            content='''I try to, when work allows. More of a mountain person—I just got back from hiking in the Rockies. Iceland is high on my list, though. Any must-see spots you’d recommend beyond the usual guides?''',
            timestamp=datetime.now()
        ),
        Message(
            id="msg_006",
            speaker="Sarah",
            content='''Definitely the Snaefellsnes peninsula. Fewer crowds, and you get volcanoes, black sand beaches, and lava fields all in one day. So, mountains over beaches for you?''',
            timestamp=datetime.now()
        ),
        Message(
            id="msg_007",
            speaker="user",
            content='''100%. There’s a silence in the mountains that I haven’t found anywhere else. Though I won’t say no to a good beach with a book. What’s your ideal trip—planned itinerary or spontaneous exploration?''',
            timestamp=datetime.now()
        ),
        Message(
            id="msg_008",
            speaker="Sarah",
            content='''A mix? I like having a rough plan so I don’t miss key things, but leaving room to get lost. Once in Lisbon, I skipped the tourist tower and spent an afternoon in a tiny tile-painting workshop instead. Best memory of the trip.''',
            timestamp=datetime.now()
        ),
    ]
    
    print(f"✓ 对话历史: {len(messages)} 条消息")
    for msg in messages:
        speaker_label = msg.speaker
        print(f"  [{speaker_label}] {msg.content[:50]}...")
    print()

    # ========== 步骤 3.1: 从对话中学习 Traits（用于生成 policy_block） ==========
    print("步骤 3.1: 从对话中学习 Traits（用于生成 policy_block）")
    print("-" * 80)

    selected_sentences: list[str] = []
    for message in messages:
        parts = [s.strip() for s in re.split(r"[.!?]+\s*", message.content) if s.strip()]
        selected_sentences.extend(parts)
    if len(selected_sentences) < 10:
        selected_sentences.extend([m.content.strip() for m in messages])

    await user_profile_service.learn_new_traits(
        user_id=user_id,
        selected_sentences=selected_sentences[:10],
        provider="dashscope",
        model="qwen-flash",
        store=True,
        map_to_standard=True,
    )

    print("✓ 已触发 trait 学习（trait_vector 将用于生成 policy_block）")
    print()
    
    # ========== 步骤 4: 分析对话场景 ==========
    print("步骤 4: 分析对话场景")
    print("-" * 80)
    print("✓ 场景分析将由 Orchestrator 在生成回复时完成（此处不额外调用 LLM）")
    print()
    
    # ========== 步骤 5: 通过 Orchestrator 生成回复 ==========
    print("步骤 5: 通过 Orchestrator 生成回复")
    print("-" * 80)

    dialogs = []
    for message in messages:
        dialogs.append({
            'speaker': message.speaker,
            'text': message.content
        })
    # 创建生成请求
    # print(dir(GenerateReplyRequest))
    request = GenerateReplyRequest(
        user_id=user_id,
        target_id=target_id,
        conversation_id=conversation_id,
        language="en",
        quality="normal",  # 使用 normal 质量
        force_regenerate=False,
        intimacy_value=60,
        dialogs = dialogs
    )
    print(request.dialogs)
    
    print(f"✓ 请求参数:")
    print(f"  - 用户ID: {request.user_id}")
    print(f"  - 对话ID: {request.conversation_id}")
    print(f"  - 质量等级: {request.quality}")
    print()
    
    # 调用 Orchestrator 生成回复
    print("正在生成回复...")
    response = await orchestrator.generate_reply(request)
    
    print()
    print("=" * 80)
    print("生成结果")
    print("=" * 80)
    print()
    print(f"回复内容:")
    print(f"  {response.reply_text}")
    print()
    print(f"元数据:")
    print(f"  - 置信度: {response.confidence:.2f}")
    print(f"  - 亲密度(前): {response.intimacy_level_before}/5")
    print(f"  - 亲密度(后): {response.intimacy_level_after}/5")
    print(f"  - 使用模型: {response.model}")
    print(f"  - 提供商: {response.provider}")
    print(f"  - 成本: ${response.cost_usd:.4f}")
    print(f"  - 是否降级: {response.fallback}")
    print()
    
    # ========== 步骤 6: 查看用户画像的完整信息 ==========
    print("步骤 6: 查看用户画像的完整信息")
    print("-" * 80)
    
    # 获取 LLM 友好的画像表示
    profile_dict = await user_profile_service.get_profile_for_llm(user_id)
    
    if profile_dict:
        print("用户画像 (LLM 格式):")
        print(f"  显式标签:")
        print(f"    - 回复风格: {profile_dict['explicit']['response_style']}")
        print(f"    - 禁止事项: {profile_dict['explicit']['forbidden']}")
        print(f"    - 角色人设: {profile_dict['explicit']['role']}")
        print(f"    - 亲密度: {profile_dict['explicit']['intimacy']}/100")
        
        if 'session' in profile_dict:
            print(f"  会话状态:")
            print(f"    - 当前目标: {profile_dict['session'].get('goal', 'N/A')}")
            print(f"    - 交互模式: {profile_dict['session'].get('mode', 'N/A')}")
            
            if 'scenario' in profile_dict['session']:
                scenario_info = profile_dict['session']['scenario']
                print(f"    - 场景风险: {scenario_info['risk_level']}")
                print(f"    - 关系阶段: {scenario_info['relationship_stage']}")
    print()
    
    # ========== 步骤 7: 从对话学习用户偏好 ==========
    print("步骤 7: 从对话学习用户偏好")
    print("-" * 80)
    
    # 在 Mock 模式下跳过 LLM 分析（避免需要真实 API）
    # 如果需要使用真实 LLM，请将 ServiceMode 改为 REAL 并配置 API 密钥
    print("✓ Mock 模式下跳过 LLM 偏好学习")
    print("  （如需使用，请切换到 REAL 模式并配置 API 密钥）")
    print()
    
    # ========== 完成 ==========
    print("=" * 80)
    print("示例完成！")
    print("=" * 80)
    print()
    print("总结:")
    print("1. ✓ 初始化了服务容器和所有依赖")
    print("2. ✓ 设置了用户画像的显式标签")
    print("3. ✓ 准备了对话历史数据")
    print("4. ✓ 分析了对话场景（Mock 模式）")
    print("5. ✓ 通过 Orchestrator 生成了回复")
    print("6. ✓ 查看了用户画像的完整信息")
    print("7. ✓ 完成演示（Mock 模式）")
    print()
    print("注意: 当前使用 Mock 模式，不需要真实 LLM API。")
    print("如需使用真实 LLM，请修改代码将 ServiceMode.MOCK 改为 ServiceMode.REAL")
    print("并配置 core/llm_adapter/config.yaml 中的 API 密钥。")
    print()
    print("完整流程演示结束。")


async def simple_example():
    """简化示例 - 最小化的使用流程"""
    
    print("\n" + "=" * 80)
    print("简化示例 - 最小化流程")
    print("=" * 80 + "\n")
    
    # 1. 创建服务容器
    container = ServiceContainer(mode=ServiceMode.REAL)
    orchestrator = container.create_orchestrator()
    
    # 2. 创建请求
    request = GenerateReplyRequest(
        user_id="user_simple",
        target_id="target_simple",
        conversation_id="conv_simple",
        quality="normal",
    )
    
    # 3. 生成回复
    print("生成回复中...")
    response = await orchestrator.generate_reply(request)
    
    # 4. 显示结果
    print(f"\n回复: {response.reply_text}")
    print(f"模型: {response.provider}/{response.model}")
    print(f"成本: ${response.cost_usd:.4f}\n")


async def mock_example():
    """Mock 模式示例 - 用于测试和开发"""
    
    print("\n" + "=" * 80)
    print("Mock 模式示例 - 用于测试和开发")
    print("=" * 80 + "\n")
    
    # 使用 Mock 模式（不需要真实的 LLM API）
    container = ServiceContainer(mode=ServiceMode.REAL)
    orchestrator = container.create_orchestrator()
    
    request = GenerateReplyRequest(
        user_id="user_mock",
        target_id="target_mock",
        conversation_id="conv_mock",
        quality="premium",
    )
    
    print("使用 Mock 服务生成回复...")
    response = await orchestrator.generate_reply(request)
    
    print(f"\n回复: {response.reply_text}")
    print(f"模型: {response.provider}/{response.model}")
    print(f"成本: ${response.cost_usd:.4f}")
    print(f"(这是 Mock 数据，不会调用真实的 LLM API)\n")


if __name__ == "__main__":
    # 运行完整示例
    asyncio.run(main())
    
    # 运行简化示例
    # asyncio.run(simple_example())
    
    # 运行 Mock 示例
    # asyncio.run(mock_example())
