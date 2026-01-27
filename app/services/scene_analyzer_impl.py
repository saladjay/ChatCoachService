from app.models.schemas import (
    SceneAnalysisInput,
    SceneAnalysisResult,
    Message,
)
from app.services.base import (
    BaseSceneAnalyzer,
)
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion

from app.services.schema_expander import SchemaExpander, parse_and_expand_scene_analysis
from app.models.schemas_compact import SceneAnalysisCompact
import json


class SceneAnalyzer(BaseSceneAnalyzer):
    """Scene analysis service implementation using LLM.
    
    Analyzes conversation to determine:
    - Current scenario (current interaction strategy level)
    - Recommended scenario (suggested strategy level for next interaction)
    - Recommended strategies (3 specific strategy codes)
    """
    
    def __init__(
        self, 
        llm_adapter: BaseLLMAdapter, 
        provider: str | None = None, 
        model: str | None = None,
        use_compact_prompt: bool = True,
        use_compact_v2: bool = True
    ):
        """Initialize SceneAnalyzer with LLM adapter.
        
        Args:
            llm_adapter: LLM adapter for analyzing conversation context
            provider: Optional LLM provider (e.g., "dashscope", "openai")
            model: Optional LLM model name
            use_compact_prompt: Use compact prompt to reduce tokens (default: True)
            use_compact_v2: Use compact V2 with compact output codes (default: True)
        """
        self._llm_adapter = llm_adapter
        self.provider = provider
        self.model = model
        self.use_compact_prompt = use_compact_prompt
        self.use_compact_v2 = use_compact_v2
        self._prompt_manager = get_prompt_manager()

    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        """Analyze conversation scene using LLM.
        
        Args:
            input: Scene analysis input containing conversation history and summaries.
        
        Returns:
            SceneAnalysisResult with current scenario, recommended scenario, and strategies.
        """
        # Phase 2 优化：只使用摘要，不使用完整对话
        # 这样可以大幅减少 prompt 大小（目标 ~80 tokens 固定部分）
        conversation_summary = input.current_conversation_summary or input.history_topic_summary or "No summary available"
        
        if self.use_compact_prompt and self.use_compact_v2:
            # 使用紧凑 V2 版本（最优化，使用紧凑输出代码）
            # Phase 2: 进一步简化 prompt
            prompt_template = self._prompt_manager.get_prompt_version(
                PromptType.SCENARIO_ANALYSIS,
                PromptVersion.V3_1_COMPACT_V2,
            )
            prompt_template = (prompt_template or "").strip()
            prompt = prompt_template.format(conversation_summary=conversation_summary)
        elif self.use_compact_prompt:
            # 使用紧凑 V1 版本（减少 token）
            prompt_template = self._prompt_manager.get_prompt_version(
                PromptType.SCENARIO_ANALYSIS,
                PromptVersion.V2_COMPACT,
            )
            prompt_template = (prompt_template or "").strip()
            prompt = prompt_template.format(conversation_summary=conversation_summary)
        else:
            # 使用完整版 prompt（用于调试）
            conversation_text = self._format_conversation(input)
            prompt_template = self._prompt_manager.get_active_prompt(PromptType.SCENARIO_ANALYSIS)
            prompt_template = (prompt_template or "").strip()
            prompt = prompt_template.format(conversation=conversation_text)
        
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
        if self.use_compact_v2:
            # 使用紧凑模式解析和扩展
            analysis = self._parse_compact_response(result.text, input)
        else:
            # 使用传统解析
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
            analysis = SceneAnalysisResult(
                relationship_state=relationship_state,
                scenario=analysis.get("recommended_scenario", "balance/medium risk strategy"),
                intimacy_level=input.intimacy_value,
                risk_flags=risk_flags,
                current_scenario=analysis.get("current_scenario", ""),
                recommended_scenario=analysis.get("recommended_scenario", ""),
                recommended_strategies=analysis.get("recommended_strategy", []),
            )
        
        return analysis
    
    def _build_ultra_compact_prompt(self, summary: str, input: SceneAnalysisInput) -> str:
        """Build ultra-compact prompt for Phase 2 optimization.
        
        Target: ~80 tokens for fixed prompt + summary length
        
        Args:
            summary: Conversation summary
            input: Scene analysis input
        
        Returns:
            Ultra-compact prompt string
        """
        # 只包含最必要的信息
        prompt = f"""[PROMPT:scene_analyzer_compact_v2]
Scene analyzer. Analyze conversation and recommend scenario.

Summary: {summary[:999]}
Intimacy: target={input.intimacy_value}, current={input.current_intimacy_level}

Output JSON:
{{"cs": "S|B|R|C|N", "rs": "S|B|R|C|N", "st": ["s1","s2","s3"]}}

cs=current_scenario, rs=recommended_scenario, st=strategies
S=SAFE, B=BALANCED, R=RISKY, C=RECOVERY, N=NEGATIVE
"""
        return prompt
    
    def _display_speaker(self, speaker) -> str:
        s = str(speaker or "").strip()
        if not s:
            return "unknown"
        low = s.casefold()
        if low in {"user"}:
            return "me"
        if low in {"assistant", "bot", "system", "ai", "target"}:
            return "opponent"
        return s
    
    def _calculate_relationship_state(
        self, 
        intimacy_value: int, 
        current_intimacy_level: int
    ) -> str:
        """根据用户设置的亲密度和当前亲密度计算关系状态.
        
        Args:
            intimacy_value: 用户设置的亲密度 (0-100)
            current_intimacy_level: 当前分析的亲密度 (0-100)
        
        Returns:
            关系状态: "破冰", "推进", "冷却", "维持"
            relationship_state: "ignition", "propulsion", "ventilation", "equilibrium"
        """
        diff = intimacy_value - current_intimacy_level
        
        # 如果当前亲密度低于用户期望，需要推进
        if diff > 10:
            if current_intimacy_level <= 40:
                return "ignition"  # 低亲密度阶段，需要破冰
            else:
                return "propulsion"  # 中高亲密度阶段，需要推进
        
        # 如果当前亲密度高于用户期望，需要冷却
        elif diff < -10:
            return "ventilation"
        
        # 亲密度相近，维持现状
        else:
            return "equilibrium"
    
    def _calculate_risk_flags(
        self,
        intimacy_value: int,
        current_intimacy_level: int
    ) -> list[str]:
        """根据亲密度差异计算风险标记.
        
        Args:
            intimacy_value: 用户设置的亲密度 (0-100)
            current_intimacy_level: 当前分析的亲密度 (0-100)
        
        Returns:
            风险标记列表
        """
        risk_flags = []
        diff = intimacy_value - current_intimacy_level
        
        # 期望亲密度远高于当前亲密度
        if diff > 20:
            risk_flags.append("Overly high expectations") # 期望过高
            risk_flags.append("Need to proceed gradually") # 需要循序渐进
        
        # 期望亲密度远低于当前亲密度
        elif diff < -20:
            risk_flags.append("Relationship regression") # 关系倒退
            risk_flags.append("Need to repair relationship") # 需要修复关系
        
        # 当前亲密度很低但期望很高
        if current_intimacy_level <= 40 and intimacy_value >= 81:
            risk_flags.append("Excessively large gap") # 跨度过大
        
        # 当前亲密度很高但期望降低
        if current_intimacy_level >= 81 and intimacy_value <= 40:
            risk_flags.append("Relationship crisis") # 关系危机
        
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
            lines.append(f"## history topic summary\n{input.history_topic_summary}\n") ## 历史对话话题总结
        
        # 添加当前对话总结
        if input.current_conversation_summary:
            lines.append(f"## current conversation summary\n{input.current_conversation_summary}\n") ## 当前对话总结
            return "\n".join(lines)
        
        # 添加当前对话详情
        if input.current_conversation:
            lines.append("## current conversation") ## 当前对话
            for msg in input.current_conversation:
                speaker = self._display_speaker(msg.speaker)
                lines.append(f"{speaker}: {msg.content}")
        elif input.history_dialog:
            # 如果没有 current_conversation，使用 history_dialog
            lines.append("## history dialog") ## 对话历史
            for msg in input.history_dialog:
                speaker = self._display_speaker(msg.speaker)
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
            
            # 兼容两种字段名：recommended_strategies(list) / recommended_strategy(str|list)
            recommended_strategy = data.get("recommended_strategies")
            if recommended_strategy is None:
                recommended_strategy = data.get("recommended_strategy", [])
            if isinstance(recommended_strategy, str):
                recommended_strategy = [s.strip() for s in recommended_strategy.split(",") if s.strip()]
            if isinstance(recommended_strategy, list):
                recommended_strategy = [str(s).strip() for s in recommended_strategy if str(s).strip()]
            else:
                recommended_strategy = []
            
            return {
                "current_scenario": data.get("current_scenario", "balance/medium risk strategy"), ## 当前场景
                "recommended_scenario": data.get("recommended_scenario", "balance/medium risk strategy"), ## 推荐场景
                "recommended_strategy": recommended_strategy,
            }
        
        except json.JSONDecodeError:
            # 如果解析失败，返回默认值
            return {
                "current_scenario": "balance/medium risk strategy",
                "recommended_scenario": "balance/medium risk strategy",
                "recommended_strategy": [],
            }
    
    def _parse_compact_response(self, response_text: str, input: SceneAnalysisInput) -> SceneAnalysisResult:
        """Parse compact LLM response and expand to full schema.
        
        This method handles the compact V2 output format with abbreviated field names
        and codes, then expands it to the full SceneAnalysisResult schema.
        
        Args:
            response_text: LLM response text with compact JSON
            input: Original input for fallback calculations
        
        Returns:
            Full SceneAnalysisResult
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
            # 解析紧凑 JSON
            data = json.loads(text)
            compact = SceneAnalysisCompact(**data)
            
            # 使用 SchemaExpander 扩展为完整模式
            result = SchemaExpander.expand_scene_analysis(compact)
            
            # 如果 LLM 没有提供 intimacy_level，使用输入的值
            if result.intimacy_level == 0:
                result.intimacy_level = input.intimacy_value
            
            return result
            
        except (json.JSONDecodeError, ValueError, Exception) as e:
            # 解析失败，使用传统方法作为后备
            # 计算 relationship_state 和 risk_flags
            relationship_state = self._calculate_relationship_state(
                input.intimacy_value, 
                input.current_intimacy_level
            )
            risk_flags = self._calculate_risk_flags(
                input.intimacy_value,
                input.current_intimacy_level
            )
            
            # 返回默认值
            return SceneAnalysisResult(
                relationship_state=relationship_state,
                scenario="BALANCED",
                intimacy_level=input.intimacy_value,
                risk_flags=risk_flags,
                current_scenario="BALANCED",
                recommended_scenario="BALANCED",
                recommended_strategies=[],
            )