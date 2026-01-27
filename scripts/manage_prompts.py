"""
Prompt Management CLI Tool

Command-line interface for managing prompt versions.

Usage:
    python scripts/manage_prompts.py list
    python scripts/manage_prompts.py activate scenario_analysis v1.0-original
    python scripts/manage_prompts.py compare scenario_analysis v1.0-original v2.0-compact
    python scripts/manage_prompts.py export reply_generation v2.0-compact output.txt
    python scripts/manage_prompts.py rollback context_summary v1.0-original
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.prompt_manager import (
    PromptManager,
    PromptType,
    PromptVersion
)

# Simple table formatter (fallback for tabulate)
def simple_table(data, headers):
    """Simple table formatter"""
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # Format header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * w for w in widths)
    
    # Format rows
    rows = []
    for row in data:
        rows.append(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    
    return header_line + "\n" + separator + "\n" + "\n".join(rows)


def list_versions(args):
    """List all prompt versions"""
    manager = PromptManager()
    
    print("=" * 100)
    print("PROMPT VERSIONS")
    print("=" * 100)
    print()
    
    for prompt_type in PromptType:
        versions = manager.list_versions(prompt_type)
        
        if not versions:
            continue
        
        print(f"\n{prompt_type.value.upper()}")
        print("-" * 100)
        
        table_data = []
        for v in versions:
            status = "✓ ACTIVE" if v["is_active"] else ""
            table_data.append([
                status,
                v["version"],
                v["token_estimate"],
                v["created_at"][:10],
                v["description"][:50] + "..." if len(v["description"]) > 50 else v["description"]
            ])
        
        headers = ["Status", "Version", "Tokens", "Created", "Description"]
        print(simple_table(table_data, headers))
    
    print()


def activate_version(args):
    """Activate a specific prompt version"""
    manager = PromptManager()
    
    try:
        prompt_type = PromptType(args.prompt_type)
        version = PromptVersion(args.version)
    except ValueError as e:
        print(f"Error: Invalid prompt type or version - {e}")
        return
    
    success = manager.activate_version(prompt_type, version, author=args.author)
    
    if success:
        print(f"✓ Activated {prompt_type.value} version {version.value}")
    else:
        print(f"✗ Failed to activate {prompt_type.value} version {version.value}")


def compare_versions(args):
    """Compare two prompt versions"""
    manager = PromptManager()
    
    try:
        prompt_type = PromptType(args.prompt_type)
        version1 = PromptVersion(args.version1)
        version2 = PromptVersion(args.version2)
    except ValueError as e:
        print(f"Error: Invalid prompt type or version - {e}")
        return
    
    comparison = manager.compare_versions(prompt_type, version1, version2)
    
    if "error" in comparison:
        print(f"✗ {comparison['error']}")
        return
    
    print("=" * 80)
    print(f"COMPARISON: {prompt_type.value}")
    print("=" * 80)
    print()
    
    print(f"Version 1: {version1.value}")
    print(f"  Length:         {comparison['version1']['length']} chars")
    print(f"  Token Estimate: {comparison['version1']['token_estimate']} tokens")
    print(f"  Created:        {comparison['version1']['created_at']}")
    print()
    
    print(f"Version 2: {version2.value}")
    print(f"  Length:         {comparison['version2']['length']} chars")
    print(f"  Token Estimate: {comparison['version2']['token_estimate']} tokens")
    print(f"  Created:        {comparison['version2']['created_at']}")
    print()
    
    print("Difference:")
    print(f"  Length Change:  {comparison['diff']['length_change']:+d} chars ({comparison['diff']['length_change_pct']:+.1f}%)")
    print(f"  Token Change:   {comparison['diff']['token_change']:+d} tokens")
    print()


def export_version(args):
    """Export a prompt version to a file"""
    manager = PromptManager()
    
    try:
        prompt_type = PromptType(args.prompt_type)
        version = PromptVersion(args.version)
    except ValueError as e:
        print(f"Error: Invalid prompt type or version - {e}")
        return
    
    success = manager.export_version(prompt_type, version, args.output_file)
    
    if success:
        print(f"✓ Exported {prompt_type.value} version {version.value} to {args.output_file}")
    else:
        print(f"✗ Failed to export {prompt_type.value} version {version.value}")


def rollback_version(args):
    """Rollback to a previous version"""
    manager = PromptManager()
    
    try:
        prompt_type = PromptType(args.prompt_type)
        version = PromptVersion(args.version)
    except ValueError as e:
        print(f"Error: Invalid prompt type or version - {e}")
        return
    
    success = manager.rollback(prompt_type, version, author=args.author)
    
    if success:
        print(f"✓ Rolled back {prompt_type.value} to version {version.value}")
    else:
        print(f"✗ Failed to rollback {prompt_type.value} to version {version.value}")


def show_active(args):
    """Show currently active prompts"""
    manager = PromptManager()
    
    print("=" * 80)
    print("ACTIVE PROMPTS")
    print("=" * 80)
    print()
    
    for prompt_type in PromptType:
        active_version = manager.registry["active_versions"].get(prompt_type.value)
        if active_version:
            metadata = manager.get_metadata(active_version)
            if metadata:
                print(f"{prompt_type.value}:")
                print(f"  Version:        {metadata.version}")
                print(f"  Token Estimate: {metadata.token_estimate}")
                print(f"  Description:    {metadata.description}")
                print()


def register_from_file(args):
    """Register a prompt version from a file (optionally activate it)."""
    manager = PromptManager()

    try:
        prompt_type = PromptType(args.prompt_type)
        version = PromptVersion(args.version)
    except ValueError as e:
        print(f"Error: Invalid prompt type or version - {e}")
        return

    prompt_path = Path(args.file)
    if not prompt_path.is_absolute():
        prompt_path = project_root / prompt_path

    if not prompt_path.exists():
        print(f"Error: Prompt file not found: {prompt_path}")
        return

    content = prompt_path.read_text(encoding="utf-8")

    prompt_id = manager.register_prompt(
        prompt_type=prompt_type,
        version=version,
        content=content,
        author=args.author,
        description=args.description,
        tags=[t.strip() for t in (args.tags or "").split(",") if t.strip()],
        token_estimate=int(args.token_estimate or 0),
        performance_notes=args.performance_notes or "",
        parent_version=args.parent_version,
    )

    print(f"✓ Registered {prompt_type.value} version {version.value} (prompt_id={prompt_id})")

    if args.activate:
        success = manager.activate_version(prompt_type, version, author=args.author)
        if success:
            print(f"✓ Activated {prompt_type.value} version {version.value}")
        else:
            print(f"✗ Failed to activate {prompt_type.value} version {version.value}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Prompt Version Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  List all versions:
    python scripts/manage_prompts.py list
  
  Activate a version:
    python scripts/manage_prompts.py activate scenario_analysis v2.0-compact
  
  Compare versions:
    python scripts/manage_prompts.py compare reply_generation v1.0-original v2.0-compact
  
  Export a version:
    python scripts/manage_prompts.py export context_summary v2.0-compact output.txt
  
  Rollback to previous version:
    python scripts/manage_prompts.py rollback scenario_analysis v1.0-original
  
  Show active versions:
    python scripts/manage_prompts.py active

  Register from file (and optionally activate):
    python scripts/manage_prompts.py register screenshot_parse v2.0-compact prompts/versions/screenshot_parse_v2.0-compact.txt --activate
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List command
    subparsers.add_parser("list", help="List all prompt versions")
    
    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Activate a prompt version")
    activate_parser.add_argument("prompt_type", help="Prompt type")
    activate_parser.add_argument("version", help="Version to activate")
    activate_parser.add_argument("--author", default="cli_user", help="Author name")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two versions")
    compare_parser.add_argument("prompt_type", help="Prompt type")
    compare_parser.add_argument("version1", help="First version")
    compare_parser.add_argument("version2", help="Second version")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export a version to file")
    export_parser.add_argument("prompt_type", help="Prompt type")
    export_parser.add_argument("version", help="Version to export")
    export_parser.add_argument("output_file", help="Output file path")
    
    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to a version")
    rollback_parser.add_argument("prompt_type", help="Prompt type")
    rollback_parser.add_argument("version", help="Version to rollback to")
    rollback_parser.add_argument("--author", default="cli_user", help="Author name")
    
    # Active command
    subparsers.add_parser("active", help="Show active prompt versions")

    # Register command
    register_parser = subparsers.add_parser("register", help="Register a prompt version from a file")
    register_parser.add_argument("prompt_type", help="Prompt type")
    register_parser.add_argument("version", help="Version identifier")
    register_parser.add_argument("file", help="Path to prompt content file")
    register_parser.add_argument("--author", default="cli_user", help="Author name")
    register_parser.add_argument("--description", default="", help="Version description")
    register_parser.add_argument("--tags", default="", help="Comma-separated tags")
    register_parser.add_argument("--token-estimate", default="0", help="Estimated token count")
    register_parser.add_argument("--performance-notes", default="", help="Performance notes")
    register_parser.add_argument("--parent-version", default=None, help="Parent version prompt_id")
    register_parser.add_argument("--activate", action="store_true", help="Activate after registering")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    commands = {
        "list": list_versions,
        "activate": activate_version,
        "compare": compare_versions,
        "export": export_version,
        "rollback": rollback_version,
        "active": show_active,
        "register": register_from_file,
    }
    
    command_func = commands.get(args.command)
    if command_func:
        command_func(args)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()


if __name__ == "__main__":
    main()
