"""Property-based tests for Prompt Builder component.

Tests:
- Property 8: Prompt Construction Completeness

Validates: Requirements 3.1, 3.2
"""

import pytest
from hypothesis import given, settings, strategies as st

from app.models.screenshot import ParseOptions
from app.services.prompt_builder import PromptBuilder


# Strategies for generating test data

@st.composite
def parse_options_strategy(draw):
    """Generate arbitrary ParseOptions configurations."""
    need_nickname = draw(st.booleans())
    need_sender = draw(st.booleans())
    force_two_columns = draw(st.booleans())
    app_type = draw(st.sampled_from(["wechat", "line", "whatsapp", "unknown"]))
    
    return ParseOptions(
        need_nickname=need_nickname,
        need_sender=need_sender,
        force_two_columns=force_two_columns,
        app_type=app_type,
    )


class TestPromptConstructionCompleteness:
    """
    Property 8: Prompt Construction Completeness
    
    *For any* ParseOptions configuration, the Prompt_Builder should generate
    a system prompt loaded from prompt management. The user prompt is intentionally
    empty to prevent large prompt edits via Python code.
    
    **Feature: chat-screenshot-parser, Property 8: Prompt Construction Completeness**
    **Validates: Requirements 3.1, 3.2**
    """
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_build_prompts_returns_both_system_and_user_prompts(
        self, options: ParseOptions
    ):
        """
        Property 8: build_prompts returns both system and user prompts
        
        For any ParseOptions configuration, the build_prompts method should
        return a tuple of (system_prompt, user_prompt) where system_prompt is non-empty
        and user_prompt is an empty string.
        
        **Validates: Requirements 3.1, 3.2**
        """
        builder = PromptBuilder()
        
        # Build prompts
        system_prompt, user_prompt = builder.build_prompts(options)
        
        # Verify both prompts are returned
        assert isinstance(system_prompt, str), "System prompt should be a string"
        assert isinstance(user_prompt, str), "User prompt should be a string"

        # Verify system prompt is non-empty and user prompt is empty
        assert len(system_prompt) > 0, "System prompt should not be empty"
        assert user_prompt == "", "User prompt should be empty"
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_system_prompt_contains_task_definition(self, options: ParseOptions):
        """
        Property 8: System prompt contains task definition
        
        For any ParseOptions configuration, the system prompt should contain
        key elements defining the parsing task (bounding box, text extraction,
        sender attribution, JSON format).
        
        **Validates: Requirements 3.1**
        """
        builder = PromptBuilder()
        
        # Build prompts
        system_prompt, _ = builder.build_prompts(options)
        
        # Verify system prompt contains task definition elements
        # These are key phrases from the system prompt template (case-insensitive)
        task_elements = [
            "chat screenshot",  # Task context
            "bounding box",     # Bounding box identification
            "text content",     # Text extraction
            "sender",           # Sender attribution
            "json",             # Output format
        ]
        
        system_prompt_lower = system_prompt.lower()
        for element in task_elements:
            assert element in system_prompt_lower, (
                f"System prompt should contain '{element}' but got: {system_prompt}"
            )
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_user_prompt_is_empty(self, options: ParseOptions):
        builder = PromptBuilder()
        _, user_prompt = builder.build_prompts(options)
        assert user_prompt == "", "User prompt should be empty"
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_system_prompt_is_consistent_across_options(self, options: ParseOptions):
        """
        Property 8: System prompt is consistent across options
        
        For any ParseOptions configuration, the system prompt should be
        consistent (not affected by options), as it defines the core task.
        
        **Validates: Requirements 3.1**
        """
        builder = PromptBuilder()
        
        # Build prompts with given options
        system_prompt_1, _ = builder.build_prompts(options)
        
        # Build prompts with different options
        different_options = ParseOptions(
            need_nickname=not options.need_nickname,
            need_sender=not options.need_sender,
            force_two_columns=not options.force_two_columns,
            app_type="unknown" if options.app_type != "unknown" else "wechat",
        )
        system_prompt_2, _ = builder.build_prompts(different_options)
        
        # System prompt should be the same regardless of options
        assert system_prompt_1 == system_prompt_2, (
            "System prompt should be consistent across different ParseOptions"
        )
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_user_prompt_does_not_depend_on_options(self, options: ParseOptions):
        builder = PromptBuilder()
        _, user_prompt = builder.build_prompts(options)
        assert user_prompt == "", "User prompt should always be empty"
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_prompts_are_deterministic_for_same_options(self, options: ParseOptions):
        """
        Property 8: Prompts are deterministic for same options
        
        For any ParseOptions configuration, calling build_prompts multiple times
        with the same options should produce identical results.
        
        **Validates: Requirements 3.1, 3.2**
        """
        builder = PromptBuilder()
        
        # Build prompts multiple times with same options
        system_1, user_1 = builder.build_prompts(options)
        system_2, user_2 = builder.build_prompts(options)
        system_3, user_3 = builder.build_prompts(options)
        
        # All should be identical
        assert system_1 == system_2 == system_3, (
            "System prompt should be deterministic for same options"
        )
        assert user_1 == user_2 == user_3, (
            "User prompt should be deterministic for same options"
        )
