from app.models.schemas import (
    LLMResult,
    ReplyGenerationInput,
)
from app.services.base import BaseReplyGenerator
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.user_profile_impl import BaseUserProfileService
from app.services.prompt_assembler import PromptAssembler


class LLMAdapterReplyGenerator(BaseReplyGenerator):
    """Reply generator implementation using LLM Adapter.
    
    This class wraps the LLM Adapter to implement the BaseReplyGenerator interface,
    allowing it to be used by the Orchestrator.
    
    Requirements: 3.3
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        user_profile_service: BaseUserProfileService,
        user_id: str = "system",
    ):

        """Initialize with an LLM Adapter.
        
        Args:
            llm_adapter: The LLM adapter to use for generating replies.
            user_id: Default user ID for billing/logging.
        """
        self.llm_adapter = llm_adapter
        self.user_id = user_id
        self.user_profile_service = user_profile_service
        self._prompt_assembler = PromptAssembler(user_profile_service)

    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult:

        """Generate a reply using the LLM Adapter.
        
        Args:
            input: Reply generation input containing prompt, quality, context, etc.
        
        Returns:
            LLMResult with generated reply and metadata.
        """
        prompt = await self._prompt_assembler.assemble_reply_prompt(input)
        
        # Create LLM call
        llm_call = LLMCall(
            task_type="generation",
            prompt=prompt,
            quality=input.quality,
            user_id=input.user_id,
            provider='dashscope',
            model='qwen-flash'
        )
        
        return await self.llm_adapter.call(llm_call)