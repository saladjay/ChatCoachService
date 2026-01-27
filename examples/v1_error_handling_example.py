#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ChatCoach API v1 - Error Handling Example

This example demonstrates comprehensive error handling when using the ChatCoach API v1.
It shows how to handle various error scenarios gracefully.

Usage:
    # Test all error scenarios
    python examples/v1_error_handling_example.py
    
    # Test specific error scenario
    python examples/v1_error_handling_example.py --scenario model_unavailable
    
    # Use custom server
    python examples/v1_error_handling_example.py --server http://localhost:8000

Requirements:
    pip install httpx
"""

import argparse
import asyncio
import sys
from enum import Enum
from typing import Optional

import httpx


class ErrorScenario(str, Enum):
    """Error scenarios to test"""
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID_APP_NAME = "invalid_app_name"
    INVALID_LANGUAGE = "invalid_language"
    INVALID_CONF_THRESHOLD = "invalid_conf_threshold"
    EMPTY_URLS = "empty_urls"
    EMPTY_USER_ID = "empty_user_id"
    INVALID_IMAGE_URL = "invalid_image_url"
    NETWORK_ERROR = "network_error"
    ALL = "all"


class ChatCoachV1ErrorHandler:
    """Client with comprehensive error handling"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1/ChatCoach"
    
    async def safe_health_check(self) -> tuple[bool, Optional[dict], Optional[str]]:
        """Safely check API health with error handling
        
        Returns:
            Tuple of (success, health_data, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.api_base}/health")
                
                if response.status_code == 401:
                    # Model unavailable
                    error_data = response.json()
                    return False, None, f"Model Unavailable: {error_data.get('detail')}"
                
                response.raise_for_status()
                return True, response.json(), None
                
        except httpx.ConnectError as e:
            return False, None, f"Connection Error: Cannot connect to {self.base_url}. Is the server running?"
        except httpx.TimeoutException as e:
            return False, None, f"Timeout Error: Server took too long to respond"
        except httpx.HTTPStatusError as e:
            return False, None, f"HTTP Error {e.response.status_code}: {e.response.text}"
        except Exception as e:
            return False, None, f"Unexpected Error: {str(e)}"
    
    async def safe_predict(
        self,
        urls: list[str],
        app_name: str,
        language: str,
        user_id: str,
        request_id: Optional[str] = None,
        conf_threshold: Optional[float] = None,
        reply: bool = False,
    ) -> tuple[bool, Optional[dict], Optional[str]]:
        """Safely call predict endpoint with error handling
        
        Returns:
            Tuple of (success, result_data, error_message)
        """
        try:
            request_data = {
                "urls": urls,
                "app_name": app_name,
                "language": language,
                "user_id": user_id,
                "reply": reply,
            }
            
            if request_id:
                request_data["request_id"] = request_id
            
            if conf_threshold is not None:
                request_data["conf_threshold"] = conf_threshold
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_base}/predict",
                    json=request_data,
                )
                
                # Handle different status codes
                if response.status_code == 401:
                    # Model unavailable
                    error_data = response.json()
                    return False, None, f"Model Unavailable: {error_data.get('detail')}"
                
                elif response.status_code == 400:
                    # Bad request (validation or image load error)
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            if "detail" in error_data:
                                return False, None, f"Bad Request: {error_data['detail']}"
                            elif not error_data.get("success"):
                                return False, error_data, f"Request Failed: {error_data.get('message')}"
                    except:
                        pass
                    return False, None, f"Bad Request: {response.text}"
                
                elif response.status_code == 422:
                    # Validation error
                    error_data = response.json()
                    if "detail" in error_data:
                        errors = error_data["detail"]
                        if isinstance(errors, list):
                            error_msgs = [f"{e.get('loc', [])} - {e.get('msg', '')}" for e in errors]
                            return False, None, f"Validation Error: {'; '.join(error_msgs)}"
                    return False, None, f"Validation Error: {response.text}"
                
                elif response.status_code == 500:
                    # Server error
                    try:
                        error_data = response.json()
                        if not error_data.get("success"):
                            return False, error_data, f"Server Error: {error_data.get('message')}"
                    except:
                        pass
                    return False, None, f"Server Error: {response.text}"
                
                response.raise_for_status()
                result = response.json()
                
                # Check if the response indicates success
                if not result.get("success"):
                    return False, result, f"Request Failed: {result.get('message')}"
                
                return True, result, None
                
        except httpx.ConnectError as e:
            return False, None, f"Connection Error: Cannot connect to {self.base_url}"
        except httpx.TimeoutException as e:
            return False, None, f"Timeout Error: Request took too long"
        except httpx.HTTPStatusError as e:
            return False, None, f"HTTP Error {e.response.status_code}: {e.response.text}"
        except Exception as e:
            return False, None, f"Unexpected Error: {str(e)}"
    
    def print_error(self, scenario: str, error_message: str):
        """Print error information
        
        Args:
            scenario: Error scenario name
            error_message: Error message
        """
        print(f"\n❌ {scenario}")
        print(f"   Error: {error_message}")
    
    def print_success(self, scenario: str, message: str = "Request successful"):
        """Print success information
        
        Args:
            scenario: Scenario name
            message: Success message
        """
        print(f"\n✅ {scenario}")
        print(f"   {message}")


async def test_model_unavailable(handler: ChatCoachV1ErrorHandler):
    """Test model unavailable error (401)"""
    print("\n" + "=" * 80)
    print("Test 1: Model Unavailable (401)")
    print("=" * 80)
    print("This error occurs when screenshotanalysis models are not loaded.")
    
    success, health, error = await handler.safe_health_check()
    if not success and "Model Unavailable" in str(error):
        handler.print_error("Model Unavailable", error)
        print("\n💡 Solution:")
        print("   - Check server logs for model loading errors")
        print("   - Ensure screenshotanalysis library is installed")
        print("   - Restart the service")
    elif success:
        handler.print_success("Health Check", "Models are available")
    else:
        handler.print_error("Health Check", error)


async def test_invalid_app_name(handler: ChatCoachV1ErrorHandler):
    """Test invalid app_name validation (400)"""
    print("\n" + "=" * 80)
    print("Test 2: Invalid App Name (400)")
    print("=" * 80)
    print("This error occurs when app_name is not in the supported list.")
    
    success, result, error = await handler.safe_predict(
        urls=["https://example.com/test.jpg"],
        app_name="invalid_app",  # Invalid app name
        language="en",
        user_id="test_user",
    )
    
    if not success:
        handler.print_error("Invalid App Name", error)
        print("\n💡 Solution:")
        print("   - Use a supported app name: whatsapp, telegram, discord, etc.")
        print("   - Check config.yaml for the full list of supported apps")
    else:
        handler.print_success("App Name Validation", "Validation passed (unexpected)")


async def test_invalid_language(handler: ChatCoachV1ErrorHandler):
    """Test invalid language validation (400)"""
    print("\n" + "=" * 80)
    print("Test 3: Invalid Language (400)")
    print("=" * 80)
    print("This error occurs when language is not in the supported list.")
    
    success, result, error = await handler.safe_predict(
        urls=["https://example.com/test.jpg"],
        app_name="whatsapp",
        language="invalid_lang",  # Invalid language
        user_id="test_user",
    )
    
    if not success:
        handler.print_error("Invalid Language", error)
        print("\n💡 Solution:")
        print("   - Use a supported language code: en, zh, es, etc.")
        print("   - Check config.yaml for the full list of supported languages")
    else:
        handler.print_success("Language Validation", "Validation passed (unexpected)")


async def test_invalid_conf_threshold(handler: ChatCoachV1ErrorHandler):
    """Test invalid conf_threshold validation (422)"""
    print("\n" + "=" * 80)
    print("Test 4: Invalid Confidence Threshold (422)")
    print("=" * 80)
    print("This error occurs when conf_threshold is outside [0.0, 1.0] range.")
    
    success, result, error = await handler.safe_predict(
        urls=["https://example.com/test.jpg"],
        app_name="whatsapp",
        language="en",
        user_id="test_user",
        conf_threshold=1.5,  # Invalid threshold
    )
    
    if not success:
        handler.print_error("Invalid Confidence Threshold", error)
        print("\n💡 Solution:")
        print("   - Use a value between 0.0 and 1.0")
        print("   - Lower values = more detections (more false positives)")
        print("   - Higher values = fewer detections (fewer false positives)")
    else:
        handler.print_success("Threshold Validation", "Validation passed (unexpected)")


async def test_empty_urls(handler: ChatCoachV1ErrorHandler):
    """Test empty URLs list validation (422)"""
    print("\n" + "=" * 80)
    print("Test 5: Empty URLs List (422)")
    print("=" * 80)
    print("This error occurs when the urls list is empty.")
    
    success, result, error = await handler.safe_predict(
        urls=[],  # Empty list
        app_name="whatsapp",
        language="en",
        user_id="test_user",
    )
    
    if not success:
        handler.print_error("Empty URLs List", error)
        print("\n💡 Solution:")
        print("   - Provide at least one image URL")
        print("   - Ensure URLs are valid and accessible")
    else:
        handler.print_success("URLs Validation", "Validation passed (unexpected)")


async def test_empty_user_id(handler: ChatCoachV1ErrorHandler):
    """Test empty user_id validation (422)"""
    print("\n" + "=" * 80)
    print("Test 6: Empty User ID (422)")
    print("=" * 80)
    print("This error occurs when user_id is empty.")
    
    success, result, error = await handler.safe_predict(
        urls=["https://example.com/test.jpg"],
        app_name="whatsapp",
        language="en",
        user_id="",  # Empty user_id
    )
    
    if not success:
        handler.print_error("Empty User ID", error)
        print("\n💡 Solution:")
        print("   - Provide a non-empty user identifier")
        print("   - Use a unique ID for each user")
    else:
        handler.print_success("User ID Validation", "Validation passed (unexpected)")


async def test_invalid_image_url(handler: ChatCoachV1ErrorHandler):
    """Test invalid image URL (400)"""
    print("\n" + "=" * 80)
    print("Test 7: Invalid Image URL (400)")
    print("=" * 80)
    print("This error occurs when the image cannot be loaded from the URL.")
    
    success, result, error = await handler.safe_predict(
        urls=["https://invalid-domain-that-does-not-exist.com/image.jpg"],
        app_name="whatsapp",
        language="en",
        user_id="test_user",
    )
    
    if not success:
        handler.print_error("Invalid Image URL", error or "Image load failed")
        print("\n💡 Solution:")
        print("   - Verify the image URL is accessible")
        print("   - Check network connectivity")
        print("   - Ensure the URL points to a valid image file")
    else:
        handler.print_success("Image Loading", "Image loaded successfully (unexpected)")


async def test_network_error(handler: ChatCoachV1ErrorHandler):
    """Test network connection error"""
    print("\n" + "=" * 80)
    print("Test 8: Network Connection Error")
    print("=" * 80)
    print("This error occurs when the server is unreachable.")
    
    # Create handler with invalid server URL
    invalid_handler = ChatCoachV1ErrorHandler(base_url="http://localhost:9999")
    
    success, health, error = await invalid_handler.safe_health_check()
    
    if not success:
        handler.print_error("Network Connection", error)
        print("\n💡 Solution:")
        print("   - Verify the server URL is correct")
        print("   - Ensure the server is running")
        print("   - Check firewall and network settings")
    else:
        handler.print_success("Network Connection", "Connected successfully (unexpected)")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="ChatCoach API v1 - Error Handling Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--scenario",
        type=ErrorScenario,
        choices=list(ErrorScenario),
        default=ErrorScenario.ALL,
        help="Specific error scenario to test (default: all)"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🚀 ChatCoach API v1 - Error Handling Examples")
    print("=" * 80)
    print(f"Server: {args.server}")
    print(f"Scenario: {args.scenario.value}")
    print("=" * 80)
    
    handler = ChatCoachV1ErrorHandler(base_url=args.server)
    
    # Run tests based on scenario
    if args.scenario == ErrorScenario.ALL:
        await test_model_unavailable(handler)
        await test_invalid_app_name(handler)
        await test_invalid_language(handler)
        await test_invalid_conf_threshold(handler)
        await test_empty_urls(handler)
        await test_empty_user_id(handler)
        await test_invalid_image_url(handler)
        await test_network_error(handler)
    elif args.scenario == ErrorScenario.MODEL_UNAVAILABLE:
        await test_model_unavailable(handler)
    elif args.scenario == ErrorScenario.INVALID_APP_NAME:
        await test_invalid_app_name(handler)
    elif args.scenario == ErrorScenario.INVALID_LANGUAGE:
        await test_invalid_language(handler)
    elif args.scenario == ErrorScenario.INVALID_CONF_THRESHOLD:
        await test_invalid_conf_threshold(handler)
    elif args.scenario == ErrorScenario.EMPTY_URLS:
        await test_empty_urls(handler)
    elif args.scenario == ErrorScenario.EMPTY_USER_ID:
        await test_empty_user_id(handler)
    elif args.scenario == ErrorScenario.INVALID_IMAGE_URL:
        await test_invalid_image_url(handler)
    elif args.scenario == ErrorScenario.NETWORK_ERROR:
        await test_network_error(handler)
    
    print("\n" + "=" * 80)
    print("✅ Error handling tests complete!")
    print("=" * 80)
    print("\n💡 Key Takeaways:")
    print("   1. Always check the 'success' field in responses")
    print("   2. Implement retry logic for transient errors (500)")
    print("   3. Validate inputs before sending requests")
    print("   4. Log request_id for debugging and support")
    print("   5. Handle network errors gracefully")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
