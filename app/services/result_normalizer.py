"""Result normalizer component for validating and standardizing LLM output.

This module provides the ResultNormalizer class that validates LLM responses,
applies fallback logic for missing/invalid data, and ensures output consistency.
"""

from app.models.screenshot import (
    ParsedScreenshotData,
    ParseOptions,
    ImageMeta,
    Participants,
    Participant,
    LayoutInfo,
    ChatBubble,
    BoundingBox,
)


class ResultNormalizer:
    """Component for validating and normalizing LLM output.
    
    This component ensures that LLM responses are complete, valid, and
    consistently formatted by applying validation rules, calculating missing
    values, and applying fallback strategies.
    """

    def normalize(
        self,
        raw_json: dict,
        image_meta: ImageMeta,
        options: ParseOptions,
    ) -> ParsedScreenshotData:
        """Validate and normalize LLM output.
        
        Args:
            raw_json: Raw JSON response from LLM
            image_meta: Image metadata for validation
            options: Parsing options used
            
        Returns:
            ParsedScreenshotData with validated and normalized data
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        
        if self._is_compact_output(raw_json):
            raw_json = self._adapt_compact_output(raw_json)

        # Step 1: Validate required fields
        self._validate_required_fields(raw_json)
        
        # Step 2: Normalize bubbles
        normalized_bubbles = self._normalize_bubbles(
            raw_json["bubbles"],
            image_meta.width,
            image_meta.height
        )
        
        # Step 3: Sort bubbles by position
        sorted_bubbles = self._sort_bubbles_by_position(normalized_bubbles)
        
        # Step 4: Ensure unique IDs
        self._ensure_unique_ids(sorted_bubbles)
        
        # Step 5: Build participants
        participants_data = raw_json["participants"]
        participants = Participants(
            self=Participant(
                id=participants_data["self"]["id"],
                nickname=participants_data["self"]["nickname"]
            ),
            other=Participant(
                id=participants_data["other"]["id"],
                nickname=participants_data["other"]["nickname"]
            )
        )
        
        # Step 6: Build layout
        layout_data = raw_json["layout"]
        layout = LayoutInfo(
            type=layout_data.get("type", "two_columns"),
            left_role=layout_data["left_role"],
            right_role=layout_data["right_role"]
        )
        
        # Step 7: Return complete structure
        return ParsedScreenshotData(
            image_meta=image_meta,
            participants=participants,
            bubbles=sorted_bubbles,
            layout=layout
        )

    def _is_compact_output(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        if "participants" in data or "layout" in data:
            return False
        return "bubbles" in data

    def _adapt_compact_output(self, data: dict) -> dict:
        nicknames = data.get("nickname")
        self_nickname = "user"
        other_nickname = "talker"
        if isinstance(nicknames, list):
            cleaned = [str(n).strip() for n in nicknames if str(n).strip()]
            if len(cleaned) >= 2:
                self_nickname, other_nickname = cleaned[0], cleaned[1]
            elif len(cleaned) == 1:
                other_nickname = cleaned[0]

        adapted_bubbles: list[dict] = []
        for b in data.get("bubbles", []) or []:
            if not isinstance(b, dict):
                continue

            bbox = b.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4:
                bbox_dict = {
                    "x1": bbox[0],
                    "y1": bbox[1],
                    "x2": bbox[2],
                    "y2": bbox[3],
                }
            elif isinstance(bbox, dict):
                bbox_dict = bbox
            else:
                continue

            sender = b.get("sender")
            if isinstance(sender, str):
                s = sender.strip().casefold()
                if s == "u":
                    sender_value = "user"
                elif s == "t":
                    sender_value = "talker"
                elif s in {"user", "talker"}:
                    sender_value = s
                else:
                    sender_value = None
            else:
                sender_value = None

            bubble_dict: dict = {
                "bbox": bbox_dict,
                "text": b.get("text", ""),
            }
            if sender_value:
                bubble_dict["sender"] = sender_value
            adapted_bubbles.append(bubble_dict)

        return {
            "participants": {
                "self": {"id": "user", "nickname": self_nickname},
                "other": {"id": "talker", "nickname": other_nickname},
            },
            "bubbles": adapted_bubbles,
            "layout": {
                "type": "two_columns",
                "left_role": "talker",
                "right_role": "user",
            },
        }

    def _validate_required_fields(self, data: dict) -> None:
        """Check all required fields are present.
        
        Args:
            data: Raw JSON data to validate
            
        Raises:
            ValueError: If required fields are missing
        """
        # Check top-level required fields
        required_top_level = ["participants", "bubbles", "layout"]
        missing = [field for field in required_top_level if field not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        
        # Validate participants structure
        participants = data.get("participants", {})
        if "self" not in participants or "other" not in participants:
            raise ValueError("participants must contain 'self' and 'other'")
        
        for role in ["self", "other"]:
            participant = participants[role]
            if not isinstance(participant, dict):
                raise ValueError(f"participants.{role} must be a dictionary")
            if "id" not in participant or "nickname" not in participant:
                raise ValueError(f"participants.{role} must contain 'id' and 'nickname'")
        
        # Validate bubbles is a list
        if not isinstance(data["bubbles"], list):
            raise ValueError("bubbles must be a list")
        
        # Validate each bubble has required fields
        for i, bubble in enumerate(data["bubbles"]):
            if not isinstance(bubble, dict):
                raise ValueError(f"bubble[{i}] must be a dictionary")
            
            # Required fields for each bubble
            required_bubble_fields = ["bbox", "text"]
            missing_bubble = [f for f in required_bubble_fields if f not in bubble]
            if missing_bubble:
                raise ValueError(
                    f"bubble[{i}] missing required fields: {', '.join(missing_bubble)}"
                )
            
            # Validate bbox structure
            bbox = bubble.get("bbox", {})
            if not isinstance(bbox, dict):
                raise ValueError(f"bubble[{i}].bbox must be a dictionary")
            
            required_bbox = ["x1", "y1", "x2", "y2"]
            missing_bbox = [f for f in required_bbox if f not in bbox]
            if missing_bbox:
                raise ValueError(
                    f"bubble[{i}].bbox missing coordinates: {', '.join(missing_bbox)}"
                )
            
            # Validate bbox coordinates are numbers
            for coord in required_bbox:
                if not isinstance(bbox[coord], (int, float)):
                    raise ValueError(
                        f"bubble[{i}].bbox.{coord} must be a number, got {type(bbox[coord])}"
                    )
            
            # Validate sender if present
            if "sender" in bubble:
                if bubble["sender"] not in ["user", "talker"]:
                    raise ValueError(
                        f"bubble[{i}].sender must be 'user' or 'talker', got '{bubble['sender']}'"
                    )
            
            # Validate column if present
            if "column" in bubble:
                if bubble["column"] not in ["left", "right"]:
                    raise ValueError(
                        f"bubble[{i}].column must be 'left' or 'right', got '{bubble['column']}'"
                    )
        
        # Validate layout structure
        layout = data.get("layout", {})
        if not isinstance(layout, dict):
            raise ValueError("layout must be a dictionary")
        
        if "left_role" not in layout or "right_role" not in layout:
            raise ValueError("layout must contain 'left_role' and 'right_role'")
        
        if layout["left_role"] not in ["user", "talker"]:
            raise ValueError(
                f"layout.left_role must be 'user' or 'talker', got '{layout['left_role']}'"
            )
        
        if layout["right_role"] not in ["user", "talker"]:
            raise ValueError(
                f"layout.right_role must be 'user' or 'talker', got '{layout['right_role']}'"
            )

    def _normalize_bubbles(
        self,
        bubbles: list[dict],
        image_width: int,
        image_height: int
    ) -> list[ChatBubble]:
        """Normalize bubble data with validation and defaults.
        
        Args:
            bubbles: List of raw bubble dictionaries
            image_width: Image width for position-based inference
            
        Returns:
            List of validated ChatBubble objects
        """
        normalized = []
        
        for i, bubble_dict in enumerate(bubbles):
            # Create BoundingBox
            bbox_dict = bubble_dict["bbox"]
            bbox = BoundingBox(
                x1=float(bbox_dict["x1"]) / image_width,
                y1=float(bbox_dict["y1"]) / image_height,
                x2=float(bbox_dict["x2"]) / image_width,
                y2=float(bbox_dict["y2"]) / image_height
            )
            
            # Calculate center if not provided
            if "center_x" in bubble_dict and "center_y" in bubble_dict:
                center_x = int(bubble_dict["center_x"])
                center_y = int(bubble_dict["center_y"])
            else:
                center_x, center_y = self._calculate_center(bbox)
            
            # Get or infer sender
            if "sender" in bubble_dict and bubble_dict["sender"] in ["user", "talker"]:
                sender = bubble_dict["sender"]
            else:
                sender = self._infer_sender_from_position(center_x, image_width)
            
            # Get or infer column
            if "column" in bubble_dict and bubble_dict["column"] in ["left", "right"]:
                column = bubble_dict["column"]
            else:
                column = self._infer_column_from_position(center_x, image_width)
            
            # Get or assign default confidence
            confidence = bubble_dict.get("confidence", 0.5)
            
            # Get or generate bubble_id
            bubble_id = bubble_dict.get("bubble_id", f"b{i}")
            
            # Create ChatBubble
            chat_bubble = ChatBubble(
                bubble_id=bubble_id,
                bbox=bbox,
                center_x=center_x,
                center_y=center_y,
                text=bubble_dict["text"],
                sender=sender,
                column=column,
                confidence=float(confidence)
            )
            
            normalized.append(chat_bubble)
        
        return normalized

    def _calculate_center(self, bbox: BoundingBox) -> tuple[int, int]:
        """Calculate center point from bounding box.
        
        Args:
            bbox: Bounding box coordinates
            
        Returns:
            Tuple of (center_x, center_y)
        """
        center_x = (bbox.x1 + bbox.x2) // 2
        center_y = (bbox.y1 + bbox.y2) // 2
        return center_x, center_y

    def _infer_sender_from_position(self, center_x: int, width: int) -> str:
        """Infer sender based on horizontal position.
        
        Args:
            center_x: Horizontal center coordinate
            width: Image width
            
        Returns:
            Sender value ("user" or "talker")
        """
        # Left side (< 50%) is typically talker, right side is user
        if center_x < width / 2:
            return "talker"
        else:
            return "user"
    
    def _infer_column_from_position(self, center_x: int, width: int) -> str:
        """Infer column based on horizontal position.
        
        Args:
            center_x: Horizontal center coordinate
            width: Image width
            
        Returns:
            Column value ("left" or "right")
        """
        # Left side (< 50%) is left column, right side is right column
        if center_x < width / 2:
            return "left"
        else:
            return "right"

    def _sort_bubbles_by_position(
        self,
        bubbles: list[ChatBubble]
    ) -> list[ChatBubble]:
        """Sort bubbles by vertical position (y1 ascending).
        
        Args:
            bubbles: List of chat bubbles
            
        Returns:
            Sorted list of chat bubbles
        """
        # Sort by y1 coordinate (top to bottom)
        # Using stable sort to maintain order for equal y1 values
        return sorted(bubbles, key=lambda b: b.bbox.y1)

    def _ensure_unique_ids(self, bubbles: list[ChatBubble]) -> None:
        """Ensure all bubble_ids are unique.
        
        Args:
            bubbles: List of chat bubbles to validate
            
        Modifies bubbles in-place to ensure unique IDs.
        """
        seen_ids = set()
        for i, bubble in enumerate(bubbles):
            original_id = bubble.bubble_id
            
            # If ID is already seen, generate a new unique one
            if original_id in seen_ids:
                # Try appending a counter
                counter = 1
                new_id = f"{original_id}_{counter}"
                while new_id in seen_ids:
                    counter += 1
                    new_id = f"{original_id}_{counter}"
                bubble.bubble_id = new_id
            
            seen_ids.add(bubble.bubble_id)
