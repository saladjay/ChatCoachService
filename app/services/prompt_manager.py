"""
Prompt Version Management System

A lightweight, file-based prompt versioning system that:
- Tracks prompt versions with metadata
- Supports rollback and comparison
- Integrates with Git for version control
- Provides A/B testing capabilities
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class PromptVersion(Enum):
    """Prompt version identifiers"""
    V1_ORIGINAL = "v1.0-original"
    V2_COMPACT = "v2.0-compact"
    V2_1_OPTIMIZED = "v2.1-optimized"
    V3_0_COMPACT = "v3.0-compact"
    V3_1_COMPACT_V2 = "v3.1-compact_v2"
    V3_1_COMPACT_V2_WITH_REASONING = "v3.1-compact_v2_with_reasoning"
    V3_2_COMPACT_V2_WITHOUT_REASONING = "v3.2-compact_v2_no_reasoning"
    V3_3 = "v3.3"


class PromptType(Enum):
    """Types of prompts in the system"""
    SCENARIO_ANALYSIS = "scenario_analysis"
    CONTEXT_SUMMARY = "context_summary"
    REPLY_GENERATION = "reply_generation"
    TRAIT_DISCOVERY = "trait_discovery"
    TRAIT_MAPPING = "trait_mapping"
    SCREENSHOT_PARSE = "screenshot_parse"
    PREFERENCE_ANALYSIS = "preference_analysis"
    MERGE_STEP = "merge_step"


@dataclass
class PromptMetadata:
    """Metadata for a prompt version"""
    prompt_id: str
    prompt_type: str
    version: str
    created_at: str
    author: str
    description: str
    tags: List[str]
    token_estimate: int
    performance_notes: str
    is_active: bool
    parent_version: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PromptMetadata':
        return cls(**data)


class PromptManager:
    """
    Manages prompt versions with file-based storage.
    
    Features:
    - Version tracking with metadata
    - Rollback capabilities
    - A/B testing support
    - Git-friendly storage
    """
    
    def __init__(self, prompts_dir: str = "prompts"):
        """
        Initialize PromptManager.
        
        Args:
            prompts_dir: Directory to store prompt versions
        """
        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.prompts_dir / "versions").mkdir(exist_ok=True)
        (self.prompts_dir / "metadata").mkdir(exist_ok=True)
        (self.prompts_dir / "active").mkdir(exist_ok=True)
        
        self.registry_file = self.prompts_dir / "registry.json"
        self._load_registry()
    
    def _load_registry(self):
        """Load prompt registry from file"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                self.registry = json.load(f)
        else:
            self.registry = {
                "prompts": {},
                "active_versions": {},
                "version_history": []
            }
    
    def _save_registry(self):
        """Save prompt registry to file"""
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)
    
    def register_prompt(
        self,
        prompt_type: PromptType,
        version: PromptVersion,
        content: str,
        author: str = "system",
        description: str = "",
        tags: List[str] = None,
        token_estimate: int = 0,
        performance_notes: str = "",
        parent_version: Optional[str] = None
    ) -> str:
        """
        Register a new prompt version.
        
        Args:
            prompt_type: Type of prompt
            version: Version identifier
            content: Prompt content
            author: Author name
            description: Version description
            tags: Tags for categorization
            token_estimate: Estimated token count
            performance_notes: Performance observations
            parent_version: Parent version if this is a modification
        
        Returns:
            Prompt ID
        """
        # Generate prompt ID
        prompt_id = self._generate_prompt_id(prompt_type, version)
        
        # Create metadata
        metadata = PromptMetadata(
            prompt_id=prompt_id,
            prompt_type=prompt_type.value,
            version=version.value,
            created_at=datetime.now().isoformat(),
            author=author,
            description=description,
            tags=tags or [],
            token_estimate=token_estimate,
            performance_notes=performance_notes,
            is_active=False,
            parent_version=parent_version
        )
        
        # Save prompt content
        version_file = self.prompts_dir / "versions" / f"{prompt_id}.txt"
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Save metadata
        metadata_file = self.prompts_dir / "metadata" / f"{prompt_id}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Update registry
        if prompt_type.value not in self.registry["prompts"]:
            self.registry["prompts"][prompt_type.value] = []
        
        self.registry["prompts"][prompt_type.value].append({
            "prompt_id": prompt_id,
            "version": version.value,
            "created_at": metadata.created_at
        })
        
        self.registry["version_history"].append({
            "prompt_id": prompt_id,
            "action": "register",
            "timestamp": datetime.now().isoformat(),
            "author": author
        })
        
        self._save_registry()
        
        return prompt_id
    
    def activate_version(
        self,
        prompt_type: PromptType,
        version: PromptVersion,
        author: str = "system"
    ) -> bool:
        """
        Activate a specific prompt version.
        
        Args:
            prompt_type: Type of prompt
            version: Version to activate
            author: Who activated this version
        
        Returns:
            Success status
        """
        prompt_id = self._generate_prompt_id(prompt_type, version)
        
        # Check if version exists
        version_file = self.prompts_dir / "versions" / f"{prompt_id}.txt"
        if not version_file.exists():
            return False
        
        # Deactivate current version
        if prompt_type.value in self.registry["active_versions"]:
            old_id = self.registry["active_versions"][prompt_type.value]
            self._update_metadata(old_id, {"is_active": False})
        
        # Activate new version
        self.registry["active_versions"][prompt_type.value] = prompt_id
        self._update_metadata(prompt_id, {"is_active": True})
        
        # Create symlink in active directory
        active_link = self.prompts_dir / "active" / f"{prompt_type.value}.txt"
        if active_link.exists():
            active_link.unlink()
        
        # Copy content to active
        with open(version_file, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(active_link, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Log activation
        self.registry["version_history"].append({
            "prompt_id": prompt_id,
            "action": "activate",
            "timestamp": datetime.now().isoformat(),
            "author": author
        })
        
        self._save_registry()
        
        return True
    
    def get_active_prompt(self, prompt_type: PromptType) -> Optional[str]:
        """
        Get the currently active prompt for a type.
        
        Args:
            prompt_type: Type of prompt
        
        Returns:
            Prompt content or None
        """
        active_file = self.prompts_dir / "active" / f"{prompt_type.value}.txt"
        
        if active_file.exists():
            with open(active_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
    
    def get_prompt_version(
        self,
        prompt_type: PromptType,
        version: PromptVersion
    ) -> Optional[str]:
        """
        Get a specific prompt version.
        
        Args:
            prompt_type: Type of prompt
            version: Version identifier
        
        Returns:
            Prompt content or None
        """
        prompt_id = self._generate_prompt_id(prompt_type, version)
        version_file = self.prompts_dir / "versions" / f"{prompt_id}.txt"
        
        if version_file.exists():
            with open(version_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
    
    def get_metadata(self, prompt_id: str) -> Optional[PromptMetadata]:
        """
        Get metadata for a prompt version.
        
        Args:
            prompt_id: Prompt identifier
        
        Returns:
            PromptMetadata or None
        """
        metadata_file = self.prompts_dir / "metadata" / f"{prompt_id}.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return PromptMetadata.from_dict(data)
        
        return None
    
    def list_versions(
        self,
        prompt_type: Optional[PromptType] = None
    ) -> List[Dict[str, Any]]:
        """
        List all prompt versions.
        
        Args:
            prompt_type: Filter by prompt type (optional)
        
        Returns:
            List of version information
        """
        versions = []
        
        if prompt_type:
            prompt_list = self.registry["prompts"].get(prompt_type.value, [])
        else:
            prompt_list = []
            for prompts in self.registry["prompts"].values():
                prompt_list.extend(prompts)
        
        for prompt_info in prompt_list:
            metadata = self.get_metadata(prompt_info["prompt_id"])
            if metadata:
                versions.append({
                    "prompt_id": prompt_info["prompt_id"],
                    "version": prompt_info["version"],
                    "created_at": prompt_info["created_at"],
                    "is_active": metadata.is_active,
                    "description": metadata.description,
                    "token_estimate": metadata.token_estimate
                })
        
        return versions
    
    def compare_versions(
        self,
        prompt_type: PromptType,
        version1: PromptVersion,
        version2: PromptVersion
    ) -> Dict[str, Any]:
        """
        Compare two prompt versions.
        
        Args:
            prompt_type: Type of prompt
            version1: First version
            version2: Second version
        
        Returns:
            Comparison results
        """
        content1 = self.get_prompt_version(prompt_type, version1)
        content2 = self.get_prompt_version(prompt_type, version2)
        
        if not content1 or not content2:
            return {"error": "One or both versions not found"}
        
        id1 = self._generate_prompt_id(prompt_type, version1)
        id2 = self._generate_prompt_id(prompt_type, version2)
        
        meta1 = self.get_metadata(id1)
        meta2 = self.get_metadata(id2)
        
        return {
            "version1": {
                "version": version1.value,
                "length": len(content1),
                "token_estimate": meta1.token_estimate if meta1 else 0,
                "created_at": meta1.created_at if meta1 else None
            },
            "version2": {
                "version": version2.value,
                "length": len(content2),
                "token_estimate": meta2.token_estimate if meta2 else 0,
                "created_at": meta2.created_at if meta2 else None
            },
            "diff": {
                "length_change": len(content2) - len(content1),
                "length_change_pct": ((len(content2) - len(content1)) / len(content1) * 100) if len(content1) > 0 else 0,
                "token_change": (meta2.token_estimate - meta1.token_estimate) if (meta1 and meta2) else 0
            }
        }
    
    def rollback(
        self,
        prompt_type: PromptType,
        target_version: PromptVersion,
        author: str = "system"
    ) -> bool:
        """
        Rollback to a previous version.
        
        Args:
            prompt_type: Type of prompt
            target_version: Version to rollback to
            author: Who performed the rollback
        
        Returns:
            Success status
        """
        return self.activate_version(prompt_type, target_version, author)
    
    def export_version(
        self,
        prompt_type: PromptType,
        version: PromptVersion,
        output_file: str
    ) -> bool:
        """
        Export a prompt version to a file.
        
        Args:
            prompt_type: Type of prompt
            version: Version to export
            output_file: Output file path
        
        Returns:
            Success status
        """
        content = self.get_prompt_version(prompt_type, version)
        if not content:
            return False
        
        prompt_id = self._generate_prompt_id(prompt_type, version)
        metadata = self.get_metadata(prompt_id)
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Prompt Version: {version.value}\n")
            f.write(f"# Type: {prompt_type.value}\n")
            if metadata:
                f.write(f"# Created: {metadata.created_at}\n")
                f.write(f"# Author: {metadata.author}\n")
                f.write(f"# Description: {metadata.description}\n")
                f.write(f"# Token Estimate: {metadata.token_estimate}\n")
            f.write("\n")
            f.write(content)
        
        return True
    
    def _generate_prompt_id(
        self,
        prompt_type: PromptType,
        version: PromptVersion
    ) -> str:
        """Generate a unique prompt ID"""
        return f"{prompt_type.value}_{version.value}"
    
    def _update_metadata(self, prompt_id: str, updates: Dict[str, Any]):
        """Update metadata for a prompt"""
        metadata_file = self.prompts_dir / "metadata" / f"{prompt_id}.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data.update(updates)
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)


# Global prompt manager instance
_prompt_manager = None


def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
