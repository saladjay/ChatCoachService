"""Data persistence service for the conversation generation system.

This module provides methods to persist:
- Scene analysis results (scene_analysis_log)
- User persona snapshots (persona_snapshot)
- LLM call logs (llm_call_log)
- Intimacy check results (intimacy_check_log)
- Final generation results (generation_result)

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc

from app.db.models import (
    ConversationSummaryLog,
    GenerationResultModel,
    IntimacyCheckLog,
    LLMCallLog,
    PersonaSnapshotModel,
    SceneAnalysisLog,
)
from app.models.schemas import (
    IntimacyCheckResult,
    LLMCallRecord,
    PersonaSnapshot,
    SceneAnalysisResult,
)


class PersistenceService:
    """Service for persisting data to the database.
    
    Provides methods to store and retrieve various log types
    for the conversation generation system.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the persistence service.
        
        Args:
            session: An async SQLAlchemy session.
        """
        self._session = session

    async def save_scene_analysis(
        self,
        conversation_id: str,
        result: SceneAnalysisResult,
        model: str,
        provider: str,
    ) -> int:
        """Save scene analysis result to database.
        
        Args:
            conversation_id: The conversation identifier.
            result: The scene analysis result.
            model: The LLM model used.
            provider: The LLM provider used.
            
        Returns:
            The ID of the created record.
            
        Requirements: 6.1
        """
        log = SceneAnalysisLog(
            conversation_id=conversation_id,
            scene=result.scene,
            intimacy_level=result.intimacy_level,
            risk_flags={"flags": result.risk_flags},
            model=model,
            provider=provider,
        )
        self._session.add(log)
        await self._session.flush()
        return log.id


    async def save_persona_snapshot(
        self,
        user_id: str,
        conversation_id: str,
        persona: PersonaSnapshot,
    ) -> int:
        """Save persona snapshot to database.
        
        Args:
            user_id: The user identifier.
            conversation_id: The conversation identifier.
            persona: The inferred persona snapshot.
            
        Returns:
            The ID of the created record.
            
        Requirements: 6.2
        """
        snapshot = PersonaSnapshotModel(
            user_id=user_id,
            conversation_id=conversation_id,
            style=persona.style,
            pacing=persona.pacing,
            risk_tolerance=persona.risk_tolerance,
            confidence=persona.confidence,
        )
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot.id

    async def save_llm_call_log(self, record: LLMCallRecord) -> int:
        """Save LLM call log to database.
        
        Args:
            record: The LLM call record.
            
        Returns:
            The ID of the created record.
            
        Requirements: 6.3
        """
        log = LLMCallLog(
            user_id=record.user_id,
            task_type=record.task_type,
            provider=record.provider,
            model=record.model,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            cost_usd=record.cost_usd,
            latency_ms=record.latency_ms,
        )
        self._session.add(log)
        await self._session.flush()
        return log.id

    async def save_intimacy_check(
        self,
        conversation_id: str,
        reply_text: str,
        result: IntimacyCheckResult,
        model: str,
    ) -> int:
        """Save intimacy check result to database.
        
        Args:
            conversation_id: The conversation identifier.
            reply_text: The reply text that was checked.
            result: The intimacy check result.
            model: The LLM model used for checking.
            
        Returns:
            The ID of the created record.
            
        Requirements: 6.4
        """
        log = IntimacyCheckLog(
            conversation_id=conversation_id,
            reply_text=reply_text,
            passed=result.passed,
            score=result.score,
            reason=result.reason,
            model=model,
        )
        self._session.add(log)
        await self._session.flush()
        return log.id

    async def save_generation_result(
        self,
        conversation_id: str,
        reply_text: str,
        intimacy_before: int,
        intimacy_after: int,
        model: str,
        provider: str,
        cost_usd: float,
    ) -> int:
        """Save final generation result to database.
        
        Args:
            conversation_id: The conversation identifier.
            reply_text: The generated reply text.
            intimacy_before: Intimacy level before generation.
            intimacy_after: Intimacy level after generation.
            model: The LLM model used.
            provider: The LLM provider used.
            cost_usd: Total cost in USD.
            
        Returns:
            The ID of the created record.
            
        Requirements: 6.5
        """
        result = GenerationResultModel(
            conversation_id=conversation_id,
            reply_text=reply_text,
            intimacy_before=intimacy_before,
            intimacy_after=intimacy_after,
            model=model,
            provider=provider,
            cost_usd=cost_usd,
        )
        self._session.add(result)
        await self._session.flush()
        return result.id

    async def save_conversation_summary(
        self,
        user_id: str,
        target_id: str,
        conversation_id: str,
        summary: str,
    ) -> int:
        log = ConversationSummaryLog(
            user_id=user_id,
            target_id=target_id,
            conversation_id=conversation_id,
            summary=summary,
        )
        self._session.add(log)
        await self._session.flush()
        return log.id

    async def list_conversation_summaries(
        self,
        user_id: str,
        target_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConversationSummaryLog]:
        stmt = (
            select(ConversationSummaryLog)
            .where(
                ConversationSummaryLog.user_id == user_id,
                ConversationSummaryLog.target_id == target_id,
            )
            .order_by(desc(ConversationSummaryLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


    # Retrieval methods

    async def get_scene_analysis_by_id(self, log_id: int) -> SceneAnalysisLog | None:
        """Retrieve scene analysis log by ID.
        
        Args:
            log_id: The log record ID.
            
        Returns:
            The scene analysis log or None if not found.
        """
        result = await self._session.execute(
            select(SceneAnalysisLog).where(SceneAnalysisLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def get_persona_snapshot_by_id(self, snapshot_id: int) -> PersonaSnapshotModel | None:
        """Retrieve persona snapshot by ID.
        
        Args:
            snapshot_id: The snapshot record ID.
            
        Returns:
            The persona snapshot or None if not found.
        """
        result = await self._session.execute(
            select(PersonaSnapshotModel).where(PersonaSnapshotModel.id == snapshot_id)
        )
        return result.scalar_one_or_none()

    async def get_llm_call_log_by_id(self, log_id: int) -> LLMCallLog | None:
        """Retrieve LLM call log by ID.
        
        Args:
            log_id: The log record ID.
            
        Returns:
            The LLM call log or None if not found.
        """
        result = await self._session.execute(
            select(LLMCallLog).where(LLMCallLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def get_intimacy_check_by_id(self, log_id: int) -> IntimacyCheckLog | None:
        """Retrieve intimacy check log by ID.
        
        Args:
            log_id: The log record ID.
            
        Returns:
            The intimacy check log or None if not found.
        """
        result = await self._session.execute(
            select(IntimacyCheckLog).where(IntimacyCheckLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def get_generation_result_by_id(self, result_id: int) -> GenerationResultModel | None:
        """Retrieve generation result by ID.
        
        Args:
            result_id: The result record ID.
            
        Returns:
            The generation result or None if not found.
        """
        result = await self._session.execute(
            select(GenerationResultModel).where(GenerationResultModel.id == result_id)
        )
        return result.scalar_one_or_none()

    async def get_scene_analyses_by_conversation(
        self, conversation_id: str
    ) -> list[SceneAnalysisLog]:
        """Retrieve all scene analyses for a conversation.
        
        Args:
            conversation_id: The conversation identifier.
            
        Returns:
            List of scene analysis logs.
        """
        result = await self._session.execute(
            select(SceneAnalysisLog)
            .where(SceneAnalysisLog.conversation_id == conversation_id)
            .order_by(SceneAnalysisLog.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_llm_calls_by_user(self, user_id: str) -> list[LLMCallLog]:
        """Retrieve all LLM call logs for a user.
        
        Args:
            user_id: The user identifier.
            
        Returns:
            List of LLM call logs.
        """
        result = await self._session.execute(
            select(LLMCallLog)
            .where(LLMCallLog.user_id == user_id)
            .order_by(LLMCallLog.created_at.desc())
        )
        return list(result.scalars().all())
