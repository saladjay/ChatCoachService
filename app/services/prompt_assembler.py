from __future__ import annotations

from typing import Any

from app.models.schemas import ReplyGenerationInput
from app.services.prompt import CHATCOACH_PROMPT
from app.services.user_profile_impl import BaseUserProfileService
from user_profile import compile_trait_vector_to_policy, format_policy_instructions


class PromptAssembler:
    def __init__(self, user_profile_service: BaseUserProfileService):
        self.user_profile_service = user_profile_service

    async def assemble_reply_prompt(self, input: ReplyGenerationInput) -> str:
        context = input.context
        scene = input.scene

        conversation_summary = context.conversation_summary
        current_intimacy_level = context.current_intimacy_level
        emotion_state = context.emotion_state
        conversation = self._format_conversation(context.conversation)

        scenario = scene.scenario
        intimacy_level = scene.intimacy_level
        recommended_strategies = (
            ", ".join(scene.recommended_strategies) if scene.recommended_strategies else "无特定策略"
        )
        current_scenario = scene.current_scenario
        recommended_scenario = scene.recommended_scenario

        persona_snapshot_prompt = await self.user_profile_service.serialize_to_prompt(
            user_id=input.user_id,
            max_tokens=500,
            language="zh",
        )
        if persona_snapshot_prompt is None:
            await self.user_profile_service.create_profile(input.user_id)
            persona_snapshot_prompt = await self.user_profile_service.serialize_to_prompt(
                user_id=input.user_id,
                max_tokens=500,
                language="zh",
            )
        if persona_snapshot_prompt is None:
            persona_snapshot_prompt = "（用户画像暂无）"

        policy_block = await self._compile_policy_block(input.user_id)

        reply_sentence = getattr(input, "reply_sentence", "")
        language = input.language

        return CHATCOACH_PROMPT.format(
            scenario=scenario,
            current_intimacy_level=current_intimacy_level,
            intimacy_level=intimacy_level,
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

    async def _compile_policy_block(self, user_id: str) -> str:
        try:
            profile = await self.user_profile_service.get_profile(user_id)
            core_profile = getattr(profile, "core_profile", None) if profile is not None else None
            trait_vector = getattr(core_profile, "trait_vector", None) if core_profile is not None else None
            compiled = compile_trait_vector_to_policy(trait_vector)
            rendered = format_policy_instructions(compiled.instructions)
            return rendered if rendered.strip() else "（暂无）"
        except Exception:
            return "（暂无）"

    def _format_conversation(self, messages: list[Any]) -> str:
        if not messages:
            return "（暂无对话历史）"

        lines: list[str] = []
        for msg in messages:
            if hasattr(msg, "speaker"):
                speaker = msg.speaker
                content = msg.content
            else:
                speaker = msg.get("speaker", "unknown")
                content = msg.get("content", "")
            lines.append(f"{speaker}: {content}")
        return "\n".join(lines)
