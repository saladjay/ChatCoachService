"""Test Vertex AI Gemini configuration."""

import os
import sys
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_vertex_ai():
    """Test Vertex AI Gemini connection."""
    print("=" * 80)
    print("Testing Vertex AI Gemini Configuration")
    print("=" * 80)
    
    # Check environment variable
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"\n1. Checking GOOGLE_APPLICATION_CREDENTIALS...")
    print(f"   Path: {creds_path}")
    
    if not creds_path:
        print("   ❌ GOOGLE_APPLICATION_CREDENTIALS not set!")
        return False
    
    if not os.path.exists(creds_path):
        print(f"   ❌ Credentials file not found: {creds_path}")
        return False
    
    print("   ✅ Credentials file exists")
    
    # Test LLM adapter
    print(f"\n2. Testing LLM Adapter with Vertex AI...")
    try:
        from app.services.llm_adapter import create_llm_adapter
        
        adapter = create_llm_adapter()
        print(f"   Adapter created successfully")
        
        # Test with a simple prompt
        print(f"\n3. Testing Gemini model call...")
        prompt = "Say 'Hello from Vertex AI!' in one sentence."
        
        from app.services.llm_adapter import LLMCall
        
        call = LLMCall(
            prompt=prompt,
            provider="gemini",
            model="gemini-2.0-flash-lite",
            task_type="test"
        )
        
        result = await adapter.call(call)
        
        print(f"   ✅ Success!")
        print(f"   Provider: {result.provider}")
        print(f"   Model: {result.model}")
        print(f"   Response: {result.text[:100]}...")
        print(f"   Input tokens: {result.input_tokens}")
        print(f"   Output tokens: {result.output_tokens}")
        print(f"   Cost: ${result.cost_usd:.6f}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_vertex_ai())
    
    print("\n" + "=" * 80)
    if success:
        print("✅ Vertex AI configuration is working correctly!")
    else:
        print("❌ Vertex AI configuration has issues. Please check the errors above.")
    print("=" * 80)
    
    sys.exit(0 if success else 1)
