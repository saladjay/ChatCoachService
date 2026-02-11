"""
Simple usage examples for multimodal LLM calls.

This file demonstrates practical use cases for the multimodal implementation.
"""

import asyncio
import base64
from pathlib import Path

from app.services.llm_adapter import LLMAdapterImpl


async def example_1_analyze_screenshot():
    """Example: Analyze a screenshot."""
    print("\n=== Example 1: Analyze Screenshot ===")
    
    adapter = LLMAdapterImpl()
    
    # Load screenshot
    screenshot_path = Path("screenshot.png")
    if screenshot_path.exists():
        with open(screenshot_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        result = await adapter.call_multimodal(
            prompt="Analyze this screenshot and describe what you see. Include any text, UI elements, and overall layout.",
            image_data=image_base64,
            image_type="base64",
            provider="dashscope",
            model="qwen-vl-plus",
            mime_type="image/png"
        )
        
        print(f"Analysis: {result.text}")
        print(f"Cost: ${result.cost_usd:.6f}")
    else:
        print("Screenshot file not found")


async def example_2_extract_text_from_image():
    """Example: Extract text from an image (OCR)."""
    print("\n=== Example 2: Extract Text (OCR) ===")
    
    adapter = LLMAdapterImpl()
    
    # Load image with text
    image_path = Path("document.jpg")
    if image_path.exists():
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        result = await adapter.call_multimodal(
            prompt="Extract all text from this image. Preserve the formatting and structure as much as possible.",
            image_data=image_base64,
            image_type="base64",
            provider="openrouter",
            model="openai/gpt-4o",
            mime_type="image/jpeg"
        )
        
        print(f"Extracted text:\n{result.text}")
        print(f"Tokens used: {result.input_tokens + result.output_tokens}")
    else:
        print("Document image not found")


async def example_3_compare_images():
    """Example: Compare multiple images."""
    print("\n=== Example 3: Compare Images ===")
    
    adapter = LLMAdapterImpl()
    
    # Load two images to compare
    image1_path = Path("before.jpg")
    image2_path = Path("after.jpg")
    
    if image1_path.exists() and image2_path.exists():
        with open(image1_path, "rb") as f:
            image1_base64 = base64.b64encode(f.read()).decode()
        
        with open(image2_path, "rb") as f:
            image2_base64 = base64.b64encode(f.read()).decode()
        
        result = await adapter.call_multimodal_with_multiple_images(
            prompt="Compare these two images. What are the main differences? List at least 5 specific changes.",
            images=[
                (image1_base64, "base64"),
                (image2_base64, "base64"),
            ],
            provider="openrouter",
            model="openai/gpt-4o",
            mime_type="image/jpeg"
        )
        
        print(f"Comparison:\n{result.text}")
        print(f"Cost: ${result.cost_usd:.6f}")
    else:
        print("Comparison images not found")


async def example_4_describe_product():
    """Example: Generate product description from image."""
    print("\n=== Example 4: Product Description ===")
    
    adapter = LLMAdapterImpl()
    
    # Load product image
    product_image_url = "https://example.com/product.jpg"
    
    result = await adapter.call_multimodal(
        prompt="""Analyze this product image and generate:
1. A detailed product description (2-3 sentences)
2. Key features (bullet points)
3. Suggested product category
4. Recommended target audience""",
        image_data=product_image_url,
        image_type="url",
        provider="dashscope",
        model="qwen-vl-plus"
    )
    
    print(f"Product Analysis:\n{result.text}")


async def example_5_ui_testing():
    """Example: UI/UX analysis for testing."""
    print("\n=== Example 5: UI/UX Analysis ===")
    
    adapter = LLMAdapterImpl()
    
    # Load UI screenshot
    ui_path = Path("ui_screenshot.png")
    if ui_path.exists():
        with open(ui_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        result = await adapter.call_multimodal(
            prompt="""Analyze this UI screenshot for:
1. Accessibility issues (contrast, text size, etc.)
2. Layout problems (alignment, spacing, etc.)
3. Usability concerns
4. Suggestions for improvement""",
            image_data=image_base64,
            image_type="base64",
            mime_type="image/png"
        )
        
        print(f"UI Analysis:\n{result.text}")
        print(f"Tokens: {result.input_tokens + result.output_tokens}")
    else:
        print("UI screenshot not found")


async def example_6_auto_provider():
    """Example: Let the adapter choose the best provider."""
    print("\n=== Example 6: Auto Provider Selection ===")
    
    adapter = LLMAdapterImpl()
    
    # Simple image analysis without specifying provider
    sample_image = "https://example.com/sample.jpg"
    
    result = await adapter.call_multimodal(
        prompt="What objects can you identify in this image?",
        image_data=sample_image,
        image_type="url"
    )
    
    print(f"Auto-selected: {result.provider} / {result.model}")
    print(f"Response: {result.text}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Multimodal LLM Usage Examples")
    print("=" * 60)
    
    # Run examples
    await example_1_analyze_screenshot()
    await example_2_extract_text_from_image()
    await example_3_compare_images()
    await example_4_describe_product()
    await example_5_ui_testing()
    await example_6_auto_provider()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
