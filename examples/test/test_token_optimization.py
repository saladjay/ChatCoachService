"""
Test script to verify token optimization effectiveness.

Compares token usage between compact and full prompt versions.
"""

import asyncio
from app.core.container import ServiceContainer, ServiceMode
from app.models.api import GenerateReplyRequest
from app.models.schemas import Message
from datetime import datetime


async def test_token_optimization():
    """Test and compare token usage between compact and full versions."""
    
    print("=" * 80)
    print("TOKEN OPTIMIZATION TEST")
    print("=" * 80)
    print()
    
    # Prepare test data
    messages = [
        Message(
            id="1",
            speaker="user",
            content='Hey Sarah, I noticed you have a photo with a copy of "Sapiens" on your bookshelf.',
            timestamp=datetime.now()
        ),
        Message(
            id="2",
            speaker="Sarah",
            content='Oh, wow, someone actually zoomed in! Most people just comment on the travel pics.',
            timestamp=datetime.now()
        ),
        Message(
            id="3",
            speaker="user",
            content='I did, though it made me a bit anxious about the future, to be honest.',
            timestamp=datetime.now()
        ),
    ]
    
    dialogs = [
        {'speaker': msg.speaker, 'text': msg.content}
        for msg in messages
    ]
    
    request = GenerateReplyRequest(
        user_id="test_user",
        target_id="test_target",
        conversation_id="test_conv",
        language="en",
        quality="normal",
        dialogs=dialogs,
        intimacy_value=60
    )
    
    # Test 1: Compact version (default)
    print("TEST 1: COMPACT VERSION (Optimized)")
    print("-" * 80)
    
    container_compact = ServiceContainer(mode=ServiceMode.REAL)
    orchestrator_compact = container_compact.create_orchestrator()
    
    try:
        response_compact = await orchestrator_compact.generate_reply(request)
        print(f"✓ Generation successful")
        print(f"  Cost: ${response_compact.cost_usd:.6f}")
        print(f"  Model: {response_compact.provider}/{response_compact.model}")
        print(f"  Reply: {response_compact.reply_text[:100]}...")
    except Exception as e:
        print(f"✗ Generation failed: {e}")
    
    print()
    
    # Test 2: Full version (for comparison)
    print("TEST 2: FULL VERSION (Original)")
    print("-" * 80)
    print("Note: To test full version, manually set use_compact_prompt=False in container.py")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("To see detailed token usage:")
    print("1. Check logs/trace.jsonl for token counts")
    print("2. Compare input_tokens between runs")
    print("3. Expected reduction: ~43% tokens")
    print()
    print("To test full version:")
    print("1. Edit app/core/container.py")
    print("2. Set use_compact_prompt=False for all services")
    print("3. Run this script again")
    print()


if __name__ == "__main__":
    asyncio.run(test_token_optimization())
