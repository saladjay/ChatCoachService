"""Property-based tests for Orchestrator service.

Tests:
- Property 3: Service Invocation Order
- Property 4: Retry Limit Enforcement

Validates: Requirements 2.1, 2.2, 2.3, 2.4
"""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

import pytest
from hypothesis import given, settings, strategies as st

from app.models.api import GenerateReplyRequest
from app.models.schemas import (
    ContextBuilderInput,
    ContextResult,
    IntimacyCheckInput,
    IntimacyCheckResult,
    LLMResult,
    OrchestratorConfig,
    PersonaInferenceInput,
    PersonaSnapshot,
    ReplyGenerationInput,
    SceneAnalysisInput,
    SceneAnalysisResult,
)
from app.services.base import (
    BaseContextBuilder,
    BaseIntimacyChecker,
    BasePersonaInferencer,
    BaseReplyGenerator,
    BaseSceneAnalyzer,
)
from app.services.billing import BillingService
from app.services.orchestrator import Orchestrator


@dataclass
class InvocationTracker:
    """Tracks the order of service invocations."""
    
    invocations: list[str] = field(default_factory=list)
    
    def record(self, service_name: str) -> None:
        self.invocations.append(service_name)
    
    def clear(self) -> None:
        self.invocations.clear()


class TrackingContextBuilder(BaseContextBuilder):
    """Context builder that tracks invocations."""
    
    def __init__(self, tracker: InvocationTracker):
        self.tracker = tracker
    
    async def build_context(self, input: ContextBuilderInput) -> ContextResult:
        self.tracker.record("context_builder")
        return ContextResult(
            conversation_summary="Test summary",
            emotion_state="neutral",
            current_intimacy_level=3,
            risk_flags=[],
        )


class TrackingSceneAnalyzer(BaseSceneAnalyzer):
    """Scene analyzer that tracks invocations."""
    
    def __init__(self, tracker: InvocationTracker):
        self.tracker = tracker
    
    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        self.tracker.record("scene_analysis")
        return SceneAnalysisResult(
            scene="维持",
            intimacy_level=3,
            risk_flags=[],
        )


class TrackingPersonaInferencer(BasePersonaInferencer):
    """Persona inferencer that tracks invocations."""
    
    def __init__(self, tracker: InvocationTracker):
        self.tracker = tracker
    
    async def infer_persona(self, input: PersonaInferenceInput) -> PersonaSnapshot:
        self.tracker.record("persona_inference")
        return PersonaSnapshot(
            style="理性",
            pacing="normal",
            risk_tolerance="medium",
            confidence=0.8,
        )


class TrackingReplyGenerator(BaseReplyGenerator):
    """Reply generator that tracks invocations."""
    
    def __init__(self, tracker: InvocationTracker):
        self.tracker = tracker
    
    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult:
        self.tracker.record("reply_generation")
        return LLMResult(
            text="Test reply",
            provider="test",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
        )


class TrackingIntimacyChecker(BaseIntimacyChecker):
    """Intimacy checker that tracks invocations and can be configured to fail."""
    
    def __init__(self, tracker: InvocationTracker, should_pass: bool = True):
        self.tracker = tracker
        self.should_pass = should_pass
        self.check_count = 0
    
    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult:
        self.tracker.record("intimacy_check")
        self.check_count += 1
        return IntimacyCheckResult(
            passed=self.should_pass,
            score=0.9 if self.should_pass else 0.3,
            reason=None if self.should_pass else "Test failure",
        )


class ConfigurableIntimacyChecker(BaseIntimacyChecker):
    """Intimacy checker that fails a configurable number of times before passing."""
    
    def __init__(self, tracker: InvocationTracker, fail_count: int):
        self.tracker = tracker
        self.fail_count = fail_count
        self.check_count = 0
    
    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult:
        self.tracker.record("intimacy_check")
        self.check_count += 1
        
        if self.check_count <= self.fail_count:
            return IntimacyCheckResult(
                passed=False,
                score=0.3,
                reason=f"Test failure {self.check_count}",
            )
        return IntimacyCheckResult(
            passed=True,
            score=0.9,
            reason=None,
        )


