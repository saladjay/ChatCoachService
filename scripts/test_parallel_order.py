"""Test that parallel processing maintains original content order."""

import asyncio


async def test_order_preservation():
    """Test that parallel processing maintains the original order of content."""
    print("=" * 80)
    print("Testing Parallel Processing Order Preservation")
    print("=" * 80)
    
    # Original content order
    content = [
        "text1",
        "https://example.com/image2.png",
        "text3",
        "https://example.com/image4.png",
        "text5",
    ]
    
    print(f"\n1. Original content order:")
    for idx, item in enumerate(content):
        content_type = "text" if not item.startswith("http") else "image"
        print(f"   [{idx}] {content_type}: {item}")
    
    # Simulate parallel processing with random delays
    async def process_single_content(content_url: str, index: int):
        """Simulate processing a single content item."""
        import random
        
        # Simulate random processing time
        delay = random.uniform(0.1, 0.5)
        await asyncio.sleep(delay)
        
        # Determine type
        if content_url.startswith("http"):
            kind = "image"
        else:
            kind = "text"
        
        return (index, kind, content_url, f"{kind}_result_{index}")
    
    # Create tasks
    content_tasks = [
        process_single_content(url, idx) 
        for idx, url in enumerate(content)
    ]
    
    # Execute in parallel
    print(f"\n2. Executing {len(content_tasks)} tasks in parallel...")
    content_results = await asyncio.gather(*content_tasks)
    
    print(f"\n3. Raw results (may be out of order):")
    for result in content_results:
        idx, kind, url, _ = result
        print(f"   [{idx}] {kind}: {url}")
    
    # Sort by original index
    print(f"\n4. Sorting by original index...")
    content_results_sorted = sorted(content_results, key=lambda x: x[0])
    
    print(f"   Sorted results:")
    for result in content_results_sorted:
        idx, kind, url, _ = result
        print(f"   [{idx}] {kind}: {url}")
    
    # Extract items without index
    items = [(kind, url, result) for _, kind, url, result in content_results_sorted]
    
    # Verify order
    print(f"\n5. Verifying order preservation...")
    success = True
    
    for idx, (original, (kind, url, _)) in enumerate(zip(content, items)):
        expected_type = "text" if not original.startswith("http") else "image"
        
        if kind != expected_type or url != original:
            print(f"   ❌ Mismatch at index {idx}:")
            print(f"      Expected: {expected_type} - {original}")
            print(f"      Got:      {kind} - {url}")
            success = False
        else:
            print(f"   ✅ [{idx}] {kind}: {url[:30]}...")
    
    # Test last content identification
    print(f"\n6. Testing last content identification...")
    last_content_type = items[-1][0]
    last_content_value = items[-1][1]
    
    expected_last_type = "text"
    expected_last_value = "text5"
    
    if last_content_type == expected_last_type and last_content_value == expected_last_value:
        print(f"   ✅ Last content correctly identified:")
        print(f"      Type: {last_content_type}")
        print(f"      Value: {last_content_value}")
    else:
        print(f"   ❌ Last content identification failed:")
        print(f"      Expected: {expected_last_type} - {expected_last_value}")
        print(f"      Got:      {last_content_type} - {last_content_value}")
        success = False
    
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(test_order_preservation())
        
        print("\n" + "=" * 80)
        if success:
            print("✅ All order preservation tests passed!")
        else:
            print("❌ Some tests failed. Check the output above.")
        print("=" * 80)
        
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
