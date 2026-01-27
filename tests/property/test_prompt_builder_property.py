"""Property-based tests for Prompt Builder component.

Tests:
- Property 8: Prompt Construction Completeness

Validates: Requirements 3.1, 3.2
"""

import json
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
    both a system prompt containing task definition and a user prompt containing
    parsing rules and JSON schema.
    
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
        return a tuple of (system_prompt, user_prompt) where both are non-empty strings.
        
        **Validates: Requirements 3.1, 3.2**
        """
        builder = PromptBuilder()
        
        # Build prompts
        system_prompt, user_prompt = builder.build_prompts(options)
        
        # Verify both prompts are returned
        assert isinstance(system_prompt, str), "System prompt should be a string"
        assert isinstance(user_prompt, str), "User prompt should be a string"
        
        # Verify both prompts are non-empty
        assert len(system_prompt) > 0, "System prompt should not be empty"
        assert len(user_prompt) > 0, "User prompt should not be empty"
    
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
    def test_system_prompt_specifies_output_format_requirements(
        self, options: ParseOptions
    ):
        """
        Property 8: System prompt specifies output format requirements
        
        For any ParseOptions configuration, the system prompt should specify
        that sender must be "user" or "talker" and column must be "left" or "right".
        
        **Validates: Requirements 3.1**
        """
        builder = PromptBuilder()
        
        # Build prompts
        system_prompt, _ = builder.build_prompts(options)
        
        system_prompt_lower = system_prompt.lower()
        
        # Verify sender requirements
        assert "user" in system_prompt_lower, "System prompt should mention 'user'"
        assert "talker" in system_prompt_lower, "System prompt should mention 'talker'"
        
        # Verify column requirements
        assert "left" in system_prompt_lower, "System prompt should mention 'left'"
        assert "right" in system_prompt_lower, "System prompt should mention 'right'"
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_user_prompt_contains_parsing_rules(self, options: ParseOptions):
        """
        Property 8: User prompt contains parsing rules
        
        For any ParseOptions configuration, the user prompt should contain
        parsing rules about bubble positioning and sender attribution.
        
        **Validates: Requirements 3.2**
        """
        builder = PromptBuilder()
        
        # Build prompts
        _, user_prompt = builder.build_prompts(options)
        
        # Verify user prompt contains parsing rules
        user_prompt_lower = user_prompt.lower()
        
        # Basic parsing rules should always be present
        assert "parse" in user_prompt_lower, "User prompt should mention 'parse'"
        assert "left" in user_prompt_lower, "User prompt should mention 'left'"
        assert "right" in user_prompt_lower, "User prompt should mention 'right'"
        assert "bubbles" in user_prompt_lower or "bubble" in user_prompt_lower, (
            "User prompt should mention 'bubbles'"
        )
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_user_prompt_contains_json_schema(self, options: ParseOptions):
        """
        Property 8: User prompt contains JSON schema
        
        For any ParseOptions configuration, the user prompt should contain
        a JSON schema template defining the expected output structure.
        
        **Validates: Requirements 3.2**
        """
        builder = PromptBuilder()
        
        # Build prompts
        _, user_prompt = builder.build_prompts(options)
        
        # Verify user prompt contains JSON schema
        user_prompt_lower = user_prompt.lower()
        
        # Schema should mention key fields
        schema_fields = [
            "image_meta",
            "participants",
            "bubbles",
            "layout",
            "bbox",
            "bubble_id",
        ]
        
        for field in schema_fields:
            assert field in user_prompt_lower, (
                f"User prompt should contain JSON schema field '{field}'"
            )
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_user_prompt_json_schema_is_valid_json(self, options: ParseOptions):
        """
        Property 8: User prompt contains valid JSON schema
        
        For any ParseOptions configuration, the JSON schema in the user prompt
        should be valid JSON that can be parsed.
        
        **Validates: Requirements 3.2**
        """
        builder = PromptBuilder()
        
        # Build prompts
        _, user_prompt = builder.build_prompts(options)
        
        # Extract JSON from user prompt (it should be after "Return this exact JSON structure:")
        # Find the JSON block
        json_start = user_prompt.find("{")
        json_end = user_prompt.rfind("}") + 1
        
        assert json_start != -1, "User prompt should contain JSON schema starting with '{'"
        assert json_end > json_start, "User prompt should contain JSON schema ending with '}'"
        
        json_text = user_prompt[json_start:json_end]
        
        # Verify it's valid JSON
        try:
            parsed_schema = json.loads(json_text)
        except json.JSONDecodeError as e:
            pytest.fail(f"JSON schema in user prompt is not valid JSON: {e}")
        
        # Verify schema has expected top-level keys
        expected_keys = ["image_meta", "participants", "bubbles", "layout"]
        for key in expected_keys:
            assert key in parsed_schema, f"JSON schema should have '{key}' key"
    
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
    def test_user_prompt_includes_two_column_hint_when_forced(
        self, options: ParseOptions
    ):
        """
        Property 8: User prompt includes two-column hint when force_two_columns=True
        
        For any ParseOptions with force_two_columns=True, the user prompt should
        include hints about two-column layout assumptions.
        
        **Validates: Requirements 3.2, 6.6**
        """
        builder = PromptBuilder()
        
        # Build prompts
        _, user_prompt = builder.build_prompts(options)
        
        user_prompt_lower = user_prompt.lower()
        
        if options.force_two_columns:
            # Should contain two-column hints
            assert "two-column" in user_prompt_lower or "two column" in user_prompt_lower, (
                "User prompt should mention 'two-column' when force_two_columns=True"
            )
        # Note: We don't test the negative case because the default might include it anyway
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_user_prompt_includes_app_specific_hints(self, options: ParseOptions):
        """
        Property 8: User prompt includes app-specific hints when app_type is specified
        
        For any ParseOptions with app_type != "unknown", the user prompt should
        include app-specific parsing hints.
        
        **Validates: Requirements 3.2, 6.7**
        """
        builder = PromptBuilder()
        
        # Build prompts
        _, user_prompt = builder.build_prompts(options)
        
        user_prompt_lower = user_prompt.lower()
        
        if options.app_type != "unknown":
            # Should contain app-specific hints
            assert options.app_type.lower() in user_prompt_lower, (
                f"User prompt should mention '{options.app_type}' when app_type={options.app_type}"
            )
    
    @settings(max_examples=100)
    @given(options=parse_options_strategy())
    def test_user_prompt_includes_nickname_rule_when_needed(
        self, options: ParseOptions
    ):
        """
        Property 8: User prompt includes nickname extraction rule when need_nickname=True
        
        For any ParseOptions with need_nickname=True, the user prompt should
        include a rule about extracting nicknames.
        
        **Validates: Requirements 3.2, 6.8**
        """
        builder = PromptBuilder()
        
        # Build prompts
        _, user_prompt = builder.build_prompts(options)
        
        user_prompt_lower = user_prompt.lower()
        
        if options.need_nickname:
            # Should contain nickname extraction rule
            assert "nickname" in user_prompt_lower, (
                "User prompt should mention 'nickname' when need_nickname=True"
            )
    
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
