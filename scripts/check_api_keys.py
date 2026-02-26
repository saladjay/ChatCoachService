#!/usr/bin/env python3
"""
Check API Keys Status
检查 API 密钥状态
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env
from dotenv import load_dotenv
load_dotenv(project_root / ".env")


async def check_openrouter():
    """Check OpenRouter API key."""
    print("\n" + "=" * 80)
    print("  OPENROUTER API KEY CHECK")
    print("=" * 80 + "\n")
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in .env")
        return False
    
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"Base URL: {base_url}")
    print()
    
    # Test the API key
    try:
        import httpx
        
        print("Testing API key with a simple request...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "mistralai/ministral-3b-2512",
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ],
                    "max_tokens": 10,
                }
            )
            
            if response.status_code == 200:
                print("✅ API key is VALID")
                print(f"Response: {response.json()}")
                return True
            elif response.status_code == 401:
                print("❌ API key is INVALID (401 Unauthorized)")
                print(f"Response: {response.text}")
                return False
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing API key: {e}")
        return False


async def check_dashscope():
    """Check DashScope API key."""
    print("\n" + "=" * 80)
    print("  DASHSCOPE API KEY CHECK")
    print("=" * 80 + "\n")
    
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
    
    if not api_key:
        print("❌ DASHSCOPE_API_KEY not found in .env")
        return False
    
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"Base URL: {base_url}")
    print()
    
    # Test the API key
    try:
        import httpx
        
        print("Testing API key with a simple request...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/services/aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen-turbo",
                    "input": {
                        "messages": [
                            {"role": "user", "content": "Hello"}
                        ]
                    },
                    "parameters": {
                        "max_tokens": 10,
                    }
                }
            )
            
            if response.status_code == 200:
                print("✅ API key is VALID")
                result = response.json()
                if result.get("code"):
                    print(f"⚠️  API returned error code: {result.get('code')}")
                    print(f"Message: {result.get('message')}")
                    return False
                print(f"Response: {result}")
                return True
            elif response.status_code == 401:
                print("❌ API key is INVALID (401 Unauthorized)")
                print(f"Response: {response.text}")
                return False
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing API key: {e}")
        return False


async def check_vertex_ai():
    """Check Vertex AI credentials."""
    print("\n" + "=" * 80)
    print("  VERTEX AI CREDENTIALS CHECK")
    print("=" * 80 + "\n")
    
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not creds_path:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not found in .env")
        return False
    
    print(f"Credentials file: {creds_path}")
    
    # Check if file exists
    if not os.path.exists(creds_path):
        print(f"❌ Credentials file not found: {creds_path}")
        return False
    
    print("✅ Credentials file exists")
    
    # Try to load credentials
    try:
        import json
        with open(creds_path, 'r') as f:
            creds = json.load(f)
        
        print(f"Project ID: {creds.get('project_id')}")
        print(f"Client email: {creds.get('client_email')}")
        print("✅ Credentials file is valid JSON")
        return True
        
    except Exception as e:
        print(f"❌ Error loading credentials: {e}")
        return False


async def main():
    """Main function."""
    print("\n" + "=" * 80)
    print("  API KEYS STATUS CHECK")
    print("=" * 80)
    
    results = {}
    
    # Check OpenRouter
    results['openrouter'] = await check_openrouter()
    
    # Check DashScope
    results['dashscope'] = await check_dashscope()
    
    # Check Vertex AI
    results['vertex_ai'] = await check_vertex_ai()
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80 + "\n")
    
    for provider, status in results.items():
        status_str = "✅ VALID" if status else "❌ INVALID"
        print(f"{provider:20s}: {status_str}")
    
    print()
    
    # Recommendations
    print("=" * 80)
    print("  RECOMMENDATIONS")
    print("=" * 80 + "\n")
    
    if not results['openrouter']:
        print("⚠️  OpenRouter API key is invalid!")
        print("   Solutions:")
        print("   1. Update OPENROUTER_API_KEY in .env with a valid key")
        print("   2. Or switch to another provider:")
        print("      - Set LLM_DEFAULT_PROVIDER=dashscope (if DashScope is valid)")
        print("      - Set LLM_DEFAULT_PROVIDER=gemini (if Vertex AI is valid)")
        print()
    
    if results['openrouter']:
        print("✅ OpenRouter is working - no changes needed")
        print()
    elif results['dashscope']:
        print("✅ DashScope is available - you can switch to it:")
        print("   LLM_DEFAULT_PROVIDER=dashscope")
        print()
    elif results['vertex_ai']:
        print("✅ Vertex AI is available - you can switch to it:")
        print("   LLM_DEFAULT_PROVIDER=gemini")
        print()
    else:
        print("❌ No valid API keys found!")
        print("   Please update at least one API key in .env")
        print()


if __name__ == "__main__":
    asyncio.run(main())
