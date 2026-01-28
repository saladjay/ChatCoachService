"""
用户画像基础示例 - 不需要 LLM API

演示 UserProfileService 的基本功能：
1. 创建和管理用户画像
2. 设置显式标签
3. 场景分析和策略推荐
4. 行为信号更新
5. 偏好学习（用户直接输入）
6. 序列化输出

运行方式：
    python examples/userprofile_basic_example.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.user_profile_impl import (
    UserProfileService,
    ScenarioRiskLevel,
    LearnedPreference,
    PreferenceSource,
)
from app.models.schemas import Message


def _style_from_profile(profile) -> str:
    if profile is not None and profile.explicit and profile.explicit.style:
        return profile.explicit.style[0]
    return "理性"


def _pacing_from_profile(profile) -> str:
    if profile is None or not profile.session_state or not profile.session_state.scenario:
        return "normal"
    return {
        ScenarioRiskLevel.SAFE: "slow",
        ScenarioRiskLevel.BALANCED: "normal",
        ScenarioRiskLevel.RISKY: "fast",
        ScenarioRiskLevel.RECOVERY: "slow",
        ScenarioRiskLevel.NEGATIVE: "slow",
    }.get(profile.session_state.scenario.risk_level, "normal")


def _risk_tolerance_from_profile(profile) -> str:
    if profile is None or not profile.session_state or not profile.session_state.scenario:
        return "medium"
    return {
        ScenarioRiskLevel.SAFE: "low",
        ScenarioRiskLevel.BALANCED: "medium",
        ScenarioRiskLevel.RISKY: "high",
        ScenarioRiskLevel.RECOVERY: "low",
        ScenarioRiskLevel.NEGATIVE: "low",
    }.get(profile.session_state.scenario.risk_level, "medium")


async def example_basic_profile():
    """基础画像操作示例"""
    print("\n" + "=" * 50)
    print("📌 示例 1: 基础画像操作")
    print("=" * 50)
    
    svc = UserProfileService()
    user_id = "user_001"
    
    # 创建画像
    profile = await svc.create_profile(user_id)
    print(f"\n✅ 创建画像: {profile.user_id}")
    print(f"   默认风格: {_style_from_profile(profile)}")
    print(f"   默认节奏: {_pacing_from_profile(profile)}")
    print(f"   默认风险容忍: {_risk_tolerance_from_profile(profile)}")
    
    # 获取画像
    profile = await svc.get_profile(user_id)
    print(f"\n📖 获取画像: {profile.user_id}")
    
    # 更新画像
    if profile.explicit:
        profile.explicit.style = ["幽默"]
    await svc.update_profile(profile)
    
    updated = await svc.get_profile(user_id)
    print(f"\n🔄 更新后风格: {_style_from_profile(updated)}")


async def example_explicit_tags():
    """显式标签管理示例"""
    print("\n" + "=" * 50)
    print("📌 示例 2: 显式标签管理")
    print("=" * 50)
    
    svc = UserProfileService()
    user_id = "user_002"
    
    # 快速设置画像
    profile = await svc.set_explicit_tags(
        user_id=user_id,
        role=["温柔大姐姐", "知心朋友"],
        style=["感性", "温暖"],
        forbidden=["说教", "冷漠", "敷衍"],
        intimacy=65.0,
    )
    
    print(f"\n✅ 设置显式标签:")
    print(f"   角色: {profile.explicit.role}")
    print(f"   风格: {profile.explicit.style}")
    print(f"   禁止: {profile.explicit.forbidden}")
    print(f"   亲密度: {profile.explicit.intimacy}")
    
    # 添加自定义标签
    await svc.add_tag(user_id, "preference", "topic", "旅游")
    await svc.add_tag(user_id, "preference", "food", "川菜")
    await svc.add_tag(user_id, "personality", "mbti", "ENFP")
    
    # 获取标签
    tags = await svc.get_tags(user_id)
    print(f"\n📋 所有标签:")
    for tag in tags:
        print(f"   {tag['category']}/{tag['name']}: {tag['value']}")


async def example_scenario_analysis():
    """场景分析示例（手动设置，不使用 LLM）"""
    print("\n" + "=" * 50)
    print("📌 示例 3: 场景分析与策略推荐（手动模式）")
    print("=" * 50)
    
    svc = UserProfileService()
    user_id = "user_003"
    conversation_id = "conv_001"
    
    # 模拟对话历史
    messages = [
        Message(id="1", speaker="target", content="你好呀~", timestamp=datetime.now()),
        Message(id="2", speaker="user", content="你好！很高兴认识你", timestamp=datetime.now()),
        Message(id="3", speaker="target", content="我看你资料说喜欢旅游？", timestamp=datetime.now()),
        Message(id="4", speaker="user", content="对的，我特别喜欢去海边", timestamp=datetime.now()),
    ]
    
    # 场景1: 破冰阶段 (Safe)
    print("\n🎭 场景1: 破冰阶段")
    profile = await svc.analyze_scenario_manual(
        user_id=user_id,
        conversation_id=conversation_id,
        messages=messages,
        risk_level=ScenarioRiskLevel.SAFE,
        recommended_strategies=[
            "situational_comment",
            "light_humor",
            "neutral_open_question",
            "pace_matching",
        ],
        relationship_stage="stranger",
        emotional_tone="positive",
    )
    
    strategies = await svc.get_recommended_strategies(user_id)
    print(f"   风险等级: SAFE")
    print(f"   推荐策略: {strategies}")
    print(f"   画像节奏: {_pacing_from_profile(profile)}")
    print(f"   风险容忍: {_risk_tolerance_from_profile(profile)}")
    
    # 场景2: 推进阶段 (Balanced)
    print("\n🎭 场景2: 推进阶段")
    profile = await svc.analyze_scenario_manual(
        user_id=user_id,
        conversation_id=conversation_id,
        messages=messages,
        risk_level=ScenarioRiskLevel.BALANCED,
        recommended_strategies=[
            "playful_tease",
            "direct_compliment",
            "emotional_resonance",
            "story_snippet",
        ],
        relationship_stage="acquaintance",
        emotional_tone="positive",
    )
    
    strategies = await svc.get_recommended_strategies(user_id)
    print(f"   风险等级: BALANCED")
    print(f"   推荐策略: {strategies}")
    print(f"   画像节奏: {_pacing_from_profile(profile)}")
    print(f"   风险容忍: {_risk_tolerance_from_profile(profile)}")
    
    # 场景3: 修复阶段 (Recovery)
    print("\n🎭 场景3: 修复阶段")
    profile = await svc.analyze_scenario_manual(
        user_id=user_id,
        conversation_id=conversation_id,
        messages=messages,
        risk_level=ScenarioRiskLevel.RECOVERY,
        recommended_strategies=[
            "tension_release",
            "boundary_respect",
            "emotional_deescalation",
        ],
        avoid_patterns=["validation_seeking", "over_explaining"],
        relationship_stage="acquaintance",
        emotional_tone="tense",
    )
    
    strategies = await svc.get_recommended_strategies(user_id)
    avoid = await svc.get_avoid_patterns(user_id)
    print(f"   风险等级: RECOVERY")
    print(f"   推荐策略: {strategies}")
    print(f"   需要回避: {avoid}")


async def example_behavior_signals():
    """行为信号更新示例"""
    print("\n" + "=" * 50)
    print("📌 示例 4: 行为信号学习")
    print("=" * 50)
    
    svc = UserProfileService()
    user_id = "user_004"
    
    # 创建初始画像
    await svc.create_profile(user_id)
    
    # 模拟用户行为信号
    print("\n📊 模拟用户行为:")
    
    # 用户要求示例
    print("   - 用户要求示例...")
    await svc.update_from_behavior(
        user_id=user_id,
        asked_for_examples=True,
        message_length="medium",
    )
    
    # 用户追问原因
    print("   - 用户追问原因...")
    await svc.update_from_behavior(
        user_id=user_id,
        asked_why=True,
        message_length="long",
    )
    
    # 用户发送长消息
    print("   - 用户发送长消息...")
    await svc.update_from_behavior(
        user_id=user_id,
        message_length="long",
    )
    
    # 获取更新后的画像
    profile = await svc.get_profile(user_id)
    if profile and profile.behavioral:
        behavioral = profile.behavioral
        print(f"\n📈 学习到的偏好:")
        print(f"   深度偏好: {behavioral.depth_preference.value:.2f}")
        print(f"   示例需求: {behavioral.example_need.value:.2f}")
        print(f"   长回复偏好: {behavioral.long_response_preference.value:.2f}")


async def example_user_input_preferences():
    """用户直接输入偏好示例"""
    print("\n" + "=" * 50)
    print("📌 示例 5: 用户直接输入偏好")
    print("=" * 50)
    
    svc = UserProfileService()
    user_id = "user_005_pref"
    
    # 创建初始画像
    await svc.create_profile(user_id)
    
    print("\n📝 添加用户直接输入的偏好:")
    
    # 用户明确表示喜欢详细回复
    prefs = await svc.add_user_preference(
        user_id=user_id,
        key="detail_level",
        value=0.9,
        description="用户明确表示喜欢详细的回复",
    )
    print(f"   - 添加 detail_level = 0.9")
    
    # 用户表示喜欢幽默风格
    prefs = await svc.add_user_preference(
        user_id=user_id,
        key="humor_preference",
        value=0.8,
        description="用户喜欢幽默的沟通方式",
    )
    print(f"   - 添加 humor_preference = 0.8")
    
    # 用户表示不喜欢太正式
    prefs = await svc.add_user_preference(
        user_id=user_id,
        key="formality",
        value=0.3,
        description="用户偏好轻松随意的交流",
    )
    print(f"   - 添加 formality = 0.3")
    
    # 获取所有学习到的偏好
    learned_prefs = await svc.get_learned_preferences(user_id)
    
    print(f"\n📋 用户偏好列表 (共 {len(learned_prefs)} 项):")
    for pref in learned_prefs:
        print(f"   {pref.key}:")
        print(f"     值: {pref.value:.2f}")
        print(f"     置信度: {pref.confidence:.2f}")
        print(f"     来源: {pref.source.value}")
        print(f"     证据: {pref.evidence[0] if pref.evidence else 'N/A'}")


async def example_serialization():
    """序列化输出示例"""
    print("\n" + "=" * 50)
    print("📌 示例 6: 序列化输出")
    print("=" * 50)
    
    svc = UserProfileService()
    user_id = "user_005"
    
    # 设置完整画像
    await svc.set_explicit_tags(
        user_id=user_id,
        role=["贴心男友", "幽默达人"],
        style=["幽默", "温暖"],
        forbidden=["冷漠", "敷衍"],
        intimacy=70.0,
    )
    
    # 添加场景（使用手动模式，不需要 LLM）
    await svc.analyze_scenario_manual(
        user_id=user_id,
        conversation_id="conv_001",
        messages=[],
        risk_level=ScenarioRiskLevel.BALANCED,
        recommended_strategies=["playful_tease", "emotional_resonance"],
        relationship_stage="friend",
        emotional_tone="positive",
    )
    
    # 1. LLM 字典格式
    llm_profile = await svc.get_profile_for_llm(user_id)
    print("\n📋 LLM 字典格式:")
    print(json.dumps(llm_profile, ensure_ascii=False, indent=2))
    
    # 2. Prompt 格式
    prompt = await svc.serialize_to_prompt(user_id, max_tokens=300)
    print("\n📝 Prompt 格式:")
    print(prompt)
    
    # 3. Tool 格式 (Function Calling)
    tool_schema = await svc.serialize_to_tool(user_id, include_confidence=True)
    print("\n🔧 Tool 格式:")
    print(json.dumps(tool_schema, ensure_ascii=False, indent=2))


async def example_context_analysis():
    """上下文分析示例"""
    print("\n" + "=" * 50)
    print("📌 示例 7: 上下文分析")
    print("=" * 50)
    
    svc = UserProfileService()
    user_id = "user_006"
    conversation_id = "conv_001"
    
    # 创建画像
    await svc.create_profile(user_id)
    
    # 模拟对话
    messages = [
        Message(id="1", speaker="user", content="你好，我想了解一下Python编程", timestamp=datetime.now()),
        Message(id="2", speaker="target", content="好的，你想学习哪方面？", timestamp=datetime.now()),
        Message(id="3", speaker="user", content="我想学习怎么写一个爬虫，能给我举个例子吗？", timestamp=datetime.now()),
        Message(id="4", speaker="target", content="当然可以，我来给你演示一下", timestamp=datetime.now()),
        Message(id="5", speaker="user", content="为什么要用requests库？有什么好处？", timestamp=datetime.now()),
    ]
    
    # 分析上下文
    overlay = await svc.analyze_context(
        user_id=user_id,
        conversation_id=conversation_id,
        messages=messages,
    )
    
    print(f"\n🔍 上下文分析结果:")
    print(f"   相关维度: {overlay.relevant_dimensions}")
    print(f"   推断意图: {overlay.inferred_intent}")
    print(f"   推断话题: {overlay.inferred_topics}")
    print(f"   权重调整: {overlay.adjusted_weights}")
    print(f"   临时属性: {overlay.temporary_attributes}")


async def example_multi_persona():
    """多人设示例"""
    print("\n" + "=" * 50)
    print("📌 示例 8: 多人设场景")
    print("=" * 50)
    
    svc = UserProfileService()
    
    # 人设1: 文静妹子
    user_id_1 = "persona_gentle"
    await svc.set_explicit_tags(
        user_id=user_id_1,
        role=["文静女生", "书香气质"],
        style=["克制", "温柔"],
        forbidden=["粗鲁", "急躁"],
        intimacy=40.0,
    )
    
    # 人设2: 活泼妹子
    user_id_2 = "persona_lively"
    await svc.set_explicit_tags(
        user_id=user_id_2,
        role=["活泼女生", "开朗性格"],
        style=["幽默", "热情"],
        forbidden=["冷漠", "无聊"],
        intimacy=60.0,
    )
    
    # 人设3: 知性姐姐
    user_id_3 = "persona_intellectual"
    await svc.set_explicit_tags(
        user_id=user_id_3,
        role=["知性姐姐", "成熟稳重"],
        style=["理性", "温暖"],
        forbidden=["幼稚", "轻浮"],
        intimacy=55.0,
    )
    print("\n👥 三种人设对比:")
    
    for name, user_id in [
        ("人设 1", user_id_1),
        ("人设 2", user_id_2),
        ("人设 3", user_id_3),
    ]:
        profile = await svc.get_profile(user_id)
        print(f"\n   {name}:")
        print(f"     角色: {profile.explicit.role}")
        print(f"     风格: {profile.explicit.style}")
        print(f"     亲密度: {profile.explicit.intimacy}")
        print(f"     风格推断: {_style_from_profile(profile)}")
        print(f"     节奏推断: {_pacing_from_profile(profile)}")
        print(f"     风险评估: {_risk_tolerance_from_profile(profile)}")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("🎯 UserProfile 服务完整示例")
    print("=" * 60)
    
    await example_basic_profile()
    await example_explicit_tags()
    await example_scenario_analysis()
    await example_behavior_signals()
    await example_user_input_preferences()
    await example_serialization()
    await example_context_analysis()
    await example_multi_persona()
    
    print("\n" + "=" * 60)
    print("✅ 所有示例完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
