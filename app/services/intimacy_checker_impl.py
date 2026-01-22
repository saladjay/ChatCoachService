from __future__ import annotations

from typing import Any

import sys
from pathlib import Path

import httpx

from app.models.schemas import IntimacyCheckInput, IntimacyCheckResult
from app.services.base import BaseIntimacyChecker


class ModerationServiceIntimacyChecker(BaseIntimacyChecker):
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
        policy: str = "default",
        fail_open: bool = True,
        use_library: bool = True,
        allow_http_fallback: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._policy = policy
        self._fail_open = fail_open
        self._use_library = use_library
        self._allow_http_fallback = allow_http_fallback
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

        return ModerationService(
            plugin_config=None,
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
