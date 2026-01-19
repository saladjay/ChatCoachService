"""
使用 LLM 构建 UserProfile 的示例

本示例演示如何：
1. 使用 app/services/llm_adapter 调用 LLM（支持指定平台）
2. 基于对话历史分析用户画像和场景
3. 使用 core/user_profile 的完整画像服务
4. 使用 LLM 从对话上下文学习用户偏好

运行方式：
    python examples/qwen_userprofile_example.py
    python examples/qwen_userprofile_example.py --provider dashscope --model qwen-plus
    python examples/qwen_userprofile_example.py --provider openai --model gpt-4o
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.llm_adapter import LLMAdapterImpl, LLMCall, SUPPORTED_PROVIDERS
from app.services.user_profile_impl import UserProfileService, ScenarioRiskLevel
from app.models.schemas import Message


# ============== Prompt 模板 ==============

PERSONA_ANALYSIS_PROMPT = """你是一个用户画像分析专家。请根据以下对话历史，分析用户的性格特征和当前对话场景。

## 对话历史
{conversation}

## 分析维度

### 1. 用户风格 (style)
- 理性：逻辑清晰，注重事实和数据
- 感性：情感丰富，注重感受和体验
- 幽默：轻松诙谐，善于调节气氛
- 克制：内敛含蓄，表达谨慎

### 2. 交流节奏 (pacing)
- slow：喜欢深入交流，不急于推进
- normal：正常节奏，适度推进
- fast：喜欢快节奏，直接高效

### 3. 风险偏好 (risk_tolerance)
- low：保守谨慎，避免冒险话题
- medium：适度开放，可接受一定风险
- high：大胆开放，愿意尝试新话题

### 4. 场景风险等级 (risk_level)
- safe：陌生阶段，低容错，需要保守策略
- balanced：推进关系阶段，可以适度冒险
- risky：关系亲密，高容错，可以大胆尝试
- recovery：关系修复阶段，需要缓和策略

### 5. 关系阶段 (relationship_stage)
- stranger：陌生人
- acquaintance：熟人
- friend：朋友
- intimate：亲密关系

### 6. 推荐策略 (recommended_strategies)
根据场景选择合适的策略：
- Safe 策略：situational_comment, light_humor, neutral_open_question, empathetic_ack, pace_matching
- Balanced 策略：playful_tease, direct_compliment, emotional_resonance, story_snippet, flirt_with_escape
- Recovery 策略：tension_release, boundary_respect, misstep_repair

