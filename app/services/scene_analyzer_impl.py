from app.models.schemas import (
    SceneAnalysisInput,
    SceneAnalysisResult,
    Message,
)
from app.services.base import (
    BaseSceneAnalyzer,
)
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.prompt import SCENARIO_PROMPT
import json


class SceneAnalyzer(BaseSceneAnalyzer):
    """Scene analysis service implementation using LLM.
    
    Analyzes conversation to determine:
    - Current scenario (current interaction strategy level)
    - Recommended scenario (suggested strategy level for next interaction)
    - Recommended strategies (3 specific strategy codes)
    """
    
    def __init__(self, llm_adapter: BaseLLMAdapter, provider: str | None = None, model: str | None = None):
        """Initialize SceneAnalyzer with LLM adapter.
        
        Args:
            llm_adapter: LLM adapter for analyzing conversation context
            provider: Optional LLM provider (e.g., "dashscope", "openai")
            model: Optional LLM model name
        """
        self._llm_adapter = llm_adapter
        self.provider = provider or "dashscope"
        self.model = model or "qwen-flash"

    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        """Analyze conversation scene using LLM.
        
        Args:
            input: Scene analysis input containing conversation history and summaries.
        
        Returns:
            SceneAnalysisResult with current scenario, recommended scenario, and strategies.
        """
        # 构建对话文本
        conversation_text = self._format_conversation(input)
        
        # 调用 LLM 分析场景
        prompt = SCENARIO_PROMPT.format(conversation=conversation_text)
        llm_call = LLMCall(
            task_type="scene",
            prompt=prompt,
            quality="normal",
            user_id="system",
            provider=self.provider,
            model=self.model
        )
        
        result = await self._llm_adapter.call(llm_call)
        
        # 解析 LLM 返回的 JSON
        analysis = self._parse_response(result.text)
        
        # 根据亲密度计算 relationship_state 和 risk_flags
        relationship_state = self._calculate_relationship_state(
            input.intimacy_value, 
            input.current_intimacy_level
        )
        risk_flags = self._calculate_risk_flags(
            input.intimacy_value,
            input.current_intimacy_level
        )
        
        # 构建返回结果
        return SceneAnalysisResult(
            relationship_state=relationship_state,
            scenario=analysis.get("recommended_scenario", "平衡/中风险策略"),  # 使用推荐场景
            intimacy_level=input.intimacy_value,  # 使用用户设置的亲密度
            risk_flags=risk_flags,
            current_scenario=analysis.get("current_scenario", ""),
            recommended_scenario=analysis.get("recommended_scenario", ""),
            recommended_strategies=analysis.get("recommended_strategy", []),
        )
    
    def _calculate_relationship_state(
        self, 
        intimacy_value: int, 
        current_intimacy_level: int
    ) -> str:
        """根据用户设置的亲密度和当前亲密度计算关系状态.
        
        Args:
            intimacy_value: 用户设置的亲密度 (0-101)
            current_intimacy_level: 当前分析的亲密度 (0-101)
        
        Returns:
            关系状态: "破冰", "推进", "冷却", "维持"
        """
        diff = intimacy_value - current_intimacy_level
        
        # 如果当前亲密度低于用户期望，需要推进
        if diff > 10:
            if current_intimacy_level < 40:
                return "破冰"  # 低亲密度阶段，需要破冰
            else:
                return "推进"  # 中高亲密度阶段，需要推进
        
        # 如果当前亲密度高于用户期望，需要冷却
        elif diff < -10:
            return "冷却"
        
        # 亲密度相近，维持现状
        else:
            return "维持"
    
    def _calculate_risk_flags(
        self,
        intimacy_value: int,
        current_intimacy_level: int
    ) -> list[str]:
        """根据亲密度差异计算风险标记.
        
        Args:
            intimacy_value: 用户设置的亲密度 (0-101)
            current_intimacy_level: 当前分析的亲密度 (0-101)
        
        Returns:
            风险标记列表
        """
        risk_flags = []
        diff = intimacy_value - current_intimacy_level
        
        # 期望亲密度远高于当前亲密度
        if diff > 20:
            risk_flags.append("期望过高")
            risk_flags.append("需要循序渐进")
        
        # 期望亲密度远低于当前亲密度
        elif diff < -20:
            risk_flags.append("关系倒退")
            risk_flags.append("需要修复关系")
        
        # 当前亲密度很低但期望很高
        if current_intimacy_level < 30 and intimacy_value > 70:
            risk_flags.append("跨度过大")
        
        # 当前亲密度很高但期望降低
        if current_intimacy_level > 70 and intimacy_value < 30:
            risk_flags.append("关系危机")
        
        return risk_flags
    
    def _format_conversation(self, input: SceneAnalysisInput) -> str:
        """Format conversation for LLM prompt.
        
        Args:
            input: Scene analysis input
        
        Returns:
            Formatted conversation text
        """
        lines = []
        
        # 添加历史话题总结
        if input.history_topic_summary:
            lines.append(f"## 历史对话话题总结\n{input.history_topic_summary}\n")
        
        # 添加当前对话总结
        if input.current_conversation_summary:
            lines.append(f"## 当前对话总结\n{input.current_conversation_summary}\n")
        
        # 添加当前对话详情
        if input.current_conversation:
            lines.append("## 当前对话")
            for msg in input.current_conversation:
                speaker = "用户" if msg.speaker == "user" else msg.speaker
                lines.append(f"{speaker}: {msg.content}")
        elif input.history_dialog:
            # 如果没有 current_conversation，使用 history_dialog
            lines.append("## 对话历史")
            for msg in input.history_dialog:
                speaker = "用户" if msg.speaker == "user" else msg.speaker
                lines.append(f"{speaker}: {msg.content}")
        
        return "\n".join(lines)
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse LLM response to extract scene analysis.
        
        Args:
            response_text: LLM response text
        
        Returns:
            Dictionary with current_scenario, recommended_scenario, and recommended_strategy
        """
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
            data = json.loads(text)
            
            # 处理 recommended_strategy - 可能是字符串或列表
            recommended_strategy = data.get("recommended_strategy", [])
            if isinstance(recommended_strategy, str):
                # 如果是字符串，尝试分割成列表
                recommended_strategy = [s.strip() for s in recommended_strategy.split(",")]
            
            return {
                "current_scenario": data.get("current_scenario", "平衡/中风险策略"),
                "recommended_scenario": data.get("recommended_scenario", "平衡/中风险策略"),
                "recommended_strategy": recommended_strategy,
            }
        except json.JSONDecodeError:
            # 如果解析失败，返回默认值
            return {
                "current_scenario": "平衡/中风险策略",
                "recommended_scenario": "平衡/中风险策略",
                "recommended_strategy": [],
            }