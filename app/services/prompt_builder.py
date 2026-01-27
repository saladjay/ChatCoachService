"""Prompt builder component for constructing multimodal LLM prompts.

This module provides the PromptBuilder class that constructs system and user
prompts for the multimodal LLM, including task definition, parsing rules,
and JSON schema templates.
"""

import json
from pathlib import Path

from app.models.screenshot import ParseOptions


class PromptBuilder:
    """Component for building prompts for multimodal LLM screenshot parsing.
    
    This component constructs both system prompts (defining the task) and
    user prompts (providing specific instructions and schema) based on
    parsing options.
    """

    def __init__(self, prompt_dir: Path | None = None):
        """Initialize the PromptBuilder.
        
        Args:
            prompt_dir: Directory containing prompt templates. 
                       Defaults to prompts/active relative to project root.
        """
        if prompt_dir is None:
            # Default to prompts/active directory
            self.prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "active"
        else:
            self.prompt_dir = prompt_dir

    def build_prompts(
        self,
        options: ParseOptions,
    ) -> tuple[str, str]:
        """Build system and user prompts for multimodal LLM.
        
        Args:
            options: Parsing options for customizing prompts
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(options)
        return system_prompt, user_prompt

    def _build_system_prompt(self) -> str:
        """Build fixed system prompt defining the parsing task.
        
        Loads the system prompt from prompts/active/screenshot_parse_system.txt.
        
        Returns:
            System prompt string
        """
        system_prompt_path = self.prompt_dir / "screenshot_parse_system.txt"
        
        try:
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"System prompt template not found at {system_prompt_path}"
            )

    def _build_user_prompt(self, options: ParseOptions) -> str:
        """Build dynamic user prompt with options and schema.
        
        Args:
            options: Parsing options for customization
            
        Returns:
            User prompt string
        """
        # Base prompt with parsing rules
        prompt_parts = ["Parse this chat screenshot."]
        
        # Add basic parsing rules
        rules = [
            "- Left bubbles typically belong to talker",
            "- Right bubbles typically belong to user",
        ]
        
        # Add option-based customizations
        if options.force_two_columns:
            rules.append("- Assume a two-column layout (left and right)")
            rules.append("- All bubbles should be assigned to either left or right column")
        
        # Add app-specific hints
        if options.app_type and options.app_type != "unknown":
            app_hints = {
                "wechat": "- This is a WeChat screenshot with typical WeChat UI patterns",
                "line": "- This is a LINE screenshot with typical LINE UI patterns",
                "whatsapp": "- This is a WhatsApp screenshot with typical WhatsApp UI patterns",
            }
            if options.app_type in app_hints:
                rules.append(app_hints[options.app_type])
        
        # Add nickname extraction rule if needed
        if options.need_nickname:
            rules.append("- Extract nicknames from header/contact name if present")
        
        prompt_parts.append("\nRules:")
        prompt_parts.extend(rules)
        
        # Add JSON schema
        schema = self._get_json_schema()
        prompt_parts.append(f"\nReturn this exact JSON structure:\n{schema}")
        
        return "\n".join(prompt_parts)

    def _get_json_schema(self) -> str:
        """Get JSON schema template for LLM output.
        
        Returns:
            JSON schema string as formatted JSON
        """
        schema = {
            "image_meta": {
                "width": "int (image width in pixels)",
                "height": "int (image height in pixels)"
            },
            "participants": {
                "self": {
                    "id": "string (user identifier)",
                    "nickname": "string (user nickname if visible)"
                },
                "other": {
                    "id": "string (other participant identifier)",
                    "nickname": "string (other participant nickname if visible)"
                }
            },
            "bubbles": [
                {
                    "bubble_id": "string (unique identifier for this bubble)",
                    "bbox": {
                        "x1": "int (left coordinate)",
                        "y1": "int (top coordinate)",
                        "x2": "int (right coordinate)",
                        "y2": "int (bottom coordinate)"
                    },
                    "center_x": "int (horizontal center)",
                    "center_y": "int (vertical center)",
                    "text": "string (extracted text content)",
                    "sender": "string (either 'user' or 'talker')",
                    "column": "string (either 'left' or 'right')",
                    "confidence": "float (0.0 to 1.0, your confidence in this extraction)"
                }
            ],
            "layout": {
                "type": "string (e.g., 'two_columns')",
                "left_role": "string (either 'user' or 'talker')",
                "right_role": "string (either 'user' or 'talker')"
            }
        }
        
        return json.dumps(schema, indent=2)
