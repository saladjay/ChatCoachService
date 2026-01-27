"""Quick test to see the full OpenRouter response."""
import asyncio
import httpx
import json

async def test():
    # Start local file server
    import threading
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import os
    
    os.chdir("D:/project/chatlayoutdet_ws/test_images")
    server = HTTPServer(('127.0.0.1', 65500), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    url = "http://localhost:8000/api/v1/chat_screenshot/parse"
    data = {
        "image_url": "http://127.0.0.1:65500/test_discord_2.png",
        "session_id": "test-final"
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=data)
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    server.shutdown()

if __name__ == "__main__":
    asyncio.run(test())
