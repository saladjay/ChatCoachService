"""测试场景分析器的新功能"""
import asyncio
from app.models.schemas import SceneAnalysisInput, Message
from app.services.scene_analyzer_impl import SceneAnalyzer
from app.services.llm_adapter import LLMAdapterImpl

async def test_scene_analyzer():
    # 初始化 LLM adapter
    llm_adapter = LLMAdapterImpl()
    
    # 创建场景分析器
    scene_analyzer = SceneAnalyzer(llm_adapter, provider="dashscope", model="qwen-flash")
    
    # 准备测试数据
    messages = [
        Message(id="1", speaker="user", content="Hey Sarah, I noticed you have a photo with a copy of 'Sapiens' on your bookshelf.", timestamp=None),
        Message(id="2", speaker="Sarah", content="Oh, wow, someone actually zoomed in! Most people just comment on the travel pics.", timestamp=None),
        Message(id="3", speaker="user", content="I did, though it made me a bit anxious about the future, to be honest.", timestamp=None),
    ]
    
    # 测试场景1: 用户期望亲密度高于当前亲密度（需要推进）
    print("=" * 60)
    print("测试场景1: 用户期望亲密度(70) > 当前亲密度(30) - 需要推进")
    print("=" * 60)
    input_data1 = SceneAnalysisInput(
        conversation_id="test_001",
        history_dialog=messages,
        history_topic_summary="双方讨论了书籍《Sapiens》，展现出对彼此兴趣的关注",
        current_conversation_summary="用户注意到Sarah的书架上有《Sapiens》这本书，Sarah表示惊讶有人注意到细节",
        current_conversation=messages,
        intimacy_value=70,  # 用户期望的亲密度
        current_intimacy_level=30,  # 当前分析的亲密度
    )
    
    result1 = await scene_analyzer.analyze_scene(input_data1)
    print(f"  关系状态: {result1.relationship_state}")
    print(f"  场景: {result1.scenario}")
    print(f"  亲密度: {result1.intimacy_level}")
    print(f"  当前情景: {result1.current_scenario}")
    print(f"  推荐情景: {result1.recommended_scenario}")
    print(f"  推荐策略: {result1.recommended_strategies}")
    print(f"  风险标记: {result1.risk_flags}")
    
    # 测试场景2: 用户期望亲密度低于当前亲密度（需要冷却）
    print("\n" + "=" * 60)
    print("测试场景2: 用户期望亲密度(30) < 当前亲密度(80) - 需要冷却")
    print("=" * 60)
    input_data2 = SceneAnalysisInput(
        conversation_id="test_002",
        history_dialog=messages,
        history_topic_summary="双方讨论了书籍《Sapiens》",
        current_conversation_summary="对话进展顺利",
        current_conversation=messages,
        intimacy_value=30,  # 用户期望的亲密度
        current_intimacy_level=80,  # 当前分析的亲密度
    )
    
    result2 = await scene_analyzer.analyze_scene(input_data2)
    print(f"  关系状态: {result2.relationship_state}")
    print(f"  场景: {result2.scenario}")
    print(f"  亲密度: {result2.intimacy_level}")
    print(f"  当前情景: {result2.current_scenario}")
    print(f"  推荐情景: {result2.recommended_scenario}")
    print(f"  推荐策略: {result2.recommended_strategies}")
    print(f"  风险标记: {result2.risk_flags}")
    
    # 测试场景3: 亲密度相近（维持）
    print("\n" + "=" * 60)
    print("测试场景3: 用户期望亲密度(50) ≈ 当前亲密度(48) - 维持")
    print("=" * 60)
    input_data3 = SceneAnalysisInput(
        conversation_id="test_003",
        history_dialog=messages,
        history_topic_summary="双方讨论了书籍《Sapiens》",
        current_conversation_summary="对话进展顺利",
        current_conversation=messages,
        intimacy_value=50,  # 用户期望的亲密度
        current_intimacy_level=48,  # 当前分析的亲密度
    )
    
    result3 = await scene_analyzer.analyze_scene(input_data3)
    print(f"  关系状态: {result3.relationship_state}")
    print(f"  场景: {result3.scenario}")
    print(f"  亲密度: {result3.intimacy_level}")
    print(f"  当前情景: {result3.current_scenario}")
    print(f"  推荐情景: {result3.recommended_scenario}")
    print(f"  推荐策略: {result3.recommended_strategies}")
    print(f"  风险标记: {result3.risk_flags}")

if __name__ == "__main__":
    asyncio.run(test_scene_analyzer())
