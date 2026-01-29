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
from app.services.prompt_manager import PromptType, PromptVersion, get_prompt_manager
from user_profile.intimacy import intimacy_label_en

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
        self._prompt_manager = get_prompt_manager()

    async def get_intimacy_score(self, text: str, context: dict[str, Any]) -> float:
        profile = (context or {}).get("profile") or {}
        intimacy_stage = profile.get("intimacy_stage")
        persona = profile.get("persona")

        prompt_template = self._prompt_manager.get_active_prompt(
            PromptType.INTIMACY_CHECK,
        )
        if not prompt_template:
            prompt_template = self._prompt_manager.get_prompt_version(
                PromptType.INTIMACY_CHECK,
                PromptVersion.V1_ORIGINAL,
            )
        prompt_template = (prompt_template or "").strip()
        prompt = prompt_template.format(
            persona=persona,
            intimacy_stage=intimacy_stage,
            text=text,
        )

        llm_call = LLMCall(
            task_type="qc",
            prompt=prompt,
            quality="normal",
            user_id="system",
            provider=self._provider,
            model=self._model,
            max_tokens=150,
        )

        try:
            result = await self._llm_adapter.call(llm_call)
            scores = self._parse_scores((result.text or "").strip())
            if not scores:
                raise ValueError("LLM response did not contain valid scores")
            self._last_scores = scores
            score = max(scores)
            return max(0.0, min(1.0, score))
        except Exception as e:
            self._last_scores = []
            try:
                from moderation_service.infrastructure.adapters import ThirdPartyAPIError  # type: ignore

                raise ThirdPartyAPIError(message=str(e), provider=self.provider) from e
            except ModuleNotFoundError:
                raise

    def _parse_scores(self, text: str) -> list[float]:
        if not text:
            return []

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
            raw_scores = parsed.get("scores")
            if isinstance(raw_scores, list):
                scores: list[float] = []
                for item in raw_scores:
                    if isinstance(item, (int, float)):
                        scores.append(float(item))
                    elif isinstance(item, str):
                        try:
                            scores.append(float(item.strip()))
                        except Exception:
                            continue
                return scores
            raw = parsed.get("score")
            if isinstance(raw, (int, float)):
                return [float(raw)]
            if isinstance(raw, str):
                return [float(raw.strip())]
        except Exception:
            pass

        matches = re.findall(r"(-?\d+(?:\.\d+)?)", text)
        scores = []
        for match in matches:
            try:
                scores.append(float(match))
            except Exception:
                continue
        return scores


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
        self._third_party_adapter: PromptLLMThirdPartyIntimacyAdapter | None = None
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
            self._third_party_adapter = PromptLLMThirdPartyIntimacyAdapter(
                llm_adapter=self._llm_adapter,
                provider=self._llm_provider,
                model=self._llm_model,
            )
            plugin_config = {
                "intimacy": {
                    "third_party_adapter": self._third_party_adapter
                }
            }

        return ModerationService(
            plugin_config=plugin_config,
            default_policy=self._policy,
            default_dimensions=["intimacy"],
        )

    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult:
        intimacy_stage = intimacy_label_en(input.intimacy_level)

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

            scores = []
            if self._third_party_adapter is not None:
                scores = list(self._third_party_adapter._last_scores or [])

            passed = decision == "pass"
            reason = None
            if scores:
                stage_gap = self._scores_exceed_stage_gap(intimacy_stage, scores)
                if stage_gap:
                    passed = False
                    reason = f"stage_gap_exceeded: {stage_gap}"

            if not passed and reason is None:
                reason = intimacy_result.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    reason = f"moderation_decision={decision or 'unknown'}"

            return IntimacyCheckResult(
                passed=passed,
                score=score,
                scores=scores,
                reason=reason,
            )

        except Exception as e:
            if self._fail_open:
                return IntimacyCheckResult(
                    passed=True,
                    score=1.0,
                    scores=[],
                    reason=f"moderation_service_unavailable: {type(e).__name__}",
                )
            return IntimacyCheckResult(
                passed=False,
                score=0.0,
                scores=[],
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

    @staticmethod
    def _score_to_stage(score: float) -> int:
        if score < 0.2:
            return 1
        if score < 0.4:
            return 2
        if score < 0.6:
            return 3
        if score < 0.8:
            return 4
        return 5

    def _scores_exceed_stage_gap(self, intimacy_stage: int, scores: list[float]) -> int | None:
        if not scores:
            return None
        max_gap = None
        for score in scores:
            stage = self._score_to_stage(score)
            gap = stage - intimacy_stage
            if gap >= 1:
                max_gap = max(max_gap or 0, gap)
        return max_gap
