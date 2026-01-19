"""Billing service for tracking LLM call costs and user quotas.

This module implements:
- record_call: Record individual LLM call costs
- get_total_cost: Get accumulated cost for a user
- check_quota: Check if user has remaining quota

Requirements: 5.1, 5.2, 5.3, 5.4
"""

from datetime import datetime
from typing import Protocol

from app.models.schemas import LLMCallRecord


class BillingService:
    """Service for tracking LLM call costs and managing user quotas.
    
    This service maintains in-memory records of LLM calls and provides
    methods for cost tracking and quota enforcement.
    
    Attributes:
        default_quota_usd: Default quota for users without explicit quota.
        _records: In-memory storage of LLM call records.
        _user_quotas: User-specific quota overrides.
    """

    def __init__(self, default_quota_usd: float = 10.0):
        """Initialize the billing service.
        
        Args:
            default_quota_usd: Default quota in USD for users.
        """
        self.default_quota_usd = default_quota_usd
        self._records: list[LLMCallRecord] = []
        self._user_quotas: dict[str, float] = {}

    async def record_call(self, record: LLMCallRecord) -> None:
        """Record an LLM call for billing purposes.
        
        Args:
            record: LLMCallRecord containing provider, model, tokens, and cost.
        
        Requirements: 5.1
        """
        self._records.append(record)

    async def get_total_cost(self, user_id: str) -> float:
        """Get the total accumulated cost for a user.
        
        Args:
            user_id: The user identifier to query.
        
        Returns:
            Total cost in USD for all recorded calls by this user.
        
        Requirements: 5.2, 5.3
        """
        return sum(
            record.cost_usd 
            for record in self._records 
            if record.user_id == user_id
        )

    async def check_quota(self, user_id: str) -> bool:
        """Check if a user has remaining quota.
        
        Args:
            user_id: The user identifier to check.
        
        Returns:
            True if user has remaining quota, False otherwise.
        
        Requirements: 5.4
        """
        total_cost = await self.get_total_cost(user_id)
        quota = self._user_quotas.get(user_id, self.default_quota_usd)
        return total_cost < quota

    def set_user_quota(self, user_id: str, quota_usd: float) -> None:
        """Set a custom quota for a specific user.
        
        Args:
            user_id: The user identifier.
            quota_usd: The quota amount in USD.
        """
        self._user_quotas[user_id] = quota_usd

    async def get_user_records(self, user_id: str) -> list[LLMCallRecord]:
        """Get all billing records for a specific user.
        
        Args:
            user_id: The user identifier to query.
        
        Returns:
            List of LLMCallRecord for the user.
        """
        return [
            record for record in self._records 
            if record.user_id == user_id
        ]

    async def get_session_cost(self, records: list[LLMCallRecord]) -> float:
        """Calculate total cost from a list of records.
        
        Used to sum costs for a single generation session.
        
        Args:
            records: List of LLMCallRecord from a session.
        
        Returns:
            Total cost in USD.
        
        Requirements: 5.2
        """
        return sum(record.cost_usd for record in records)
