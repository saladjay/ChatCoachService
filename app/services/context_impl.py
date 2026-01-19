from app.services.base import BaseContextBuilder

from app.models.schemas import (
    ContextBuilderInput,
    ContextResult)
from app.services.llm_adapter import BaseLLMAdapter, LLMCall

from app.services.prompt import CONTEXT_SUMMARY_PROMPT

class ContextBuilder(BaseContextBuilder):
    """Real implementation of context builder service.
    
    Uses LLM to analyze conversation history and build context.
    """
    def __init__(self, llm_adapter: BaseLLMAdapter, provider: str | None = None, model: str | None = None):
        """Initialize ContextBuilder with LLM adapter.
        
        Args:
            llm_adapter: LLM adapter for analyzing conversation context
            provider: Optional LLM provider (e.g., "dashscope", "openai")
            model: Optional LLM model name
        """
        self._llm_adapter = llm_adapter
        self.provider = provider
        self.model = model

    async def build_context(self, input: ContextBuilderInput) -> ContextResult:
        """Build context by analyzing conversation history with LLM.
        
        Args:
            input: Context builder input with conversation history.
        
        Returns:
            ContextResult with analyzed context information.
        """
        # Format conversation history for prompt
        conversation_text = self._format_conversation(input.history_dialog)
        
        # Build prompt
        prompt = CONTEXT_SUMMARY_PROMPT.format(conversation=conversation_text)
        
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
        
        # Parse LLM response (assuming JSON format)
        try:
            import json
            analysis = json.loads(result.text)
            
            return ContextResult(
                conversation_summary=analysis.get("summary", ""),
                emotion_state=analysis.get("emotion_state", "neutral"),
                current_intimacy_level=analysis.get("intimacy_level", 3),
                risk_flags=analysis.get("risk_flags", []),
                conversation = input.history_dialog
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback to default values if parsing fails
            return ContextResult(
                conversation_summary=result.text[:200] if result.text else "Unable to summarize",
                emotion_state="neutral",
                current_intimacy_level=3,
                risk_flags=[],
            )
    
    def _format_conversation(self, messages: list) -> str:
        """Format conversation messages for prompt.
        
        Args:
            messages: List of Message objects or dicts
        
        Returns:
            Formatted conversation text
        """
        if not messages:
            return "（暂无对话历史）"
        
        lines = []
        for msg in messages:
            # Handle both Message objects and dicts
            if hasattr(msg, 'speaker'):
                # Pydantic Message object
                speaker = msg.speaker
                content = msg.content
            else:
                # Dict
                speaker = msg.get("speaker", "unknown")
                content = msg.get("content", "")
            
            lines.append(f"{speaker}: {content}")
        
        return "\n".join(lines)