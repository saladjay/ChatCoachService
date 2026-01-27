"""
同步 prompt_compact.py 中的 prompt 到 prompts/versions/ 目录

这个脚本将代码中定义的 compact prompt 同步到文件系统，
使其能够被现有的 prompt 管理工具管理。

Usage:
    python scripts/sync_prompts_to_files.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.prompt_manager import PromptType, PromptVersion


PROMPTS_DIR = project_root / "prompts"
VERSIONS_DIR = PROMPTS_DIR / "versions"


def _read_version(prompt_type: PromptType, version: PromptVersion) -> str:
    path = VERSIONS_DIR / f"{prompt_type.value}_{version.value}.txt"
    return path.read_text(encoding="utf-8").strip()


def sync_prompts():
    """同步所有 prompt 到文件系统"""
    
    prompts_dir = PROMPTS_DIR
    versions_dir = VERSIONS_DIR
    metadata_dir = prompts_dir / "metadata"
    active_dir = prompts_dir / "active"
    registry_file = prompts_dir / "registry.json"
    
    # 确保目录存在
    versions_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    active_dir.mkdir(parents=True, exist_ok=True)
    
    # 读取现有 registry
    if registry_file.exists():
        with open(registry_file, 'r', encoding='utf-8') as f:
            registry = json.load(f)
    else:
        registry = {"prompts": {}}
    
    # 定义要同步的 prompt
    prompts_to_sync = [
        {
            "name": PromptType.CONTEXT_SUMMARY.value,
            "version": PromptVersion.V3_1_COMPACT_V2.value,
            "content": _read_version(PromptType.CONTEXT_SUMMARY, PromptVersion.V3_1_COMPACT_V2),
            "description": "Context summary - compact V2 with compressed output",
            "version_id": "context_summary_compact_v2",
        },
        {
            "name": PromptType.SCENARIO_ANALYSIS.value,
            "version": PromptVersion.V3_1_COMPACT_V2.value,
            "content": _read_version(PromptType.SCENARIO_ANALYSIS, PromptVersion.V3_1_COMPACT_V2),
            "description": "Scenario analysis - compact V2 with compressed codes",
            "version_id": "scene_analyzer_compact_v2",
        },
        {
            "name": PromptType.REPLY_GENERATION.value,
            "version": PromptVersion.V2_COMPACT.value,
            "content": _read_version(PromptType.REPLY_GENERATION, PromptVersion.V2_COMPACT),
            "description": "Reply generation - compact version with reasoning",
            "version_id": "reply_generation_compact_v1",
        },
        {
            "name": PromptType.REPLY_GENERATION.value,
            "version": PromptVersion.V3_1_COMPACT_V2_WITH_REASONING.value,
            "content": _read_version(PromptType.REPLY_GENERATION, PromptVersion.V3_1_COMPACT_V2_WITH_REASONING),
            "description": "Reply generation - compact V2 with reasoning",
            "version_id": "reply_generation_compact_v2_with_reasoning",
        },
        {
            "name": PromptType.REPLY_GENERATION.value,
            "version": PromptVersion.V3_2_COMPACT_V2_WITHOUT_REASONING.value,
            "content": _read_version(PromptType.REPLY_GENERATION, PromptVersion.V3_2_COMPACT_V2_WITHOUT_REASONING),
            "description": "Reply generation - compact V2 without reasoning (most optimized)",
            "version_id": "reply_generation_compact_v2_no_reasoning",
        },
    ]
    
    print("=" * 80)
    print("同步 Prompt 到文件系统")
    print("=" * 80)
    print()
    
    for prompt_info in prompts_to_sync:
        name = prompt_info["name"]
        version = prompt_info["version"]
        content = prompt_info["content"]
        description = prompt_info["description"]
        version_id = prompt_info["version_id"]
        
        prompt_id = f"{name}_{version}"
        
        # 1. 写入 versions/ 目录
        version_file = versions_dir / f"{prompt_id}.txt"
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(content.strip() + "\n")
        print(f"✓ 写入版本文件: {version_file.relative_to(project_root)}")
        
        # 2. 写入 metadata
        metadata_file = metadata_dir / f"{prompt_id}.json"
        metadata = {
            "prompt_id": prompt_id,
            "prompt_type": name,
            "version": version,
            "created_at": datetime.now().isoformat(),
            "author": "system",
            "description": description,
            "tags": ["compact", "optimized", "token-reduced"],
            "token_estimate": len(content) // 4,  # 粗略估算
            "performance_notes": f"Version ID: {version_id}",
            "is_active": False,  # 稍后更新 active 版本
            "parent_version": None,
        }
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"✓ 写入元数据: {metadata_file.relative_to(project_root)}")
        
        # 3. 更新 registry
        if name not in registry["prompts"]:
            registry["prompts"][name] = []
        
        # 检查是否已存在
        existing = [p for p in registry["prompts"][name] if p["prompt_id"] == prompt_id]
        if not existing:
            registry["prompts"][name].append({
                "prompt_id": prompt_id,
                "version": version,
                "version_id": version_id,
                "created_at": datetime.now().isoformat(),
            })
            print(f"✓ 添加到注册表: {name} -> {version}")
        else:
            print(f"  (已存在于注册表: {name} -> {version})")
        
        print()
    
    # 4. 写入更新后的 registry
    with open(registry_file, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    print(f"✓ 更新注册表: {registry_file.relative_to(project_root)}")
    print()
    
    # 5. 更新 active/ 目录（指向最新版本）
    active_versions = {
        PromptType.CONTEXT_SUMMARY.value: PromptVersion.V3_1_COMPACT_V2.value,
        PromptType.SCENARIO_ANALYSIS.value: PromptVersion.V3_1_COMPACT_V2.value,
        PromptType.REPLY_GENERATION.value: PromptVersion.V3_2_COMPACT_V2_WITHOUT_REASONING.value,  # 最优化版本
    }
    
    print("更新 active/ 目录:")
    for name, version in active_versions.items():
        prompt_id = f"{name}_{version}"
        source_file = versions_dir / f"{prompt_id}.txt"
        active_file = active_dir / f"{name}.txt"
        
        if source_file.exists():
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(active_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ {name}.txt -> {version}")
    
    print()
    print("=" * 80)
    print("同步完成！")
    print("=" * 80)
    print()
    print("现在可以使用以下工具管理 prompt:")
    print("  - python scripts/manage_prompts.py list")
    print("  - python scripts/manage_prompts.py show <prompt_name>")
    print("  - python scripts/manage_prompts.py compare <prompt_name> <version1> <version2>")
    print()


if __name__ == "__main__":
    sync_prompts()
