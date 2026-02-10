"""
Adapter for converting merge_step prompt output to existing data structures.

This module provides adapters to convert the unified merge_step JSON output
into the separate data structures used by the existing services:
- ParsedScreenshotData (for screenshot_parser)
- ContextResult (for context_builder)
- SceneAnalysisResult (for scene_analyzer)
"""

import json
import logging
from typing import Dict, Any

from app.models.screenshot import (
    ParsedScreenshotData,
    ImageMeta,
    Participants,
    Participant,
    ChatBubble,
    BoundingBox,
    LayoutInfo,
)
from app.models.schemas import (
    ContextResult,
    SceneAnalysisResult,
    Message,
)

logger = logging.getLogger(__name__)


class MergeStepAdapter:
    """Adapter for converting merge_step output to existing data structures."""
    
    @staticmethod
    def to_parsed_screenshot_data(
        merge_output: Dict[str, Any],
        image_width: int,
        image_height: int,
    ) -> ParsedScreenshotData:
        """
        Convert merge_step screenshot_parse output to ParsedScreenshotData.
        
        Automatically fills in missing fields:
        - center_x, center_y: Calculated from bbox if missing
        - bubble_id: Generated if missing
        - confidence: Default 0.95 if missing
        - column: Inferred from center_x if missing
        
        Args:
            merge_output: The full merge_step JSON output
            image_width: Original image width
            image_height: Original image height
            
        Returns:
            ParsedScreenshotData compatible with screenshot_parser
        """
        screenshot_data = merge_output.get("screenshot_parse", {})
        
        # Extract participants with defaults
        participants_data = screenshot_data.get("participants", {})
        self_data = participants_data.get("self", {})
        other_data = participants_data.get("other", {})
        
        participants = Participants(
            self=Participant(
                id=self_data.get("id", "user"),
                nickname=self_data.get("nickname", "User")
            ),
            other=Participant(
                id=other_data.get("id", "talker"),
                nickname=other_data.get("nickname", "Talker")
            )
        )
        
        # Extract and process bubbles
        bubbles_data = screenshot_data.get("bubbles", [])
        
        # Check if v3.0 image_metadata is available
        image_metadata = merge_output.get("image_metadata", {})
        llm_reported_width = image_metadata.get("original_width", 0)
        llm_reported_height = image_metadata.get("original_height", 0)
        
        # Validate LLM-reported dimensions against actual dimensions
        if llm_reported_width > 0 and llm_reported_height > 0:
            if abs(llm_reported_width - image_width) > 5 or abs(llm_reported_height - image_height) > 5:
                logger.warning(
                    f"Image dimension mismatch: LLM reported {llm_reported_width}x{llm_reported_height}, "
                    f"actual {image_width}x{image_height}"
                )
            else:
                logger.debug(f"Image dimensions confirmed by LLM: {llm_reported_width}x{llm_reported_height}")
        
        # First pass: detect coordinate scale by checking all bubbles
        coordinate_scale = "pixels"  # default assumption
        max_x = 0
        max_y = 0
        all_coords_small = True
        
        for bubble_data in bubbles_data:
            bbox_data = bubble_data.get("bbox", {})
            x1 = float(bbox_data.get("x1", 0))
            y1 = float(bbox_data.get("y1", 0))
            x2 = float(bbox_data.get("x2", 0))
            y2 = float(bbox_data.get("y2", 0))
            
            max_x = max(max_x, x1, x2)
            max_y = max(max_y, y1, y2)
            
            if x1 > 1.0 or y1 > 1.0 or x2 > 1.0 or y2 > 1.0:
                all_coords_small = False
        
        # Determine scale
        if all_coords_small and max_x <= 1.0 and max_y <= 1.0:
            coordinate_scale = "normalized_0_1"
            logger.warning(
                f"Detected normalized coordinates (0-1 range) despite v3.0 prompt requiring pixels. "
                f"This may indicate LLM is not following the prompt correctly."
            )
        elif max_x > image_width or max_y > image_height:
            coordinate_scale = "normalized_0_1000"
            logger.warning(
                f"Detected coordinates exceeding image bounds "
                f"(max_x={max_x} > {image_width} or max_y={max_y} > {image_height}). "
                f"Assuming 0-1000 scale. This should not happen with v3.0 prompt."
            )
        else:
            logger.debug(f"Coordinates appear to be in pixels (as expected with v3.0 prompt)")
        
        bubbles = []
        
        # Second pass: process bubbles with detected scale
        for idx, bubble_data in enumerate(bubbles_data):
            bbox_data = bubble_data.get("bbox", {})
            
            # Extract bbox coordinates
            x1 = float(bbox_data.get("x1", 0))
            y1 = float(bbox_data.get("y1", 0))
            x2 = float(bbox_data.get("x2", 0))
            y2 = float(bbox_data.get("y2", 0))
            
            # Apply scale conversion
            if coordinate_scale == "normalized_0_1":
                x1 = x1 * image_width
                y1 = y1 * image_height
                x2 = x2 * image_width
                y2 = y2 * image_height
            elif coordinate_scale == "normalized_0_1000":
                x1 = (x1 / 1000.0) * image_width
                y1 = (y1 / 1000.0) * image_height
                x2 = (x2 / 1000.0) * image_width
                y2 = (y2 / 1000.0) * image_height
            
            # Validate final coordinates (v3.0 requirements)
            if x1 >= x2 or y1 >= y2:
                logger.error(
                    f"Bubble {idx}: Invalid bbox coordinates (violates x2>x1, y2>y1): "
                    f"x1={x1:.1f} >= x2={x2:.1f} or y1={y1:.1f} >= y2={y2:.1f}"
                )
            if x2 > image_width or y2 > image_height:
                logger.warning(
                    f"Bubble {idx}: Bbox exceeds image bounds after normalization: "
                    f"bbox=[{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}], image={image_width}x{image_height}"
                )
            
            # Convert to integers as required by v3.0 prompt
            x1 = int(round(x1))
            y1 = int(round(y1))
            x2 = int(round(x2))
            y2 = int(round(y2))
            
            # Calculate center_x and center_y if missing
            center_x = bubble_data.get("center_x")
            center_y = bubble_data.get("center_y")
            
            if center_x is None:
                center_x = (x1 + x2) / 2
                logger.debug(f"Calculated center_x={center_x} for bubble {idx}")
            else:
                center_x = float(center_x)
            
            if center_y is None:
                center_y = (y1 + y2) / 2
                logger.debug(f"Calculated center_y={center_y} for bubble {idx}")
            else:
                center_y = float(center_y)
            
            # Generate bubble_id if missing
            bubble_id = bubble_data.get("bubble_id")
            if not bubble_id:
                bubble_id = str(idx + 1)
                logger.debug(f"Generated bubble_id={bubble_id} for bubble {idx}")
            
            # Get sender
            sender = bubble_data.get("sender", "user")
            
            # Infer column if missing
            column = bubble_data.get("column")
            if not column:
                # Infer from center_x position (left half = left, right half = right)
                if image_width > 0:
                    column = "left" if center_x < image_width / 2 else "right"
                else:
                    # Fallback: infer from sender
                    column = "left" if sender == "user" else "right"
                logger.debug(f"Inferred column={column} for bubble {idx}")
            
            # Get confidence with default
            confidence = bubble_data.get("confidence")
            if confidence is None:
                confidence = 0.95
                logger.debug(f"Using default confidence=0.95 for bubble {idx}")
            else:
                confidence = float(confidence)
            
            bubbles.append(ChatBubble(
                bubble_id=bubble_id,
                bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                center_x=center_x,
                center_y=center_y,
                text=bubble_data.get("text", ""),
                sender=sender,
                column=column,
                confidence=confidence,
            ))
        
        # Extract layout with defaults
        layout_data = screenshot_data.get("layout", {})
        
        # Infer layout roles if missing
        left_role = layout_data.get("left_role")
        right_role = layout_data.get("right_role")
        
        if not left_role or not right_role:
            # Try to infer from bubbles
            if bubbles:
                # Find most common sender in left column
                left_senders = [b.sender for b in bubbles if b.column == "left"]
                right_senders = [b.sender for b in bubbles if b.column == "right"]
                
                if left_senders and not left_role:
                    # Most common sender in left column
                    left_role = max(set(left_senders), key=left_senders.count)
                    logger.debug(f"Inferred left_role={left_role}")
                
                if right_senders and not right_role:
                    # Most common sender in right column
                    right_role = max(set(right_senders), key=right_senders.count)
                    logger.debug(f"Inferred right_role={right_role}")
        
        # Final defaults
        if not left_role:
            left_role = "user"
        if not right_role:
            right_role = "talker"
        
        layout = LayoutInfo(
            type=layout_data.get("type", "two_columns"),
            left_role=left_role,
            right_role=right_role,
        )
        
        # Create image meta
        image_meta = ImageMeta(
            width=image_width,
            height=image_height,
        )
        
        return ParsedScreenshotData(
            image_meta=image_meta,
            participants=participants,
            bubbles=bubbles,
            layout=layout,
        )
    
    @staticmethod
    def to_context_result(
        merge_output: Dict[str, Any],
        dialogs: list[Dict[str, str]],
    ) -> ContextResult:
        """
        Convert merge_step conversation_analysis output to ContextResult.
        
        Automatically fills in missing fields:
        - conversation_summary: Default empty string if missing
        - emotion_state: Default "neutral" if missing
        - current_intimacy_level: Default 50 if missing
        - risk_flags: Default empty list if missing
        
        Args:
            merge_output: The full merge_step JSON output
            dialogs: List of dialog items from the conversation
            
        Returns:
            ContextResult compatible with context_builder
        """
        conversation_data = merge_output.get("conversation_analysis", {})
        
        # Extract with defaults
        conversation_summary = conversation_data.get("conversation_summary", "")
        if not conversation_summary:
            logger.debug("conversation_summary missing, using empty string")
        
        emotion_state = conversation_data.get("emotion_state", "neutral")
        if emotion_state not in ["positive", "neutral", "negative"]:
            logger.warning(f"Invalid emotion_state '{emotion_state}', defaulting to 'neutral'")
            emotion_state = "neutral"
        
        current_intimacy_level = conversation_data.get("current_intimacy_level")
        if current_intimacy_level is None:
            current_intimacy_level = 50
            logger.debug("current_intimacy_level missing, using default 50")
        else:
            current_intimacy_level = int(current_intimacy_level)
            # Clamp to valid range
            if current_intimacy_level < 0:
                logger.warning(f"current_intimacy_level {current_intimacy_level} < 0, clamping to 0")
                current_intimacy_level = 0
            elif current_intimacy_level > 100:
                logger.warning(f"current_intimacy_level {current_intimacy_level} > 100, clamping to 100")
                current_intimacy_level = 100
        
        risk_flags = conversation_data.get("risk_flags", [])
        if not isinstance(risk_flags, list):
            logger.warning(f"risk_flags is not a list, converting to empty list")
            risk_flags = []
        
        # Convert dialogs to Message objects
        messages = []
        for i, dialog in enumerate(dialogs):
            speaker = dialog.get("speaker", "user")
            text = dialog.get("text", "")
            timestamp = dialog.get("timestamp")
            
            messages.append(Message(
                id=str(i),
                speaker=speaker,
                content=text,
                timestamp=timestamp,
            ))
        
        return ContextResult(
            conversation_summary=conversation_summary,
            emotion_state=emotion_state,
            current_intimacy_level=current_intimacy_level,
            risk_flags=risk_flags,
            conversation=messages,
            history_conversation="",
        )
    
    @staticmethod
    def to_scene_analysis_result(
        merge_output: Dict[str, Any],
    ) -> SceneAnalysisResult:
        """
        Convert merge_step scenario_decision output to SceneAnalysisResult.
        
        Automatically fills in missing fields:
        - relationship_state: Default "维持" if missing
        - scenario: Defaults to recommended_scenario or "SAFE"
        - intimacy_level: Default 50 if missing
        - risk_flags: Default empty list if missing
        - current_scenario: Default empty string if missing
        - recommended_scenario: Default "SAFE" if missing
        - recommended_strategies: Always empty (filled by StrategySelector)
        
        Note: recommended_strategies will be empty and should be filled by
        StrategySelector based on recommended_scenario.
        
        Args:
            merge_output: The full merge_step JSON output
            
        Returns:
            SceneAnalysisResult compatible with scene_analyzer
        """
        scenario_data = merge_output.get("scenario_decision", {})
        
        # Extract relationship_state with validation
        relationship_state = scenario_data.get("relationship_state", "维持")
        valid_states = ["破冰", "推进", "冷却", "维持", "ignition", "propulsion", "ventilation", "equilibrium"]
        if relationship_state not in valid_states:
            logger.warning(f"Invalid relationship_state '{relationship_state}', defaulting to '维持'")
            relationship_state = "维持"
        
        # Extract recommended_scenario with validation
        recommended_scenario = scenario_data.get("recommended_scenario", "SAFE")
        valid_scenarios = ["SAFE", "BALANCED", "RISKY", "RECOVERY", "NEGATIVE"]
        if recommended_scenario not in valid_scenarios:
            logger.warning(f"Invalid recommended_scenario '{recommended_scenario}', defaulting to 'SAFE'")
            recommended_scenario = "SAFE"
        
        # scenario defaults to recommended_scenario
        scenario = scenario_data.get("scenario", recommended_scenario)
        if scenario not in valid_scenarios:
            logger.warning(f"Invalid scenario '{scenario}', using recommended_scenario '{recommended_scenario}'")
            scenario = recommended_scenario
        
        # Extract intimacy_level with validation
        intimacy_level = scenario_data.get("intimacy_level")
        if intimacy_level is None:
            intimacy_level = 50
            logger.debug("intimacy_level missing, using default 50")
        else:
            intimacy_level = int(intimacy_level)
            # Clamp to valid range
            if intimacy_level < 0:
                logger.warning(f"intimacy_level {intimacy_level} < 0, clamping to 0")
                intimacy_level = 0
            elif intimacy_level > 100:
                logger.warning(f"intimacy_level {intimacy_level} > 100, clamping to 100")
                intimacy_level = 100
        
        # Extract risk_flags
        risk_flags = scenario_data.get("risk_flags", [])
        if not isinstance(risk_flags, list):
            logger.warning(f"risk_flags is not a list, converting to empty list")
            risk_flags = []
        
        # Extract current_scenario
        current_scenario = scenario_data.get("current_scenario", "")
        
        return SceneAnalysisResult(
            relationship_state=relationship_state,
            scenario=scenario,
            intimacy_level=intimacy_level,
            risk_flags=risk_flags,
            current_scenario=current_scenario,
            recommended_scenario=recommended_scenario,
            recommended_strategies=[],  # Will be filled by StrategySelector
        )
    
    @staticmethod
    def validate_merge_output(merge_output: Dict[str, Any]) -> bool:
        """
        Validate that merge_step output has all required fields.
        
        Supports both v2.0 and v3.0 prompt formats:
        - v2.0: No image_metadata field
        - v3.0: Includes image_metadata with original_width/height
        
        Args:
            merge_output: The merge_step JSON output
            
        Returns:
            True if valid, False otherwise
        """
        try:
            logger.info(f"Starting validation of merge_output with keys: {list(merge_output.keys())}")
            
            # Check for v3.0 image_metadata (optional for backward compatibility)
            if "image_metadata" in merge_output:
                metadata = merge_output["image_metadata"]
                logger.info(f"Detected v3.0 format with image_metadata: {metadata}")
                
                # Validate image_metadata structure
                if "original_width" in metadata and "original_height" in metadata:
                    width = metadata.get("original_width", 0)
                    height = metadata.get("original_height", 0)
                    if width > 0 and height > 0:
                        logger.info(f"Image dimensions from LLM: {width}x{height}")
                    else:
                        logger.warning(f"Invalid image dimensions in metadata: {width}x{height}")
            else:
                logger.info("No image_metadata found, assuming v2.0 format")
            
            # Check top-level keys
            required_keys = ["screenshot_parse", "conversation_analysis", "scenario_decision"]
            for key in required_keys:
                if key not in merge_output:
                    logger.error(f"Missing required key: {key}")
                    logger.error(f"Actual keys: {list(merge_output.keys())}")
                    logger.error(f"Full output: {json.dumps(merge_output, indent=2)[:1000]}")
                    return False
            
            logger.info("Top-level keys validated successfully")
            
            # Check screenshot_parse structure
            screenshot = merge_output["screenshot_parse"]
            if "bubbles" not in screenshot:
                logger.error("Missing 'bubbles' in screenshot_parse")
                logger.error(f"screenshot_parse keys: {list(screenshot.keys())}")
                return False
            
            logger.info(f"screenshot_parse validated: {len(screenshot.get('bubbles', []))} bubbles")
            
            # Check conversation_analysis structure
            conversation = merge_output["conversation_analysis"]
            required_conv_keys = ["conversation_summary", "emotion_state", "current_intimacy_level"]
            for key in required_conv_keys:
                if key not in conversation:
                    logger.error(f"Missing '{key}' in conversation_analysis")
                    logger.error(f"conversation_analysis keys: {list(conversation.keys())}")
                    return False
            
            logger.info("conversation_analysis validated successfully")
            
            # Check scenario_decision structure
            scenario = merge_output["scenario_decision"]
            logger.info(f"scenario_decision keys: {list(scenario.keys())}")
            required_scenario_keys = ["relationship_state", "recommended_scenario"]
            for key in required_scenario_keys:
                if key not in scenario:
                    logger.error(f"Missing '{key}' in scenario_decision")
                    logger.error(f"scenario_decision keys: {list(scenario.keys())}")
                    logger.error(f"scenario_decision content: {json.dumps(scenario, indent=2)}")
                    return False
            
            logger.info("scenario_decision validated successfully")
            logger.info("✓ All validation checks passed!")
            return True
            
        except Exception as e:
            logger.error(f"Error validating merge_output: {e}", exc_info=True)
            logger.error(f"merge_output type: {type(merge_output)}")
            if isinstance(merge_output, dict):
                logger.error(f"merge_output keys: {list(merge_output.keys())}")
            return False


def convert_merge_step_output(
    merge_output: Dict[str, Any],
    image_width: int,
    image_height: int,
    dialogs: list[Dict[str, str]],
) -> tuple[ParsedScreenshotData, ContextResult, SceneAnalysisResult]:
    """
    Convenience function to convert merge_step output to all three data structures.
    
    Args:
        merge_output: The full merge_step JSON output
        image_width: Original image width
        image_height: Original image height
        dialogs: List of dialog items from the conversation
        
    Returns:
        Tuple of (ParsedScreenshotData, ContextResult, SceneAnalysisResult)
        
    Raises:
        ValueError: If merge_output is invalid
    """
    adapter = MergeStepAdapter()
    
    # Validate first
    if not adapter.validate_merge_output(merge_output):
        raise ValueError("Invalid merge_step output structure")
    
    # Convert to all three formats
    screenshot_data = adapter.to_parsed_screenshot_data(merge_output, image_width, image_height)
    context_result = adapter.to_context_result(merge_output, dialogs)
    scene_result = adapter.to_scene_analysis_result(merge_output)
    
    return screenshot_data, context_result, scene_result
