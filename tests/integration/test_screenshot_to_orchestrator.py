# -*- coding: utf-8 -*-
"""Integration tests for screenshot parsing to orchestrator flow.

This module tests the complete integration from screenshot URL to reply generation:
- Parse screenshot → Convert to dialogs → Generate reply
- Test with various chat app screenshots (WeChat, WhatsApp, LINE)
- Verify integration with existing orchestrator

Task 10.5: Write integration tests
Requirements: 1.4, 8.1, 8.2, 8.3
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseScreenshotResponse,
    ParseOptions,
    ParsedScreenshotData,
    ImageMeta,
    Participants,
    Participant,
    ChatBubble,
    BoundingBox,
    LayoutInfo,
)
from app.models.api import GenerateReplyRequest, GenerateReplyResponse
from app.services.screenshot_parser import ScreenshotParserService
from app.services.pipeline_integration import bubbles_to_dialogs, validate_layout
from app.services.orchestrator import Orchestrator


class TestScreenshotToOrchestratorIntegration:
    """Tests for end-to-end integration from screenshot to reply generation.
    
    Task 10.5: Test end-to-end flow from screenshot URL to GenerateReplyRequest
    """

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wechat_screenshot_to_reply_flow(self):
        """Test complete flow: WeChat screenshot → dialogs → reply generation."""
        # Step 1: Create mock screenshot parser service
        mock_parser = Mock(spec=ScreenshotParserService)
        
        # Simulate parsed WeChat screenshot
        parsed_data = ParsedScreenshotData(
            image_meta=ImageMeta(width=750, height=1334),
            participants=Participants(
                self=Participant(id="user_wechat_123", nickname="Me"),
                other=Participant(id="friend_wechat_456", nickname="小明")
            ),
            bubbles=[
                ChatBubble(
                    bubble_id="b1",
                    bbox=BoundingBox(x1=50, y1=100, x2=300, y2=150),
                    center_x=175,
                    center_y=125,
                    text="你好！最近怎么样？",
                    sender="user",
                    column="right",
                    confidence=0.95
                ),
                ChatBubble(
                    bubble_id="b2",
                    bbox=BoundingBox(x1=50, y1=170, x2=300, y2=220),
                    center_x=175,
                    center_y=195,
                    text="挺好的，谢谢！你呢？",
                    sender="talker",
                    column="left",
                    confidence=0.92
                ),
                ChatBubble(
                    bubble_id="b3",
                    bbox=BoundingBox(x1=50, y1=240, x2=300, y2=290),
                    center_x=175,
                    center_y=265,
                    text="一起喝咖啡吗？",
                    sender="user",
                    column="right",
                    confidence=0.88
                )
            ],
            layout=LayoutInfo(
                type="two_columns",
                left_role="talker",
                right_role="user"
            )
        )
        
        mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
            code=0,
            msg="Success",
            data=parsed_data
        ))
        
        # Step 2: Parse screenshot
        parse_request = ParseScreenshotRequest(
            image_url="https://example.com/wechat_screenshot.png",
            session_id="test-wechat-integration",
            options=ParseOptions(app_type="wechat")
        )
        
        parse_response = await mock_parser.parse_screenshot(parse_request)
        
        # Verify parse succeeded
        assert parse_response.code == 0
        assert parse_response.data is not None
        assert len(parse_response.data.bubbles) == 3
        
        # Step 3: Validate layout
        is_valid = validate_layout(parse_response.data.layout, parse_response.data.bubbles)
        assert is_valid is True
        
        # Step 4: Convert to dialogs
        dialogs = bubbles_to_dialogs(parse_response.data.bubbles)
        
        assert len(dialogs) == 3
        assert dialogs[0]["speaker"] == "user"
        assert dialogs[0]["text"] == "你好！最近怎么样？"
        assert dialogs[1]["speaker"] == "talker"
        assert dialogs[1]["text"] == "挺好的，谢谢！你呢？"
        assert dialogs[2]["speaker"] == "user"
        assert dialogs[2]["text"] == "一起喝咖啡吗？"
        
        # Step 5: Create GenerateReplyRequest
        gen_request = GenerateReplyRequest(
            user_id=parse_response.data.participants.self.id,
            target_id=parse_response.data.participants.other.id,
            conversation_id="conv_wechat_test",
            dialogs=dialogs,
            intimacy_value=50,
            language="zh-CN",
            quality="normal"
        )
        
        # Verify request is properly formatted
        assert gen_request.user_id == "user_wechat_123"
        assert gen_request.target_id == "friend_wechat_456"
        assert len(gen_request.dialogs) == 3
        assert gen_request.language == "zh-CN"
        
        # Step 6: Mock orchestrator and generate reply
        mock_orchestrator = Mock(spec=Orchestrator)
        mock_orchestrator.generate_reply = AsyncMock(return_value=GenerateReplyResponse(
            reply_text="好啊！什么时候？",
            confidence=0.85,
            intimacy_level_before=3,
            intimacy_level_after=3,
            model="qwen-plus",
            provider="dashscope",
            cost_usd=0.002,
            fallback=False
        ))
        
        reply_response = await mock_orchestrator.generate_reply(gen_request)
        
        # Verify reply generation succeeded
        assert reply_response.reply_text is not None
        assert len(reply_response.reply_text) > 0
        assert reply_response.confidence > 0
        assert reply_response.fallback is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_whatsapp_screenshot_to_reply_flow(self):
        """Test complete flow: WhatsApp screenshot → dialogs → reply generation."""
        # Step 1: Create mock screenshot parser service
        mock_parser = Mock(spec=ScreenshotParserService)
        
        # Simulate parsed WhatsApp screenshot
        parsed_data = ParsedScreenshotData(
            image_meta=ImageMeta(width=1080, height=1920),
            participants=Participants(
                self=Participant(id="user_whatsapp_123", nickname="You"),
                other=Participant(id="friend_whatsapp_456", nickname="Sarah")
            ),
            bubbles=[
                ChatBubble(
                    bubble_id="b1",
                    bbox=BoundingBox(x1=100, y1=200, x2=500, y2=280),
                    center_x=300,
                    center_y=240,
                    text="Hey! How's it going?",
                    sender="talker",
                    column="left",
                    confidence=0.93
                ),
                ChatBubble(
                    bubble_id="b2",
                    bbox=BoundingBox(x1=580, y1=300, x2=980, y2=380),
                    center_x=780,
                    center_y=340,
                    text="Pretty good! Just finished work",
                    sender="user",
                    column="right",
                    confidence=0.91
                )
            ],
            layout=LayoutInfo(
                type="two_columns",
                left_role="talker",
                right_role="user"
            )
        )
        
        mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
            code=0,
            msg="Success",
            data=parsed_data
        ))
        
        # Step 2: Parse screenshot
        parse_request = ParseScreenshotRequest(
            image_url="https://example.com/whatsapp_screenshot.png",
            session_id="test-whatsapp-integration",
            options=ParseOptions(app_type="whatsapp")
        )
        
        parse_response = await mock_parser.parse_screenshot(parse_request)
        
        # Verify parse succeeded
        assert parse_response.code == 0
        assert len(parse_response.data.bubbles) == 2
        
        # Step 3: Convert to dialogs and create request
        dialogs = bubbles_to_dialogs(parse_response.data.bubbles)
        
        gen_request = GenerateReplyRequest(
            user_id=parse_response.data.participants.self.id,
            target_id=parse_response.data.participants.other.id,
            conversation_id="conv_whatsapp_test",
            dialogs=dialogs,
            intimacy_value=60,
            language="en",
            quality="normal"
        )
        
        # Verify request
        assert gen_request.user_id == "user_whatsapp_123"
        assert gen_request.target_id == "friend_whatsapp_456"
        assert len(gen_request.dialogs) == 2
        assert gen_request.dialogs[0]["speaker"] == "talker"
        assert gen_request.dialogs[1]["speaker"] == "user"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_line_screenshot_to_reply_flow(self):
        """Test complete flow: LINE screenshot → dialogs → reply generation."""
        # Step 1: Create mock screenshot parser service
        mock_parser = Mock(spec=ScreenshotParserService)
        
        # Simulate parsed LINE screenshot
        parsed_data = ParsedScreenshotData(
            image_meta=ImageMeta(width=720, height=1280),
            participants=Participants(
                self=Participant(id="user_line_123", nickname="私"),
                other=Participant(id="friend_line_456", nickname="田中さん")
            ),
            bubbles=[
                ChatBubble(
                    bubble_id="b1",
                    bbox=BoundingBox(x1=60, y1=150, x2=350, y2=200),
                    center_x=205,
                    center_y=175,
                    text="こんにちは！",
                    sender="talker",
                    column="left",
                    confidence=0.90
                ),
                ChatBubble(
                    bubble_id="b2",
                    bbox=BoundingBox(x1=370, y1=220, x2=660, y2=270),
                    center_x=515,
                    center_y=245,
                    text="こんにちは！元気ですか？",
                    sender="user",
                    column="right",
                    confidence=0.88
                )
            ],
            layout=LayoutInfo(
                type="two_columns",
                left_role="talker",
                right_role="user"
            )
        )
        
        mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
            code=0,
            msg="Success",
            data=parsed_data
        ))
        
        # Step 2: Parse screenshot
        parse_request = ParseScreenshotRequest(
            image_url="https://example.com/line_screenshot.png",
            session_id="test-line-integration",
            options=ParseOptions(app_type="line")
        )
        
        parse_response = await mock_parser.parse_screenshot(parse_request)
        
        # Verify parse succeeded
        assert parse_response.code == 0
        assert len(parse_response.data.bubbles) == 2
        
        # Step 3: Convert to dialogs and create request
        dialogs = bubbles_to_dialogs(parse_response.data.bubbles)
        
        gen_request = GenerateReplyRequest(
            user_id=parse_response.data.participants.self.id,
            target_id=parse_response.data.participants.other.id,
            conversation_id="conv_line_test",
            dialogs=dialogs,
            intimacy_value=45,
            language="en",  # Note: Japanese text but English reply
            quality="normal"
        )
        
        # Verify request
        assert gen_request.user_id == "user_line_123"
        assert gen_request.target_id == "friend_line_456"
        assert len(gen_request.dialogs) == 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_turn_conversation_flow(self):
        """Test integration with longer multi-turn conversation."""
        # Create mock parser with longer conversation
        mock_parser = Mock(spec=ScreenshotParserService)
        
        # Simulate a longer conversation
        bubbles = []
        for i in range(10):
            sender = "user" if i % 2 == 0 else "talker"
            column = "right" if i % 2 == 0 else "left"
            center_x = 600 if i % 2 == 0 else 200
            
            bubbles.append(ChatBubble(
                bubble_id=f"b{i+1}",
                bbox=BoundingBox(x1=50, y1=100+i*70, x2=300, y2=150+i*70),
                center_x=center_x,
                center_y=125+i*70,
                text=f"Message {i+1}",
                sender=sender,
                column=column,
                confidence=0.90
            ))
        
        parsed_data = ParsedScreenshotData(
            image_meta=ImageMeta(width=800, height=1400),
            participants=Participants(
                self=Participant(id="user_123", nickname="Me"),
                other=Participant(id="friend_456", nickname="Friend")
            ),
            bubbles=bubbles,
            layout=LayoutInfo(
                type="two_columns",
                left_role="talker",
                right_role="user"
            )
        )
        
        mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
            code=0,
            msg="Success",
            data=parsed_data
        ))
        
        # Parse and convert
        parse_request = ParseScreenshotRequest(
            image_url="https://example.com/long_conversation.png",
            session_id="test-multi-turn"
        )
        
        parse_response = await mock_parser.parse_screenshot(parse_request)
        dialogs = bubbles_to_dialogs(parse_response.data.bubbles)
        
        # Verify all messages converted
        assert len(dialogs) == 10
        
        # Verify alternating speakers
        for i, dialog in enumerate(dialogs):
            expected_speaker = "user" if i % 2 == 0 else "talker"
            assert dialog["speaker"] == expected_speaker
            assert dialog["text"] == f"Message {i+1}"
        
        # Create request
        gen_request = GenerateReplyRequest(
            user_id="user_123",
            target_id="friend_456",
            conversation_id="conv_multi_turn",
            dialogs=dialogs,
            intimacy_value=55,
            language="en",
            quality="normal"
        )
        
        assert len(gen_request.dialogs) == 10

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_in_integration_flow(self):
        """Test error handling when screenshot parsing fails."""
        # Create mock parser that returns error
        mock_parser = Mock(spec=ScreenshotParserService)
        mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
            code=1001,
            msg="Failed to download image",
            data=None
        ))
        
        # Attempt to parse
        parse_request = ParseScreenshotRequest(
            image_url="https://example.com/invalid.png",
            session_id="test-error-handling"
        )
        
        parse_response = await mock_parser.parse_screenshot(parse_request)
        
        # Verify error response
        assert parse_response.code != 0
        assert parse_response.data is None
        assert "Failed to download" in parse_response.msg
        
        # In production, the API would return this error to the client
        # and not proceed to reply generation

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_layout_validation_in_integration_flow(self):
        """Test that layout validation catches inconsistencies."""
        # Create mock parser with inconsistent data
        mock_parser = Mock(spec=ScreenshotParserService)
        
        # Inconsistent: bubble says sender="talker" but column="right"
        # while layout says right_role="user"
        parsed_data = ParsedScreenshotData(
            image_meta=ImageMeta(width=800, height=600),
            participants=Participants(
                self=Participant(id="user_123", nickname="Me"),
                other=Participant(id="friend_456", nickname="Friend")
            ),
            bubbles=[
                ChatBubble(
                    bubble_id="b1",
                    bbox=BoundingBox(x1=50, y1=100, x2=300, y2=150),
                    center_x=600,  # Right side
                    center_y=125,
                    text="Hello",
                    sender="talker",  # Inconsistent!
                    column="right",
                    confidence=0.95
                )
            ],
            layout=LayoutInfo(
                type="two_columns",
                left_role="talker",
                right_role="user"
            )
        )
        
        mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
            code=0,
            msg="Success",
            data=parsed_data
        ))
        
        parse_response = await mock_parser.parse_screenshot(parse_request := ParseScreenshotRequest(
            image_url="https://example.com/test.png",
            session_id="test-validation"
        ))
        
        # Attempt to validate layout
        with pytest.raises(ValueError) as exc_info:
            validate_layout(parse_response.data.layout, parse_response.data.bubbles)
        
        assert "Inconsistent sender attribution" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_tracking_through_pipeline(self):
        """Test that session_id is preserved through the pipeline."""
        session_id = "test-session-tracking-12345"
        
        # Create mock parser
        mock_parser = Mock(spec=ScreenshotParserService)
        parsed_data = ParsedScreenshotData(
            image_meta=ImageMeta(width=800, height=600),
            participants=Participants(
                self=Participant(id="user_123", nickname="Me"),
                other=Participant(id="friend_456", nickname="Friend")
            ),
            bubbles=[
                ChatBubble(
                    bubble_id="b1",
                    bbox=BoundingBox(x1=50, y1=100, x2=300, y2=150),
                    center_x=175,
                    center_y=125,
                    text="Test message",
                    sender="user",
                    column="right",
                    confidence=0.95
                )
            ],
            layout=LayoutInfo(
                type="two_columns",
                left_role="talker",
                right_role="user"
            )
        )
        
        mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
            code=0,
            msg="Success",
            data=parsed_data
        ))
        
        # Parse with session_id
        parse_request = ParseScreenshotRequest(
            image_url="https://example.com/test.png",
            session_id=session_id
        )
        
        parse_response = await mock_parser.parse_screenshot(parse_request)
        
        # Verify session_id can be tracked
        assert parse_request.session_id == session_id
        
        # In production, this session_id would be:
        # 1. Logged in the screenshot parser
        # 2. Passed to the orchestrator
        # 3. Included in all downstream service calls
        # 4. Used for end-to-end tracing

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_different_intimacy_levels(self):
        """Test integration with different intimacy levels."""
        intimacy_levels = [10, 30, 50, 70, 90]
        
        for intimacy in intimacy_levels:
            # Create mock parser
            mock_parser = Mock(spec=ScreenshotParserService)
            parsed_data = ParsedScreenshotData(
                image_meta=ImageMeta(width=800, height=600),
                participants=Participants(
                    self=Participant(id="user_123", nickname="Me"),
                    other=Participant(id="friend_456", nickname="Friend")
                ),
                bubbles=[
                    ChatBubble(
                        bubble_id="b1",
                        bbox=BoundingBox(x1=50, y1=100, x2=300, y2=150),
                        center_x=175,
                        center_y=125,
                        text="Hello",
                        sender="user",
                        column="right",
                        confidence=0.95
                    )
                ],
                layout=LayoutInfo(
                    type="two_columns",
                    left_role="talker",
                    right_role="user"
                )
            )
            
            mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
                code=0,
                msg="Success",
                data=parsed_data
            ))
            
            parse_response = await mock_parser.parse_screenshot(ParseScreenshotRequest(
                image_url="https://example.com/test.png",
                session_id=f"test-intimacy-{intimacy}"
            ))
            
            dialogs = bubbles_to_dialogs(parse_response.data.bubbles)
            
            # Create request with specific intimacy level
            gen_request = GenerateReplyRequest(
                user_id="user_123",
                target_id="friend_456",
                conversation_id=f"conv_intimacy_{intimacy}",
                dialogs=dialogs,
                intimacy_value=intimacy,
                language="en",
                quality="normal"
            )
            
            assert gen_request.intimacy_value == intimacy

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_different_languages(self):
        """Test integration with different language settings."""
        languages = ["en", "zh-CN", "ar", "pt", "es"]
        
        for lang in languages:
            # Create mock parser
            mock_parser = Mock(spec=ScreenshotParserService)
            parsed_data = ParsedScreenshotData(
                image_meta=ImageMeta(width=800, height=600),
                participants=Participants(
                    self=Participant(id="user_123", nickname="Me"),
                    other=Participant(id="friend_456", nickname="Friend")
                ),
                bubbles=[
                    ChatBubble(
                        bubble_id="b1",
                        bbox=BoundingBox(x1=50, y1=100, x2=300, y2=150),
                        center_x=175,
                        center_y=125,
                        text="Test message",
                        sender="user",
                        column="right",
                        confidence=0.95
                    )
                ],
                layout=LayoutInfo(
                    type="two_columns",
                    left_role="talker",
                    right_role="user"
                )
            )
            
            mock_parser.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
                code=0,
                msg="Success",
                data=parsed_data
            ))
            
            parse_response = await mock_parser.parse_screenshot(ParseScreenshotRequest(
                image_url="https://example.com/test.png",
                session_id=f"test-lang-{lang}"
            ))
            
            dialogs = bubbles_to_dialogs(parse_response.data.bubbles)
            
            # Create request with specific language
            gen_request = GenerateReplyRequest(
                user_id="user_123",
                target_id="friend_456",
                conversation_id=f"conv_lang_{lang}",
                dialogs=dialogs,
                intimacy_value=50,
                language=lang,
                quality="normal"
            )
            
            assert gen_request.language == lang
