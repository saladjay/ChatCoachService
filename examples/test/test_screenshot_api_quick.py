"""Quick test of screenshot API with a real image."""
import requests
import json

def test_screenshot_api():
    """Test the screenshot API endpoint."""
    url = "http://localhost:8000/api/v1/chat_screenshot/parse"
    
    # Use a publicly accessible test image
    # Note: Replace with actual image URL for real testing
    data = {
        "image_url": "https://raw.githubusercontent.com/python-pillow/Pillow/main/Tests/images/hopper.png",
        "session_id": "test-quick-123"
    }
    
    print("Testing screenshot API...")
    print(f"URL: {url}")
    print(f"Request: {json.dumps(data, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=data, timeout=60)
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_screenshot_api()
