"""
Multimodal Image Formats Usage Example

This example demonstrates how to use LLMAdapterImpl with different image formats:
- URL format: Pass image via URL
- Base64 format: Pass image as base64-encoded string
- Multiple images: Mix URL and Base64 formats
"""

import asyncio
import base64
from pathlib import Path

from app.services.llm_adapter import LLMAdapterImpl


async def example_url_format():
    """Example: Using URL image format."""
    print("\n" + "="*60)
    print("Example 1: URL Image Format")
    print("="*60)
    
    adapter = LLMAdapterImpl()
    
    # Public image URL
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/320px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    
    result = await adapter.call_multimodal(
        prompt="Describe this landscape image in detail.",
        image_data=image_url,
        image_type="url",
        provider="openrouter",
        model="openai/gpt-4o-mini",
    )
    
    print(f"Provider: {result.provider}")
    print(f"Model: {result.model}")
    print(f"Response: {result.text}")
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
    print(f"Cost: ${result.cost_usd:.6f}")


async def example_base64_format():
    """Example: Using Base64 image format."""
    print("\n" + "="*60)
    print("Example 2: Base64 Image Format")
    print("="*60)
    
    adapter = LLMAdapterImpl()
    
    # Read local image and convert to base64
    # For this example, we'll use a minimal test image
    # In real usage, you would read from a file:
    # with open("image.jpg", "rb") as f:
    #     image_bytes = f.read()
    #     base64_string = base64.b64encode(image_bytes).decode('utf-8')
    
    # Minimal 1x1 red pixel PNG for testing
    base64_string = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    
    result = await adapter.call_multimodal(
        prompt="What color is this pixel?",
        image_data=base64_string,
        image_type="base64",
        provider="dashscope",
        model="qwen-vl-plus",
        mime_type="image/png",
    )
    
    print(f"Provider: {result.provider}")
    print(f"Model: {result.model}")
    print(f"Response: {result.text}")
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
    print(f"Cost: ${result.cost_usd:.6f}")


async def example_multiple_images():
    """Example: Using multiple images with mixed formats."""
    print("\n" + "="*60)
    print("Example 3: Multiple Images (Mixed Formats)")
    print("="*60)
    
    adapter = LLMAdapterImpl()
    
    # Mix of URL and Base64 images
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/320px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    base64_image = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    
    result = await adapter.call_multimodal_with_multiple_images(
        prompt="Compare these two images. What are the differences?",
        images=[
            (image_url, "url"),
            (base64_image, "base64"),
        ],
        provider="openrouter",
        model="openai/gpt-4o-mini",
        mime_type="image/png",
    )
    
    print(f"Provider: {result.provider}")
    print(f"Model: {result.model}")
    print(f"Response: {result.text}")
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
    print(f"Cost: ${result.cost_usd:.6f}")


async def example_auto_provider_selection():
    """Example: Automatic provider selection for multimodal."""
    print("\n" + "="*60)
    print("Example 4: Automatic Provider Selection")
    print("="*60)
    
    adapter = LLMAdapterImpl()
    
    # Don't specify provider/model - let adapter choose
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/320px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    
    result = await adapter.call_multimodal(
        prompt="What's the main subject of this image?",
        image_data=image_url,
        image_type="url",
        # No provider/model specified - uses first available multimodal provider
    )
    
    print(f"Auto-selected Provider: {result.provider}")
    print(f"Auto-selected Model: {result.model}")
    print(f"Response: {result.text}")
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
    print(f"Cost: ${result.cost_usd:.6f}")


async def example_local_image_file():
    """Example: Loading and using a local image file."""
    print("\n" + "="*60)
    print("Example 5: Local Image File")
    print("="*60)
    
    adapter = LLMAdapterImpl()
    
    # Example of reading a local image file
    # Uncomment and modify path for real usage:
    # image_path = Path("path/to/your/image.jpg")
    # if image_path.exists():
    #     with open(image_path, "rb") as f:
    #         image_bytes = f.read()
    #         base64_string = base64.b64encode(image_bytes).decode('utf-8')
    #     
    #     result = await adapter.call_multimodal(
    #         prompt="Analyze this image",
    #         image_data=base64_string,
    #         image_type="base64",
    #         provider="dashscope",
    #         model="qwen-vl-plus",
    #         mime_type="image/jpeg",
    #     )
    #     
    #     print(f"Response: {result.text}")
    
    print("(Skipped - no local image file provided)")
    print("To use this example, uncomment the code and provide an image path")


async def main():
    """Run all examples."""
    print("="*60)
    print("Multimodal Image Formats Usage Examples")
    print("="*60)
    
    try:
        # Example 1: URL format
        await example_url_format()
        
        # Example 2: Base64 format
        await example_base64_format()
        
        # Example 3: Multiple images
        await example_multiple_images()
        
        # Example 4: Auto provider selection
        await example_auto_provider_selection()
        
        # Example 5: Local image file
        await example_local_image_file()
        
        print("\n" + "="*60)
        print("All examples completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
