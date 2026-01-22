from app.services.base import BaseContextBuilder

from app.models.schemas import (
    ContextBuilderInput,
    ContextResult)
from app.services.llm_adapter import BaseLLMAdapter, LLMCall

from app.services.prompt import CONTEXT_SUMMARY_PROMPT
from app.services.prompt_compact import CONTEXT_SUMMARY_PROMPT_COMPACT, format_conversation_compact
from user_profile.intimacy import is_recovery_stage, normalize_intimacy_level


class ContextBuilder(BaseContextBuilder):
    """Real implementation of context builder service.
    
    Uses LLM to analyze conversation history and build context.
    """
    def __init__(
        self, 
        llm_adapter: BaseLLMAdapter, 
        provider: str | None = None, 
        model: str | None = None,
        use_compact_prompt: bool = True
    ):
        """Initialize ContextBuilder with LLM adapter.
        
        Args:
            llm_adapter: LLM adapter for analyzing conversation context
            provider: Optional LLM provider (e.g., "dashscope", "openai")
            model: Optional LLM model name
            use_compact_prompt: Use compact prompt to reduce tokens (default: True)
        """
        self._llm_adapter = llm_adapter
        self.provider = provider
        self.model = model
        self.use_compact_prompt = use_compact_prompt

    async def build_context(self, input: ContextBuilderInput) -> ContextResult:
        """Build context by analyzing conversation history with LLM.
        
        Args:
            input: Context builder input with conversation history.
        
        Returns:
            ContextResult with analyzed context information.
        """
        # Format conversation history for prompt
        if self.use_compact_prompt:
            # 使用精简版格式（减少 token）
            conversation_text = format_conversation_compact(input.history_dialog, max_messages=5)
            prompt = f"[PROMPT:context_summary_compact_v1]\n{CONTEXT_SUMMARY_PROMPT_COMPACT.format(conversation=conversation_text)}"
        else:
            # 使用完整版格式（用于调试）
            conversation_text = self._format_conversation(input.history_dialog)
            prompt = f"[PROMPT:context_summary_full_v1]\n{CONTEXT_SUMMARY_PROMPT.format(conversation=conversation_text)}"
        
        # Call LLM
        llm_call = LLMCall(
            task_type="scene",
            prompt=prompt,
            quality="normal",
            user_id=input.user_id,
            provider=self.provider,
            model=self.model
        )
        
        result = await self._llm_adapter.call(llm_call)
        
        try:
            import json

            text = (result.text or "").strip()
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()

            if "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]

            analysis = json.loads(text)
            if not isinstance(analysis, dict):
                raise ValueError("Context summary response is not a JSON object")

            conversation_summary = analysis.get("conversation_summary")
            if not isinstance(conversation_summary, str) or not conversation_summary.strip():
                conversation_summary = analysis.get("summary", "")
            if not isinstance(conversation_summary, str) or not conversation_summary.strip():
                conversation_summary = self._fallback_summary(input.history_dialog)

            emotion_state = analysis.get("emotion_state", "neutral")

            current_intimacy_raw = (
                analysis.get("current_intimacy_level")
                if analysis.get("current_intimacy_level") is not None
                else analysis.get("intimacy_level")
            )
            is_recovery = is_recovery_stage(current_intimacy_raw)
            current_intimacy_level = normalize_intimacy_level(current_intimacy_raw)

            risk_flags = analysis.get("risk_flags", [])
            if not isinstance(risk_flags, list):
                risk_flags = []
            if is_recovery and "修复期" not in risk_flags:
                risk_flags.append("修复期")

            return ContextResult(
                conversation_summary=conversation_summary,
                emotion_state=str(emotion_state),
                current_intimacy_level=current_intimacy_level,
                risk_flags=risk_flags,
                conversation=input.history_dialog,
            )
        except Exception:
            # Fallback to default values if parsing fails
            return ContextResult(
                conversation_summary=self._fallback_summary(input.history_dialog),
                emotion_state="neutral",
                current_intimacy_level=3,
                risk_flags=[],
                conversation=input.history_dialog,
            )

    def _display_speaker(self, speaker) -> str:
        s = str(speaker or "").strip()
        if not s:
            return "unknown"
        low = s.casefold()
        if low in {"user"}:
            return "me"
        if low in {"assistant", "bot", "system", "ai", "target"}:
            return "other"
        return s

    def _fallback_summary(self, messages: list) -> str:
        if not messages:
            return "(no conversation summary)"

        tail = messages[-4:]
        lines: list[str] = []
        for msg in tail:
            if hasattr(msg, "speaker"):
                speaker = self._display_speaker(msg.speaker)
                content = str(msg.content)
            else:
                speaker = self._display_speaker(msg.get("speaker", "unknown"))
                content = str(msg.get("content", ""))

            content = content.strip()
            if not content:
                continue
            if len(content) > 999:
                content = content[:999] + "..."
            lines.append(f"{speaker}: {content}")

        return " / ".join(lines) if lines else "(no conversation summary)"

    def _normalize_intimacy_level(self, value) -> int:
        return normalize_intimacy_level(value)
    
    def _format_conversation(self, messages: list) -> str:
        """Format conversation messages for prompt.
        
        Args:
            messages: List of Message objects or dicts
        
        Returns:
            Formatted conversation text
        """
        if not messages:
            return "(no conversation history)"
        
        lines = []
        for msg in messages:
            # Handle both Message objects and dicts
            if hasattr(msg, 'speaker'):
                # Pydantic Message object
                speaker = self._display_speaker(msg.speaker)
                content = msg.content
            else:
                # Dict
                speaker = self._display_speaker(msg.get("speaker", "unknown"))
                content = msg.get("content", "")
            
            lines.append(f"{speaker}: {content}")
        
        return "\n".join(lines)