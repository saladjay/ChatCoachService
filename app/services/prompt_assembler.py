from __future__ import annotations

from typing import Any

from app.models.schemas import ReplyGenerationInput
from app.services.prompt import CHATCOACH_PROMPT
from app.services.user_profile_impl import BaseUserProfileService
from user_profile import compile_trait_vector_to_policy, format_policy_instructions
from user_profile.intimacy import intimacy_label_zh, intimacy_label_en


class PromptAssembler:
    def __init__(self, user_profile_service: BaseUserProfileService):
        self.user_profile_service = user_profile_service

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

    async def assemble_reply_prompt(self, input: ReplyGenerationInput) -> str:
        context = input.context
        scene = input.scene

        conversation_summary = context.conversation_summary
        current_intimacy_level = context.current_intimacy_level
        emotion_state = context.emotion_state
        conversation = getattr(context, "history_conversation", "")
        if not isinstance(conversation, str) or not conversation.strip():
            conversation = "no history conversation"

        scenario = scene.scenario
        intimacy_level = scene.intimacy_level
        recommended_strategies = (
            ", ".join(scene.recommended_strategies) if scene.recommended_strategies else "no specific strategies"
        )
        current_scenario = scene.current_scenario
        recommended_scenario = scene.recommended_scenario

        intimacy_level_label = self._intimacy_label(intimacy_level)
        current_intimacy_level_label = self._intimacy_label(current_intimacy_level)
        if hasattr(context, "risk_flags") and isinstance(context.risk_flags, list):
            if "修复期" in context.risk_flags:
                current_intimacy_level_label = "修复期" # 修复期

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
        language = input.language

        return CHATCOACH_PROMPT.format(
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
            core_profile = getattr(profile, "core_profile", None) if profile is not None else None
            trait_vector = getattr(core_profile, "trait_vector", None) if core_profile is not None else None
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
                    core_profile = getattr(profile, "core_profile", None) if profile is not None else None
                    trait_vector = getattr(core_profile, "trait_vector", None) if core_profile is not None else None
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
