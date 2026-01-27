"""Simple screenshot API test using httpx."""
import asyncio
import httpx
import json

async def test_screenshot_api():
    """Test screenshot API with a public image."""
    url = "http://localhost:8000/api/v1/chat_screenshot/parse"
    
    # Use a publicly accessible test image
    data = {
        "image_url": "https://raw.githubusercontent.com/python-pillow/Pillow/main/Tests/images/hopper.png",
        "session_id": "test-simple-123"
    }
    
    print("=" * 80)
    print("Testing Screenshot API")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"Request: {json.dumps(data, indent=2)}")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print("Sending request...")
            response = await client.post(url, json=data)
            print(f"Status Code: {response.status_code}")
            print()
            print("Response:")
            print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_screenshot_api())