## 输出格式
请严格按照以下 JSON 格式输出，不要包含其他内容：
{{
    "style": "理性|感性|幽默|克制",
    "pacing": "slow|normal|fast",
    "risk_tolerance": "low|medium|high",
    "risk_level": "safe|balanced|risky|recovery",
    "relationship_stage": "stranger|acquaintance|friend|intimate",
    "emotional_tone": "positive|neutral|negative|tense",
    "recommended_strategies": ["策略1", "策略2", "策略3"],
    "avoid_patterns": ["需要回避的模式"],
    "confidence": 0.0-1.0,
    "analysis": "简要分析说明"
}}
"""


def format_conversation(messages: list[Message]) -> str:
    """格式化对话历史为文本"""
    lines = []
    for msg in messages:
        speaker = "用户" if msg.speaker == "user" else "对方"
        lines.append(f"{speaker}: {msg.content}")
    return "\n".join(lines)


def parse_llm_response(response_text: str) -> dict:
    """解析 LLM 返回的 JSON 响应"""
    text = response_text.strip()
    
    # 处理 markdown 代码块
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()
    
    # 提取 JSON 对象
    if "{" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        text = text[start:end]
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析失败: {e}")
        return {
            "style": "理性",
            "pacing": "normal",
            "risk_tolerance": "medium",
            "risk_level": "safe",
            "relationship_stage": "stranger",
            "emotional_tone": "neutral",
            "recommended_strategies": ["pace_matching", "empathetic_ack"],
            "avoid_patterns": [],
            "confidence": 0.5,
            "analysis": "解析失败，使用默认值"
        }


async def analyze_with_llm(
    llm_adapter: LLMAdapterImpl,
    user_id: str,
    messages: list[Message],
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """使用 LLM 分析用户画像和场景
    
    Args:
        llm_adapter: LLM 适配器
        user_id: 用户ID
        messages: 对话消息列表
        provider: 可选，指定平台 (dashscope/openai/gemini 等)
        model: 可选，指定模型 (qwen-plus/gpt-4o 等)
    """
    conversation_text = format_conversation(messages)
    prompt = PERSONA_ANALYSIS_PROMPT.format(conversation=conversation_text)
    
    print("\n📝 发送分析请求到 LLM...")
    print(f"   对话轮数: {len(messages)}")
    
    # 创建 LLM 调用请求
    llm_call = LLMCall(
        task_type="persona",
        prompt=prompt,
        quality="normal",
        user_id=user_id,
        provider='dashscope',
        model='qwen-flash',
    )
    
    result = await llm_adapter.call(llm_call)
    
    print(f"   平台: {result.provider}")
    print(f"   模型: {result.model}")
    print(f"   Token: {result.input_tokens} + {result.output_tokens}")
    print(f"   成本: ${result.cost_usd:.6f}")
    
    parsed = parse_llm_response(result.text)
    parsed["raw_response"] = result.text
    
    return parsed


async def run_example(provider: str | None = None, model: str | None = None, verbose: bool = False):
    """运行示例
    
    Args:
        provider: 可选，指定平台
        model: 可选，指定模型
        verbose: 是否显示详细输出
    """
    print("=" * 60)
    print("🎯 LLM + UserProfile 完整示例")
    print("=" * 60)
    
    # 显示使用的平台信息
    if provider and model:
        print(f"\n📌 使用指定平台: {provider} / {model}")
    else:
        print("\n📌 使用默认路由 (基于 quality 自动选择)")
    
    print(f"   支持的平台: {SUPPORTED_PROVIDERS}")
    
    # 初始化 LLM Adapter
    llm_adapter = LLMAdapterImpl()
    
    # 使用 LLM adapter 初始化 UserProfileService
    user_profile_service = UserProfileService(llm_adapter=llm_adapter)
    
    user_id = "demo_user_001"
    conversation_id = "conv_001"
    
    # 示例对话
    sample_messages = [
        Message(
            id="msg_001",
            speaker="target",
            content="你好呀，看到你的资料觉得挺有意思的",
            timestamp=datetime.now()
        ),
        Message(
            id="msg_002",
            speaker="user",
            content="哈哈谢谢！你的照片也很好看，是在哪里拍的？",
            timestamp=datetime.now()
        ),
        Message(
            id="msg_003",
            speaker="target",
            content="是上个月去云南旅游的时候拍的，那边风景特别美",
            timestamp=datetime.now()
        ),
        Message(
            id="msg_004",
            speaker="user",
            content="云南确实不错，我之前去过大理，洱海边骑车特别舒服。你喜欢旅游吗？",
            timestamp=datetime.now()
        ),
        Message(
            id="msg_005",
            speaker="target",
            content="超喜欢的！每年都会安排几次出行，你呢？",
            timestamp=datetime.now()
        ),
        Message(
            id="msg_006",
            speaker="user",
            content="我也是，不过工作比较忙，一般就周末短途游。对了，你平时除了旅游还有什么爱好？",
            timestamp=datetime.now()
        ),
        Message(
            id="msg_007",
            speaker="target",
            content="我喜欢看书和做饭，周末会尝试做一些新菜式",
            timestamp=datetime.now()
        ),
        Message(
            id="msg_008",
            speaker="user",
            content="哇，会做饭太棒了！我厨艺一般，不过很喜欢吃😄 你最拿手的菜是什么？",
            timestamp=datetime.now()
        ),
    ]
    
    print("\n📜 对话历史:")
    print("-" * 40)
    for msg in sample_messages:
        speaker = "👤 用户" if msg.speaker == "user" else "👩 对方"
        print(f"{speaker}: {msg.content}")
    print("-" * 40)
    
    try:
        # 1. 使用 LLM 分析场景
        print("\n" + "=" * 50)
        print("📊 第一步: 场景分析")
        print("=" * 50)
        
        analysis = await analyze_with_llm(
            llm_adapter=llm_adapter,
            user_id=user_id,
            messages=sample_messages,
            provider=provider,
            model=model,
        )
        
        print("\n📊 LLM 分析结果:")
        print("-" * 40)
        print(f"   沟通风格: {analysis.get('style', 'N/A')}")
        print(f"   交流节奏: {analysis.get('pacing', 'N/A')}")
        print(f"   风险偏好: {analysis.get('risk_tolerance', 'N/A')}")
        print(f"   场景风险: {analysis.get('risk_level', 'N/A')}")
        print(f"   关系阶段: {analysis.get('relationship_stage', 'N/A')}")
        print(f"   情绪基调: {analysis.get('emotional_tone', 'N/A')}")
        print(f"   置信度: {analysis.get('confidence', 0):.2f}")
        print(f"   分析说明: {analysis.get('analysis', 'N/A')}")
        
        print("\n   推荐策略:")
        for strategy in analysis.get('recommended_strategies', []):
            print(f"     - {strategy}")
        
        if analysis.get('avoid_patterns'):
            print("\n   需要回避:")
            for pattern in analysis.get('avoid_patterns', []):
                print(f"     - {pattern}")
        
        # 2. 更新 UserProfile 服务
        risk_level_map = {
            "safe": ScenarioRiskLevel.SAFE,
            "balanced": ScenarioRiskLevel.BALANCED,
            "risky": ScenarioRiskLevel.RISKY,
            "recovery": ScenarioRiskLevel.RECOVERY,
        }
        risk_level = risk_level_map.get(
            analysis.get('risk_level', 'safe'),
            ScenarioRiskLevel.SAFE
        )
        
        # 设置显式标签
        await user_profile_service.set_explicit_tags(
            user_id=user_id,
            style=[analysis.get('style', '理性')],
            role=["约会对象"],
            intimacy=50.0,
        )

        # 使用 LLM 分析场景并更新（现在 analyze_scenario 会自动调用 LLM）
        print("\n📝 调用 LLM 分析场景...")
        profile = await user_profile_service.analyze_scenario(
            user_id=user_id,
            conversation_id=conversation_id,
            messages=sample_messages,
            provider='dashscope',
            model='qwen-flash'
        )
        
        # 获取场景分析结果
        if profile.core_profile and profile.core_profile.session_state:
            scenario = profile.core_profile.session_state.scenario
            print("\n📊 场景分析结果:")
            print(f"   风险等级: {scenario.risk_level.value}")
            print(f"   关系阶段: {scenario.relationship_stage}")
            print(f"   情绪基调: {scenario.emotional_tone}")
            print(f"   推荐策略: {scenario.recommended_strategies}")
            if scenario.avoid_patterns:
                print(f"   需要回避: {scenario.avoid_patterns}")
        
        print("\n✅ 用户画像已更新")
        print(f"   user_id: {profile.user_id}")
        print(f"   style: {profile.style}")
        print(f"   pacing: {profile.pacing}")
        print(f"   risk_tolerance: {profile.risk_tolerance}")
        
        # 3. 使用 LLM 从对话学习用户偏好
        print("\n" + "=" * 50)
        print("🧠 第二步: 从对话学习用户偏好")
        print("=" * 50)
        
        print("\n📝 调用 LLM 分析对话偏好...")
        learned_preferences = await user_profile_service.learn_preferences_from_conversation(
            user_id=user_id,
            messages=sample_messages,
        )
        
        print(f"\n📋 学习到的偏好 (共 {len(learned_preferences)} 项):")
        print("-" * 40)
        for pref in learned_preferences:
            print(f"   {pref.key}:")
            print(f"     值: {pref.value:.2f}")
            print(f"     置信度: {pref.confidence:.2f}")
            print(f"     来源: {pref.source.value}")
        
        # 4. 获取所有学习到的偏好
        all_preferences = await user_profile_service.get_learned_preferences(user_id)
        print(f"\n📊 用户偏好汇总 (共 {len(all_preferences)} 项):")
        for pref in all_preferences:
            bar = "█" * int(pref.value * 10) + "░" * (10 - int(pref.value * 10))
            print(f"   {pref.key}: [{bar}] {pref.value:.2f}")
        
        # 5. 获取 LLM 友好的画像
        print("\n" + "=" * 50)
        print("📋 第三步: 序列化输出")
        print("=" * 50)
        
        llm_profile = await user_profile_service.get_profile_for_llm(user_id)
        if llm_profile:
            print("\n📋 LLM 友好的画像格式:")
            print("-" * 40)
            print(json.dumps(llm_profile, ensure_ascii=False, indent=2))
        
        # 6. 获取推荐策略
        strategies = await user_profile_service.get_recommended_strategies(user_id)
        if strategies:
            print("\n🎯 当前推荐策略:")
            for s in strategies:
                print(f"   - {s}")
        
        # 7. 序列化为 Prompt 格式
        prompt_text = await user_profile_service.serialize_to_prompt(user_id)
        if prompt_text:
            print("\n📝 Prompt 格式画像:")
            print("-" * 40)
            print(prompt_text)
        
        # 8. 显示使用统计
        usage = llm_adapter.get_user_usage(user_id)
        print("\n📈 LLM 使用统计:")
        print(f"   总调用次数: {usage['total_calls']}")
        print(f"   总输入 Token: {usage['total_input_tokens']}")
        print(f"   总输出 Token: {usage['total_output_tokens']}")
        print(f"   总成本: ${usage['total_cost_usd']:.6f}")
        
        # 显示原始响应（调试用）
        if verbose:
            print("\n🔍 LLM 原始响应:")
            print("-" * 40)
            print(analysis.get("raw_response", "N/A"))
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="使用 LLM 构建 UserProfile 的示例",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认路由
  python examples/qwen_userprofile_example.py
  
  # 指定使用 DashScope 的 qwen-plus
  python examples/qwen_userprofile_example.py --provider dashscope --model qwen-plus
  
  # 指定使用 OpenAI 的 gpt-4o
  python examples/qwen_userprofile_example.py --provider openai --model gpt-4o
  
  # 指定使用 Gemini
  python examples/qwen_userprofile_example.py --provider gemini --model gemini-1.5-flash
  
  # 显示详细输出
  python examples/qwen_userprofile_example.py --verbose
        """
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=SUPPORTED_PROVIDERS,
        help=f"指定 LLM 平台: {SUPPORTED_PROVIDERS}",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="指定模型名称 (如 qwen-plus, gpt-4o, gemini-1.5-flash)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细输出",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # 验证参数
    if args.provider and not args.model:
        print("❌ 错误: 指定 --provider 时必须同时指定 --model")
        sys.exit(1)
    if args.model and not args.provider:
        print("❌ 错误: 指定 --model 时必须同时指定 --provider")
        sys.exit(1)
    
    asyncio.run(run_example(
        provider=args.provider,
        model=args.model,
        verbose=args.verbose,
    ))
