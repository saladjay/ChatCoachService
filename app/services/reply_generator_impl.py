from app.models.schemas import (
    LLMResult,
    ReplyGenerationInput,
)
from app.services.base import BaseReplyGenerator
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.prompt import CHATCOACH_PROMPT


class LLMAdapterReplyGenerator(BaseReplyGenerator):
    """Reply generator implementation using LLM Adapter.
    
    This class wraps the LLM Adapter to implement the BaseReplyGenerator interface,
    allowing it to be used by the Orchestrator.
    
    Requirements: 3.3
    """
    
    def __init__(self, llm_adapter: BaseLLMAdapter, user_id: str = "system"):
        """Initialize with an LLM Adapter.
        
        Args:
            llm_adapter: The LLM adapter to use for generating replies.
            user_id: Default user ID for billing/logging.
        """
        self.llm_adapter = llm_adapter
        self.user_id = user_id

    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult:
        """Generate a reply using the LLM Adapter.
        
        Args:
            input: Reply generation input containing prompt, quality, context, etc.
        
        Returns:
            LLMResult with generated reply and metadata.
        """
        context = input.context
        scene = input.scene
        persona = input.persona

        # Extract context information
        conversation_summary = context.conversation_summary
        current_intimacy_level = context.current_intimacy_level
        emotion_state = context.emotion_state
        
        # Format conversation history
        conversation = self._format_conversation(context.conversation)

        # Extract scene information
        scenario = scene.scenario
        intimacy_level = scene.intimacy_level
        recommended_strategies = ", ".join(scene.recommended_strategies) if scene.recommended_strategies else "无特定策略"
        current_scenario = scene.current_scenario
        recommended_scenario = scene.recommended_scenario

        # Extract persona information
        persona_snapshot_prompt = persona.prompt
        
        # Get reply sentence from input (default to empty if not provided)
        reply_sentence = getattr(input, 'reply_sentence', '')
        
        # Get language from input (must be provided, no default fallback)
        # Language should always come from request to ensure consistency
        language = input.language

        # Build the complete prompt
        prompt = CHATCOACH_PROMPT.format(
            scenario=scenario,
            current_intimacy_level=current_intimacy_level,
            intimacy_level=intimacy_level,
            emotion_state=emotion_state,
            conversation=conversation,
            conversation_summary=conversation_summary,
            persona_snapshot_prompt=persona_snapshot_prompt,
            reply_sentence=reply_sentence,
            language=language,
            recommended_strategies=recommended_strategies,
            current_scenario=current_scenario,
            recommended_scenario=recommended_scenario,
        )
        
        # Create LLM call
        llm_call = LLMCall(
            task_type="generation",
            prompt=prompt,
            quality=input.quality,
            user_id=self.user_id,
            provider='dashscope',
            model='qwen-flash'
        )
        
        return await self.llm_adapter.call(llm_call)
    
    def _format_conversation(self, messages: list) -> str:
        """Format conversation messages for prompt.
        
        Args:
            messages: List of Message objects
        
        Returns:
            Formatted conversation text
        """
        if not messages:
            return "（暂无对话历史）"
        
        lines = []
        for msg in messages:
            # Handle Message objects
            if hasattr(msg, 'speaker'):
                speaker = msg.speaker
                content = msg.content
            else:
                # Fallback for dict
                speaker = msg.get("speaker", "unknown")
                content = msg.get("content", "")
            
            lines.append(f"{speaker}: {content}")
        
        return "\n".join(lines)