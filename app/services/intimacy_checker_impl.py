from __future__ import annotations

import json
import re
from typing import Any

import sys
from pathlib import Path

import httpx

from app.models.schemas import IntimacyCheckInput, IntimacyCheckResult
from app.services.base import BaseIntimacyChecker
from app.services.llm_adapter import BaseLLMAdapter, LLMCall


class PromptLLMThirdPartyIntimacyAdapter:
    provider = "app_llm_adapter"

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self._llm_adapter = llm_adapter
        self._provider = provider
        self._model = model
        self.model_version = f"{provider}:{model}" if provider and model else "router"

    async def get_intimacy_score(self, text: str, context: dict[str, Any]) -> float:
        profile = (context or {}).get("profile") or {}
        intimacy_stage = profile.get("intimacy_stage")
        persona = profile.get("persona")

        prompt = (
            "[PROMPT:intimacy_third_party_llm_v1]\n"
            "你是一个对话内容审核员，负责评估回复内容在当前关系阶段下是否过度亲密/越界。\n"
            "请结合关系阶段（intimacy_stage）判断该回复是否‘超过’当前阶段可接受的亲密程度。\n\n"
            "关系阶段说明（intimacy_stage）：\n"
            "1=陌生期(stranger)，2=熟人期(acquaintance)，3=朋友期(friend)，"
            "4=亲密期(intimate)，5=羁绊期(bonded)。\n\n"
            "输出要求：\n"
            "- 只输出 JSON：{\"score\": <0~1>}\n"
            "- score 表示‘越界风险’，0=完全合适，1=严重越界。\n\n"
            f"persona: {persona}\n"
            f"intimacy_stage: {intimacy_stage}\n"
            f"text: {text}\n"
        )

        llm_call = LLMCall(
            task_type="qc",
            prompt=prompt,
            quality="normal",
            user_id="system",
            provider=self._provider,
            model=self._model,
            max_tokens=80,
        )

        try:
            result = await self._llm_adapter.call(llm_call)
            score = self._parse_score((result.text or "").strip())
            if score is None:
                raise ValueError("LLM response did not contain a valid score")
            return max(0.0, min(1.0, score))
        except Exception as e:
            try:
                from moderation_service.infrastructure.adapters import ThirdPartyAPIError  # type: ignore

                raise ThirdPartyAPIError(message=str(e), provider=self.provider) from e
            except ModuleNotFoundError:
                raise

    def _parse_score(self, text: str) -> float | None:
        if not text:
            return None

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]

        try:
            parsed = json.loads(text)
            raw = parsed.get("score")
            if isinstance(raw, (int, float)):
                return float(raw)
            if isinstance(raw, str):
                return float(raw.strip())
        except Exception:
            pass

        m = re.search(r"(-?\d+(?:\.\d+)?)", text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None


class ModerationServiceIntimacyChecker(BaseIntimacyChecker):
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
        policy: str = "default",
        fail_open: bool = True,
        use_library: bool = True,
        allow_http_fallback: bool = True,
        llm_adapter: BaseLLMAdapter | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._policy = policy
        self._fail_open = fail_open
        self._use_library = use_library
        self._allow_http_fallback = allow_http_fallback
        self._llm_adapter = llm_adapter
        self._llm_provider = llm_provider
        self._llm_model = llm_model
        self._client = httpx.AsyncClient(timeout=self._timeout)

        self._library_service = None
        self._library_init_error: Exception | None = None
        if self._use_library:
            try:
                self._library_service = self._create_library_service()
            except Exception as e:
                self._library_init_error = e

    def _create_library_service(self):
        try:
            from moderation_service.core.service import ModerationService  # type: ignore
        except ModuleNotFoundError:
            project_root = Path(__file__).resolve().parents[2]
            moderation_root = project_root / "core" / "moderation-service"
            if moderation_root.exists() and str(moderation_root) not in sys.path:
                sys.path.insert(0, str(moderation_root))
            from moderation_service.core.service import ModerationService  # type: ignore

        plugin_config = None
        if self._llm_adapter is not None:
            plugin_config = {
                "intimacy": {
                    "third_party_adapter": PromptLLMThirdPartyIntimacyAdapter(
                        llm_adapter=self._llm_adapter,
                        provider=self._llm_provider,
                        model=self._llm_model,
                    )
                }
            }

        return ModerationService(
            plugin_config=plugin_config,
            default_policy=self._policy,
            default_dimensions=["intimacy"],
        )

    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult:
        intimacy_stage = self._convert_intimacy_to_stage(input.intimacy_level)

        profile: dict[str, Any] = {
            "persona": input.persona.prompt,
            "intimacy_stage": intimacy_stage,
        }

        payload: dict[str, Any] = {
            "text": input.reply_text,
            "dimensions": ["intimacy"],
            "context": {
                "profile": profile,
                "profile_version": "v1.0",
            },
            "policy": self._policy,
        }

        try:
            data = await self._check_via_library(payload)
            if data is None:
                data = await self._check_via_http(payload)

            decision = str(((data.get("decision") or {}).get("final") or "")).strip().lower()
            intimacy_result = (data.get("results") or {}).get("intimacy") or {}
            score_raw = intimacy_result.get("score", 0.0)
            try:
                score = float(score_raw)
            except Exception:
                score = 0.0

            passed = decision == "pass"
            reason = None
            if not passed:
                reason = intimacy_result.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    reason = f"moderation_decision={decision or 'unknown'}"

            return IntimacyCheckResult(passed=passed, score=score, reason=reason)

        except Exception as e:
            if self._fail_open:
                return IntimacyCheckResult(
                    passed=True,
                    score=1.0,
                    reason=f"moderation_service_unavailable: {type(e).__name__}",
                )
            return IntimacyCheckResult(
                passed=False,
                score=0.0,
                reason=f"moderation_service_error: {type(e).__name__}",
            )

    async def _check_via_library(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self._use_library:
            return None
        if self._library_service is None:
            if self._allow_http_fallback:
                return None
            if self._library_init_error is not None:
                raise self._library_init_error
            raise RuntimeError("moderation-service library mode init failed")

        return await self._library_service.check(
            text=payload.get("text", ""),
            dimensions=payload.get("dimensions"),
            context=payload.get("context"),
            policy=payload.get("policy"),
        )

    async def _check_via_http(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._allow_http_fallback:
            raise RuntimeError("HTTP fallback disabled")

        resp = await self._client.post(f"{self._base_url}/moderation/check", json=payload)
        resp.raise_for_status()
        return resp.json()

    def _convert_intimacy_to_stage(self, intimacy_level_0_100: int) -> int:
        if intimacy_level_0_100 <= 20:
            return 1
        if intimacy_level_0_100 <= 40:
            return 2
        if intimacy_level_0_100 <= 60:
            return 3
        if intimacy_level_0_100 <= 80:
            return 4
        return 5
