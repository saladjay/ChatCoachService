import inspect
import time
import uuid
from pathlib import Path
from typing import Any

from app.models.schemas import LLMResult
from app.core.config import settings
from app.observability.trace_logger import TraceLogger, trace_logger
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.prompt_utils import extract_prompt_version


class LoggingLLMAdapter(BaseLLMAdapter):
    def __init__(
        self,
        inner: BaseLLMAdapter,
        logger: TraceLogger = trace_logger,
    ):
        self._inner = inner
        self._logger = logger

    async def call(self, llm_call: LLMCall) -> LLMResult:
        call_id = uuid.uuid4().hex
        start = time.monotonic()

        # Extract prompt version identifier
        prompt_version, clean_prompt = extract_prompt_version(llm_call.prompt)
        
        # Create a modified LLMCall with clean prompt (without version identifier)
        clean_llm_call = LLMCall(
            task_type=llm_call.task_type,
            prompt=clean_prompt,
            quality=llm_call.quality,
            user_id=llm_call.user_id,
            provider=llm_call.provider,
            model=llm_call.model,
            max_tokens=llm_call.max_tokens,
        )

        caller_info: dict[str, Any] = {}
        for frame_info in inspect.stack()[1:]:
            module = str(frame_info.frame.f_globals.get("__name__") or "")
            if module == __name__:
                continue
            if module.startswith("app.services"):
                caller_info = {
                    "caller_module": module,
                    "caller_func": frame_info.function,
                    "caller_file": frame_info.filename,
                    "caller_line": frame_info.lineno,
                }
                break

        prompt_file: str | None = None
        if settings.trace.log_llm_prompt:
            prompt_dir = Path("logs") / "llm_prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = prompt_dir / f"{call_id}.txt"
            # Save the original prompt with version identifier
            prompt_path.write_text(llm_call.prompt, encoding="utf-8")
            prompt_file = str(prompt_path)

        prompt_value: str | None
        if settings.trace.log_llm_prompt:
            # Log the original prompt with version identifier
            prompt_value = llm_call.prompt
        else:
            prompt_value = None

        self._logger.log_event(
            {
                "level": "debug",
                "type": "llm_call_start",
                "call_id": call_id,
                "task_type": llm_call.task_type,
                "user_id": llm_call.user_id,
                "quality": llm_call.quality,
                "provider": llm_call.provider,
                "model": llm_call.model,
                "prompt": prompt_value,
                "prompt_version": prompt_version,  # Add prompt version to log
                "prompt_len": len(clean_prompt),  # Length without version identifier
                "prompt_file": prompt_file,
                **caller_info,
            }
        )

        try:
            # Call the inner adapter with clean prompt (version identifier removed)
            result = await self._inner.call(clean_llm_call)
            duration_ms = int((time.monotonic() - start) * 1000)
            self._logger.log_event(
                {
                    "level": "debug",
                    "type": "llm_call_end",
                    "call_id": call_id,
                    "task_type": llm_call.task_type,
                    "user_id": llm_call.user_id,
                    "quality": llm_call.quality,
                    "requested_provider": llm_call.provider,
                    "requested_model": llm_call.model,
                    "prompt_version": prompt_version,  # Add prompt version to log
                    "duration_ms": duration_ms,
                    "provider": result.provider,
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "cost_usd": result.cost_usd,
                    "text": result.text,
                    "prompt_file": prompt_file,
                    **caller_info,
                }
            )
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._logger.log_event(
                {
                    "level": "error",
                    "type": "llm_call_error",
                    "call_id": call_id,
                    "task_type": llm_call.task_type,
                    "user_id": llm_call.user_id,
                    "quality": llm_call.quality,
                    "requested_provider": llm_call.provider,
                    "requested_model": llm_call.model,
                    "prompt_version": prompt_version,  # Add prompt version to log
                    "duration_ms": duration_ms,
                    "error": str(e),
                    "prompt_file": prompt_file,
                    **caller_info,
                }
            )
            raise

    async def call_with_provider(
        self,
        prompt: str,
        provider: str,
        model: str,
        user_id: str = "system",
    ) -> LLMResult:
        llm_call = LLMCall(
            task_type="generation",
            prompt=prompt,
            quality="normal",
            user_id=user_id,
            provider=provider,
            model=model,
        )
        return await self.call(llm_call)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
