from __future__ import annotations

from typing import Any

from app.models.schemas import ReplyGenerationInput
from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion
from app.services.prompt_utils import (
    format_user_style_compact,
    format_conversation_compact,
    get_last_message
)
from app.services.user_profile_impl import BaseUserProfileService
from user_profile import compile_trait_vector_to_policy, format_policy_instructions
from user_profile.intimacy import intimacy_label_zh, intimacy_label_en


# Phase 3: Reply length constraints by quality tier
REPLY_LENGTH_CONSTRAINTS = {
    "cheap": {
        "max_tokens": 50,
        "guidance": "Keep replies very brief (1-2 sentences max)"
    },
    "normal": {
        "max_tokens": 100,
        "guidance": "Keep replies concise (2-3 sentences)"
    },
    "premium": {
        "max_tokens": 200,
        "guidance": "Provide detailed replies (3-5 sentences)"
    }
}


class PromptAssembler:
    def __init__(
        self, 
        user_profile_service: BaseUserProfileService, 
        use_compact_prompt: bool = True,
        use_compact_v2: bool = True,
        include_reasoning: bool = False,  # Phase 3: Reasoning control
    ):
        self.user_profile_service = user_profile_service
        self.use_compact_prompt = use_compact_prompt
        self.use_compact_v2 = use_compact_v2
        self.include_reasoning = include_reasoning  # Phase 3
        self._prompt_manager = get_prompt_manager()

    def _display_speaker(self, speaker: Any) -> str:
        s = str(speaker or "").strip()
        if not s:
            return "未知"
        low = s.casefold()
        if low in {"user"}:
            return "我"
        if low in {"assistant", "bot", "system", "ai", "target"}:
            return "对方"
        return s

    async def assemble_reply_prompt(self, input: ReplyGenerationInput, strategy_plan=None) -> str:
        context = input.context
        scene = input.scene

        conversation_summary = context.conversation_summary
        current_intimacy_level = context.current_intimacy_level
        emotion_state = context.emotion_state

        intimacy_level = scene.intimacy_level
        
        # Phase 2: 如果有策略计划，使用它来减少 prompt 大小
        if strategy_plan:
            # 使用策略计划中的权重信息，而不是列出所有策略
            top_strategies = sorted(
                strategy_plan.strategy_weights.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            recommended_strategies = ", ".join([f"{s}({w:.1f})" for s, w in top_strategies])
            recommended_scenario = strategy_plan.recommended_scenario
        else:
            # 后备：使用场景分析的推荐
            recommended_strategies = (
                ", ".join(scene.recommended_strategies) if scene.recommended_strategies else "no specific strategies"
            )
            recommended_scenario = scene.recommended_scenario

        intimacy_level_label = self._intimacy_label(intimacy_level)
        current_intimacy_level_label = self._intimacy_label(current_intimacy_level)
        
        language = input.language

        # Phase 3: Get length constraint for quality tier
        length_constraint = REPLY_LENGTH_CONSTRAINTS.get(input.quality, REPLY_LENGTH_CONSTRAINTS["normal"])
        length_guidance = length_constraint["guidance"]

        # 选择使用精简版或完整版 prompt
        if self.use_compact_prompt:
            # 获取精简的用户画像
            profile_dict = await self.user_profile_service.get_profile_for_llm(input.user_id)
            if profile_dict:
                user_style_compact = format_user_style_compact(profile_dict)
            else:
                user_style_compact = "No profile available"
            
            # 获取最后一条消息
            last_message = get_last_message(context.conversation)
            
            if self.use_compact_v2:
                prompt_version = (
                    PromptVersion.V3_1_COMPACT_V2_WITH_REASONING
                    if self.include_reasoning
                    else PromptVersion.V3_2_COMPACT_V2_WITHOUT_REASONING
                )
                prompt_template = self._prompt_manager.get_prompt_version(
                    PromptType.REPLY_GENERATION,
                    prompt_version,
                )
                prompt_template = (prompt_template or "").strip()
                # Phase 3: Build output schema instruction based on reasoning control
                output_instruction = self._build_output_schema_instruction(
                    include_reasoning=self.include_reasoning
                )
                
                # 精简 V2：使用紧凑输出格式（最优化）
                base_prompt = prompt_template.format(
                    recommended_scenario=recommended_scenario,
                    recommended_strategies=recommended_strategies,
                    intimacy_level=intimacy_level,
                    current_intimacy_level=current_intimacy_level,
                    emotion_state=emotion_state,
                    conversation_summary=conversation_summary,
                    user_style_compact=user_style_compact,
                    last_message=last_message,
                    language=language,
                )
                
                # Phase 3: Add length constraint and output schema instruction
                # Add prompt version identifier
                version_suffix = "with_reasoning" if self.include_reasoning else "no_reasoning"
                return f"[PROMPT:reply_generation_compact_v2_{version_suffix}]\n{base_prompt}\n\nLength Constraint: {length_guidance}\n\n{output_instruction}"
            else:
                prompt_template = self._prompt_manager.get_prompt_version(
                    PromptType.REPLY_GENERATION,
                    PromptVersion.V2_COMPACT,
                )
                prompt_template = (prompt_template or "").strip()
                # 精简 V1：减少 40-50% tokens
                base_prompt = prompt_template.format(
                    recommended_scenario=recommended_scenario,
                    recommended_strategies=recommended_strategies,
                    intimacy_level=f"{intimacy_level_label}({intimacy_level})",
                    current_intimacy_level=f"{current_intimacy_level_label}({current_intimacy_level})",
                    emotion_state=emotion_state,
                    conversation_summary=conversation_summary,
                    user_style_compact=user_style_compact,
                    last_message=last_message,
                    language=language,
                )
                
                # Phase 3: Add length constraint
                return f"[PROMPT:reply_generation_compact_v1]\n{base_prompt}\n\nLength Constraint: {length_guidance}"
        else:
            # 完整版：用于调试和对比
            conversation = getattr(context, "history_conversation", "")
            if not isinstance(conversation, str) or not conversation.strip():
                conversation = "no history conversation"

            scenario = scene.scenario
            current_scenario = scene.current_scenario

            if hasattr(context, "risk_flags") and isinstance(context.risk_flags, list):
                if "修复期" in context.risk_flags:
                    current_intimacy_level_label = "修复期"

            persona_snapshot_prompt = await self.user_profile_service.serialize_to_prompt(
                user_id=input.user_id,
                max_tokens=500,
                language="en",
            )
            if persona_snapshot_prompt is None:
                await self.user_profile_service.create_profile(input.user_id)
                persona_snapshot_prompt = await self.user_profile_service.serialize_to_prompt(
                    user_id=input.user_id,
                    max_tokens=500,
                    language="en",
                )
            if persona_snapshot_prompt is None:
                persona_snapshot_prompt = "(no user profile yet)"

            policy_block = await self._compile_policy_block(input.user_id, context.conversation)

            reply_sentence = getattr(input, "reply_sentence", "")
            if not isinstance(reply_sentence, str) or not reply_sentence.strip():
                reply_sentence = self._infer_reply_sentence(context.conversation)

            prompt_template = self._prompt_manager.get_active_prompt(PromptType.REPLY_GENERATION)
            prompt_template = (prompt_template or "").strip()
            base_prompt = prompt_template.format(
                scenario=scenario,
                current_intimacy_level=f"{current_intimacy_level_label}({current_intimacy_level})",
                intimacy_level=f"{intimacy_level_label}({intimacy_level})",
                emotion_state=emotion_state,
                conversation=conversation,
                conversation_summary=conversation_summary,
                persona_snapshot_prompt=persona_snapshot_prompt,
                policy_block=policy_block,
                reply_sentence=reply_sentence,
                language=language,
                recommended_strategies=recommended_strategies,
                current_scenario=current_scenario,
                recommended_scenario=recommended_scenario,
            )
            
            return f"[PROMPT:reply_generation_full_v1]\n{base_prompt}"

    def _infer_reply_sentence(self, messages: list[Any]) -> str:
        if not messages:
            return ""

        def _get(msg: Any) -> tuple[str, str]:
            if hasattr(msg, "speaker"):
                speaker = str(getattr(msg, "speaker", ""))
                content = str(getattr(msg, "content", ""))
            else:
                speaker = str(msg.get("speaker", ""))
                content = str(msg.get("content", ""))
            return speaker, content

        user_speakers = {"user", "用户", "我", "me"}

        for msg in reversed(messages):
            speaker, content = _get(msg)
            if not isinstance(content, str):
                continue
            text = content.strip()
            if not text:
                continue
            if str(speaker).strip() not in user_speakers:
                return text

        for msg in reversed(messages):
            _, content = _get(msg)
            if isinstance(content, str) and content.strip():
                return content.strip()
        return ""

    async def _compile_policy_block(self, user_id: str, messages: list[Any] | None = None) -> str:
        try:
            profile = await self.user_profile_service.get_profile(user_id)
            trait_vector = getattr(profile, "trait_vector", None) if profile is not None else None
            compiled = compile_trait_vector_to_policy(trait_vector)
            rendered = format_policy_instructions(compiled.instructions)
            if rendered.strip():
                return rendered

            if messages is not None:
                selected_sentences: list[str] = []
                for msg in messages:
                    content = getattr(msg, "content", None) if hasattr(msg, "content") else msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        selected_sentences.append(content.strip())
                if len(selected_sentences) >= 10:
                    await self.user_profile_service.learn_new_traits(
                        user_id=user_id,
                        selected_sentences=selected_sentences[:10],
                        store=True,
                        map_to_standard=True,
                    )
                    profile = await self.user_profile_service.get_profile(user_id)
                    trait_vector = getattr(profile, "trait_vector", None) if profile is not None else None
                    compiled = compile_trait_vector_to_policy(trait_vector)
                    rendered = format_policy_instructions(compiled.instructions)
                    if rendered.strip():
                        return rendered

            return "(no traits learned yet)"
        except Exception:
            return "(no traits learned yet)"

    def _intimacy_label(self, value: int) -> str:
        try:
            v = int(value)
        except Exception:
            return "unknown"
        return intimacy_label_en(v)
    
    def _build_output_schema_instruction(self, include_reasoning: bool) -> str:
        """Build output schema instruction based on reasoning control.
        
        Phase 3: Output Optimization - Control reasoning field inclusion.
        
        Args:
            include_reasoning: Whether to include reasoning fields
        
        Returns:
            Output schema instruction string
        """
        if include_reasoning:
            return """Output Format (JSON):
{
  "r": [
    ["<reply_text>", "<strategy_code>", "<reasoning>"],
    ...
  ],
  "adv": "<overall_advice>"
}

Include reasoning for each reply option."""
        else:
            return """Output Format (JSON):
{
  "r": [
    ["<reply_text>", "<strategy_code>"],
    ...
  ],
  "adv": "<overall_advice>"
}

Exclude reasoning to save tokens."""

    def _format_conversation(self, messages: list[Any]) -> str:
        if not messages:
            return "(no conversation history)"

        lines: list[str] = []
        for msg in messages:
            if hasattr(msg, "speaker"):
                speaker = self._display_speaker(msg.speaker)
                content = msg.content
            else:
                speaker = self._display_speaker(msg.get("speaker", "unknown"))
                content = msg.get("content", "")
            lines.append(f"{speaker}: {content}")
        return "\n".join(lines)
