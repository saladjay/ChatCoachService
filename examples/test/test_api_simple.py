"""Simple test script to verify screenshot API is working."""
import httpx
import asyncio

async def test_api():
    """Test the screenshot API endpoint."""
    url = "http://localhost:8000/api/v1/chat_screenshot/parse"
    
    # Test data
    data = {
        "image_url": "https://example.com/test.png",
        "session_id": "test-123"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