# Strategies for generating test data
user_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).filter(lambda x: len(x.strip()) > 0)

quality_strategy = st.sampled_from(["cheap", "normal", "premium"])


def create_request(user_id: str, quality: str) -> GenerateReplyRequest:
    """Create a valid GenerateReplyRequest for testing."""
    return GenerateReplyRequest(
        user_id=user_id or "test_user",
        target_id="target_123",
        conversation_id="conv_123",
        language="en",  # Default to English
        quality=quality,
        force_regenerate=False,
    )


class TestServiceInvocationOrder:
    """
    Property 3: Service Invocation Order
    
    *For any* successful generation flow, the Orchestrator SHALL invoke services
    in the exact order: Context_Builder → Scene_Analysis → Persona_Inference →
    Reply_Generation → Intimacy_Check, and each service SHALL receive the output
    of its predecessor.
    
    **Feature: conversation-generation-service, Property 3: Service Invocation Order**
    **Validates: Requirements 2.1, 2.2**
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        quality=quality_strategy,
    )
    async def test_service_invocation_order(
        self,
        user_id: str,
        quality: Literal["cheap", "normal", "premium"],
    ):
        """
        Property 3: Service Invocation Order
        
        For any successful generation request, services must be invoked in order:
        Context_Builder → Scene_Analysis → Persona_Inference → Reply_Generation → Intimacy_Check
        
        **Validates: Requirements 2.1, 2.2**
        """
        # Setup tracking
        tracker = InvocationTracker()
        
        # Create tracking services
        context_builder = TrackingContextBuilder(tracker)
        scene_analyzer = TrackingSceneAnalyzer(tracker)
        persona_inferencer = TrackingPersonaInferencer(tracker)
        reply_generator = TrackingReplyGenerator(tracker)
        intimacy_checker = TrackingIntimacyChecker(tracker, should_pass=True)
        billing_service = BillingService()
        
        # Create orchestrator
        orchestrator = Orchestrator(
            context_builder=context_builder,
            scene_analyzer=scene_analyzer,
            persona_inferencer=persona_inferencer,
            reply_generator=reply_generator,
            intimacy_checker=intimacy_checker,
            billing_service=billing_service,
            config=OrchestratorConfig(max_retries=3, timeout_seconds=30.0),
        )
        
        # Create request
        request = create_request(user_id, quality)
        
        # Execute
        response = await orchestrator.generate_reply(request)
        
        # Verify invocation order
        expected_order = [
            "context_builder",
            "scene_analysis",
            "persona_inference",
            "reply_generation",
            "intimacy_check",
        ]
        
        assert tracker.invocations == expected_order, (
            f"Expected invocation order {expected_order}, "
            f"but got {tracker.invocations}"
        )
        
        # Verify response is valid
        assert response.reply_text is not None
        assert response.confidence >= 0.0
        assert response.confidence <= 1.0


class TestRetryLimitEnforcement:
    """
    Property 4: Retry Limit Enforcement
    
    *For any* generation request where Intimacy_Check fails, the system SHALL
    retry at most max_retries times (default 3), and after exhausting retries
    SHALL return a fallback response or error.
    
    **Feature: conversation-generation-service, Property 4: Retry Limit Enforcement**
    **Validates: Requirements 2.3, 2.4**
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        quality=quality_strategy,
        max_retries=st.integers(min_value=1, max_value=5),
    )
    async def test_retry_limit_enforcement(
        self,
        user_id: str,
        quality: Literal["cheap", "normal", "premium"],
        max_retries: int,
    ):
        """
        Property 4: Retry Limit Enforcement
        
        For any generation request where Intimacy_Check always fails,
        the system retries at most max_retries times.
        
        **Validates: Requirements 2.3, 2.4**
        """
        # Setup tracking
        tracker = InvocationTracker()
        
        # Create services with always-failing intimacy checker
        context_builder = TrackingContextBuilder(tracker)
        scene_analyzer = TrackingSceneAnalyzer(tracker)
        persona_inferencer = TrackingPersonaInferencer(tracker)
        reply_generator = TrackingReplyGenerator(tracker)
        intimacy_checker = TrackingIntimacyChecker(tracker, should_pass=False)
        billing_service = BillingService()
        
        # Create orchestrator with configurable max_retries
        config = OrchestratorConfig(
            max_retries=max_retries,
            timeout_seconds=30.0,
        )
        
        orchestrator = Orchestrator(
            context_builder=context_builder,
            scene_analyzer=scene_analyzer,
            persona_inferencer=persona_inferencer,
            reply_generator=reply_generator,
            intimacy_checker=intimacy_checker,
            billing_service=billing_service,
            config=config,
        )
        
        # Create request
        request = create_request(user_id, quality)
        
        # Execute - should not raise, should return fallback
        response = await orchestrator.generate_reply(request)
        
        # Count intimacy check invocations
        intimacy_check_count = tracker.invocations.count("intimacy_check")
        
        # Verify retry limit is enforced
        assert intimacy_check_count == max_retries, (
            f"Expected exactly {max_retries} intimacy checks, "
            f"but got {intimacy_check_count}"
        )
        
        # Verify response is returned (fallback or last attempt)
        assert response is not None
        assert response.reply_text is not None
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        quality=quality_strategy,
        max_retries=st.integers(min_value=2, max_value=5),
        fail_count=st.integers(min_value=1, max_value=4),
    )
    async def test_retry_stops_on_success(
        self,
        user_id: str,
        quality: Literal["cheap", "normal", "premium"],
        max_retries: int,
        fail_count: int,
    ):
        """
        Property 4 (corollary): Retry stops when Intimacy_Check passes
        
        For any generation request where Intimacy_Check fails N times then passes,
        the system should stop retrying after the successful check.
        
        **Validates: Requirements 2.3**
        """
        # Ensure fail_count is less than max_retries for this test
        fail_count = min(fail_count, max_retries - 1)
        
        # Setup tracking
        tracker = InvocationTracker()
        
        # Create services with configurable intimacy checker
        context_builder = TrackingContextBuilder(tracker)
        scene_analyzer = TrackingSceneAnalyzer(tracker)
        persona_inferencer = TrackingPersonaInferencer(tracker)
        reply_generator = TrackingReplyGenerator(tracker)
        intimacy_checker = ConfigurableIntimacyChecker(tracker, fail_count=fail_count)
        billing_service = BillingService()
        
        # Create orchestrator
        config = OrchestratorConfig(
            max_retries=max_retries,
            timeout_seconds=30.0,
        )
        
        orchestrator = Orchestrator(
            context_builder=context_builder,
            scene_analyzer=scene_analyzer,
            persona_inferencer=persona_inferencer,
            reply_generator=reply_generator,
            intimacy_checker=intimacy_checker,
            billing_service=billing_service,
            config=config,
        )
        
        # Create request
        request = create_request(user_id, quality)
        
        # Execute
        response = await orchestrator.generate_reply(request)
        
        # Count intimacy check invocations
        intimacy_check_count = tracker.invocations.count("intimacy_check")
        
        # Should have exactly fail_count + 1 checks (failures + 1 success)
        expected_checks = fail_count + 1
        assert intimacy_check_count == expected_checks, (
            f"Expected {expected_checks} intimacy checks "
            f"({fail_count} failures + 1 success), "
            f"but got {intimacy_check_count}"
        )
        
        # Verify successful response
        assert response is not None
        assert response.reply_text is not None
