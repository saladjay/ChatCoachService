#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ChatCoach API v1 - Reply Generation Example

This example demonstrates how to use the ChatCoach API v1 to analyze chat screenshots
and generate intelligent reply suggestions.

Usage:
    # Basic reply generation
    python examples/v1_reply_generation_example.py
    
    # With custom configuration
    python examples/v1_reply_generation_example.py --server http://localhost:8000 --app telegram --language zh
    
    # Analyze multiple screenshots and generate replies
    python examples/v1_reply_generation_example.py --urls url1 url2 url3

Requirements:
    pip install httpx
"""

import argparse
import asyncio
import json
import sys
from typing import Optional

import httpx


class ChatCoachV1Client:
    """Client for ChatCoach API v1 with reply generation"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1/ChatCoach"
    
    async def check_health(self) -> dict:
        """Check API health status
        
        Returns:
            Health check response
            
        Raises:
            httpx.HTTPError: If the request fails
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.api_base}/health")
            response.raise_for_status()
            return response.json()
    
    async def analyze_and_generate_replies(
        self,
        urls: list[str],
        app_name: str,
        language: str,
        user_id: str,
        request_id: Optional[str] = None,
        conf_threshold: Optional[float] = None,
    ) -> dict:
        """Analyze screenshots and generate reply suggestions
        
        Args:
            urls: List of image URLs to analyze
            app_name: Chat application type (e.g., "whatsapp", "telegram")
            language: Conversation language (e.g., "en", "zh")
            user_id: User identifier
            request_id: Optional request tracking ID
            conf_threshold: Detection confidence threshold (0.0-1.0)
            
        Returns:
            Analysis results with suggested replies
            
        Raises:
            httpx.HTTPError: If the request fails
        """
        request_data = {
            "urls": urls,
            "app_name": app_name,
            "language": language,
            "user_id": user_id,
            "reply": True,  # Request reply generation
        }
        
        if request_id:
            request_data["request_id"] = request_id
        
        if conf_threshold is not None:
            request_data["conf_threshold"] = conf_threshold
        
        async with httpx.AsyncClient(timeout=180.0) as client:  # Longer timeout for reply generation
            response = await client.post(
                f"{self.api_base}/predict",
                json=request_data,
            )
            response.raise_for_status()
            return response.json()
    
    def print_health_status(self, health: dict):
        """Print health check results
        
        Args:
            health: Health check response
        """
        print("\n" + "=" * 80)
        print("🏥 API Health Status")
        print("=" * 80)
        print(f"Status: {health['status']}")
        print(f"Version: {health['version']}")
        print(f"Timestamp: {health['timestamp']}")
        print(f"\n📦 Models:")
        for model_name, available in health.get('models', {}).items():
            status_icon = "✅" if available else "❌"
            print(f"  {status_icon} {model_name}: {'Available' if available else 'Unavailable'}")
        print("=" * 80)
    
    def print_results_with_replies(self, results: dict):
        """Print screenshot analysis results with reply suggestions
        
        Args:
            results: Analysis response with replies
        """
        print("\n" + "=" * 80)
        print("📊 Screenshot Analysis & Reply Generation Results")
        print("=" * 80)
        
        if not results.get("success"):
            print(f"❌ Error: {results.get('message')}")
            return
        
        print(f"✅ Success: {results.get('message')}")
        print(f"User ID: {results.get('user_id')}")
        if results.get('request_id'):
            print(f"Request ID: {results.get('request_id')}")
        
        # Print screenshot analysis results
        for idx, image_result in enumerate(results.get('results', []), 1):
            print(f"\n📷 Image {idx}: {image_result['url']}")
            print(f"   Found {len(image_result['dialogs'])} dialog items")
            
            for dialog_idx, dialog in enumerate(image_result['dialogs'], 1):
                speaker_icon = "👤" if dialog['from_user'] else "👥"
                print(f"\n   {dialog_idx}. {speaker_icon} {dialog['speaker']}")
                print(f"      Text: {dialog['text']}")
                print(f"      From User: {dialog['from_user']}")
        
        # Print suggested replies
        suggested_replies = results.get('suggested_replies')
        if suggested_replies:
            print("\n" + "-" * 80)
            print("💬 Suggested Replies")
            print("-" * 80)
            for idx, reply in enumerate(suggested_replies, 1):
                print(f"\n{idx}. {reply}")
            print("-" * 80)
        else:
            print("\n⚠️  No suggested replies were generated")
            print("   This may happen if:")
            print("   - The Orchestrator service is unavailable")
            print("   - No dialogs were extracted from the screenshots")
            print("   - Reply generation failed")
        
        print("\n" + "=" * 80)
    
    def extract_conversation_summary(self, results: dict) -> dict:
        """Extract a summary of the conversation
        
        Args:
            results: Analysis response
            
        Returns:
            Conversation summary
        """
        summary = {
            "total_messages": 0,
            "user_messages": 0,
            "other_messages": 0,
            "conversation": [],
        }
        
        for image_result in results.get('results', []):
            for dialog in image_result['dialogs']:
                summary["total_messages"] += 1
                if dialog['from_user']:
                    summary["user_messages"] += 1
                else:
                    summary["other_messages"] += 1
                
                summary["conversation"].append({
                    "speaker": dialog['speaker'],
                    "text": dialog['text'],
                    "from_user": dialog['from_user'],
                })
        
        return summary


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="ChatCoach API v1 - Reply Generation Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--urls",
        nargs="+",
        default=["https://example.com/screenshot1.jpg"],
        help="Image URLs to analyze"
    )
    
    parser.add_argument(
        "--app",
        default="whatsapp",
        help="Chat application type (default: whatsapp)"
    )
    
    parser.add_argument(
        "--language",
        default="en",
        help="Conversation language (default: en)"
    )
    
    parser.add_argument(
        "--user-id",
        default="demo_user",
        help="User identifier (default: demo_user)"
    )
    
    parser.add_argument(
        "--request-id",
        help="Optional request tracking ID"
    )
    
    parser.add_argument(
        "--conf-threshold",
        type=float,
        help="Detection confidence threshold (0.0-1.0)"
    )
    
    parser.add_argument(
        "--output",
        help="Save results to JSON file"
    )
    
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip health check before analysis"
    )
    
    parser.add_argument(
        "--show-summary",
        action="store_true",
        help="Show conversation summary"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🚀 ChatCoach API v1 - Reply Generation")
    print("=" * 80)
    print(f"Server: {args.server}")
    print(f"URLs: {len(args.urls)} image(s)")
    print(f"App: {args.app}")
    print(f"Language: {args.language}")
    print(f"User ID: {args.user_id}")
    if args.conf_threshold:
        print(f"Confidence Threshold: {args.conf_threshold}")
    print("=" * 80)
    
    try:
        # Create client
        client = ChatCoachV1Client(base_url=args.server)
        
        # Step 1: Health check
        if not args.skip_health_check:
            print("\n🔍 Checking API health...")
            health = await client.check_health()
            client.print_health_status(health)
            
            if health['status'] != 'healthy':
                print("\n⚠️  Warning: API is not healthy, but continuing anyway...")
        
        # Step 2: Analyze screenshots and generate replies
        print(f"\n🔍 Analyzing {len(args.urls)} screenshot(s) and generating replies...")
        print("   (This may take a few seconds...)")
        results = await client.analyze_and_generate_replies(
            urls=args.urls,
            app_name=args.app,
            language=args.language,
            user_id=args.user_id,
            request_id=args.request_id,
            conf_threshold=args.conf_threshold,
        )
        
        # Print results
        client.print_results_with_replies(results)
        
        # Show conversation summary if requested
        if args.show_summary and results.get("success"):
            summary = client.extract_conversation_summary(results)
            print("\n" + "=" * 80)
            print("📈 Conversation Summary")
            print("=" * 80)
            print(f"Total Messages: {summary['total_messages']}")
            print(f"User Messages: {summary['user_messages']}")
            print(f"Other Messages: {summary['other_messages']}")
            print("=" * 80)
        
        # Save to file if requested
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Results saved to: {args.output}")
        
        print("\n✅ Reply generation complete!")
        
    except httpx.HTTPStatusError as e:
        print(f"\n❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"\n❌ Network Error: {e}")
        print(f"   Please ensure the server at {args.server} is running")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
