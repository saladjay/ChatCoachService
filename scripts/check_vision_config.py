#!/usr/bin/env python3
"""
Vision API Configuration Checker

This script checks if the vision/multimodal API is properly configured.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_env_variables():
    """Check environment variables."""
    print("=" * 80)
    print("1. Checking Environment Variables")
    print("=" * 80)
    
    multimodal_provider = os.getenv("MULTIMODAL_DEFAULT_PROVIDER")
    if multimodal_provider:
        print(f"✅ MULTIMODAL_DEFAULT_PROVIDER: {multimodal_provider}")
    else:
        print("⚠️  MULTIMODAL_DEFAULT_PROVIDER not set (will auto-select)")
    
    # Check provider-specific keys
    providers = {
        "gemini": "GOOGLE_APPLICATION_CREDENTIALS",
        "openrouter": "OPENROUTER_API_KEY",
        "dashscope": "DASHSCOPY_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    
    print("\nProvider API Keys:")
    for provider, env_var in providers.items():
        value = os.getenv(env_var)
        if value:
            # Mask the key for security
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  ✅ {provider}: {env_var}={masked}")
        else:
            print(f"  ❌ {provider}: {env_var} not set")
    
    print()


def check_config_file():
    """Check config.yaml file."""
    print("=" * 80)
    print("2. Checking config.yaml")
    print("=" * 80)
    
    config_path = project_root / "core" / "llm_adapter" / "config.yaml"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    print(f"✅ Config file found: {config_path}")
    
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Check default provider
        default_provider = config.get("llm", {}).get("default_provider")
        print(f"\nDefault Provider: {default_provider}")
        
        # Check multimodal models
        print("\nMultimodal Models:")
        providers = config.get("providers", {})
        for provider_name, provider_config in providers.items():
            models = provider_config.get("models", {})
            multimodal_model = models.get("multimodal")
            if multimodal_model:
                print(f"  ✅ {provider_name}: {multimodal_model}")
            else:
                print(f"  ❌ {provider_name}: No multimodal model configured")
        
    except Exception as e:
        print(f"❌ Error reading config: {e}")
    
    print()


def check_adapters():
    """Check which adapters support vision."""
    print("=" * 80)
    print("3. Checking Adapter Vision Support")
    print("=" * 80)
    
    adapters_dir = project_root / "core" / "llm_adapter" / "llm_adapter" / "adapters"
    
    if not adapters_dir.exists():
        print(f"❌ Adapters directory not found: {adapters_dir}")
        return
    
    # Check each adapter file
    adapter_files = list(adapters_dir.glob("*_adapter.py"))
    
    for adapter_file in adapter_files:
        adapter_name = adapter_file.stem.replace("_adapter", "")
        
        # Read file and check for vision support
        try:
            content = adapter_file.read_text(encoding='utf-8')
            has_vision = "call_vision" in content or "image_base64" in content
            
            if has_vision:
                print(f"  ✅ {adapter_name}: Vision support detected")
            else:
                print(f"  ❌ {adapter_name}: No vision support")
        except Exception as e:
            print(f"  ⚠️  {adapter_name}: Error checking ({e})")
    
    print()


def check_credentials():
    """Check Google Cloud credentials for Gemini."""
    print("=" * 80)
    print("4. Checking Google Cloud Credentials (for Gemini)")
    print("=" * 80)
    
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not creds_path:
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set")
        print("   Gemini Vertex AI mode will not work")
    else:
        creds_file = Path(creds_path)
        if creds_file.exists():
            print(f"✅ Credentials file found: {creds_path}")
            
            # Try to load and validate
            try:
                import json
                with open(creds_file, 'r') as f:
                    creds = json.load(f)
                
                project_id = creds.get("project_id")
                if project_id:
                    print(f"   Project ID: {project_id}")
                else:
                    print("   ⚠️  No project_id in credentials")
            except Exception as e:
                print(f"   ⚠️  Error reading credentials: {e}")
        else:
            print(f"❌ Credentials file not found: {creds_path}")
    
    print()


def provide_recommendations():
    """Provide recommendations based on checks."""
    print("=" * 80)
    print("5. Recommendations")
    print("=" * 80)
    
    multimodal_provider = os.getenv("MULTIMODAL_DEFAULT_PROVIDER")
    
    if not multimodal_provider:
        print("⚠️  MULTIMODAL_DEFAULT_PROVIDER not set")
        print("\nRecommendation:")
        print("  Add to .env file:")
        print("  MULTIMODAL_DEFAULT_PROVIDER=gemini")
        print()
    
    # Check if DashScope is default but no multimodal provider set
    try:
        import yaml
        config_path = project_root / "core" / "llm_adapter" / "config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        default_provider = config.get("llm", {}).get("default_provider")
        
        if default_provider == "dashscope" and not multimodal_provider:
            print("⚠️  DashScope is default provider but doesn't support vision")
            print("\nRecommendation:")
            print("  DashScope is good for text generation but doesn't support vision.")
            print("  Add to .env file:")
            print("  MULTIMODAL_DEFAULT_PROVIDER=gemini")
            print("\n  This will use:")
            print("  - DashScope for text generation")
            print("  - Gemini for screenshot analysis (vision)")
            print()
    except Exception:
        pass
    
    print("For more details, see: docs/VISION_API_PROVIDER_FIX.md")
    print()


def main():
    """Main function."""
    print("\n" + "=" * 80)
    print("Vision API Configuration Checker")
    print("=" * 80)
    print()
    
    # Load .env file if exists
    env_file = project_root / ".env"
    if env_file.exists():
        print(f"Loading environment from: {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print()
    
    # Run checks
    check_env_variables()
    check_config_file()
    check_adapters()
    check_credentials()
    provide_recommendations()
    
    print("=" * 80)
    print("Check complete!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
