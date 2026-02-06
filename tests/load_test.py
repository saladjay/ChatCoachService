#!/usr/bin/env python3
"""
Load testing script for ChatCoach API.

This script tests the maximum concurrent requests the API can handle
and measures performance metrics like response time, throughput, and error rate.

Usage:
    python tests/load_test.py --url http://localhost:8000 --concurrent 10 --requests 100
"""

import asyncio
import time
import argparse
import json
import hashlib
from typing import List, Dict, Any
from dataclasses import dataclass, field
import statistics

import httpx

# Load environment variables from .env file
from pathlib import Path
import sys

# Add project root to path and load .env
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load .env file before importing app modules
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✓ Loaded environment variables from {env_file}")
    else:
        print(f"⚠ .env file not found at {env_file}")
except ImportError:
    print("⚠ python-dotenv not installed, environment variables from .env will not be loaded")
except Exception as e:
    print(f"⚠ Error loading .env file: {e}")


@dataclass
class TestResult:
    """Result of a single request."""
    success: bool
    status_code: int
    response_time: float  # seconds
    error: str = ""
    response_size: int = 0


@dataclass
class LoadTestStats:
    """Statistics from load test."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    response_times: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=dict)
    status_codes: Dict[int, int] = field(default_factory=dict)
    
    def add_result(self, result: TestResult):
        """Add a test result to statistics."""
        self.total_requests += 1
        if result.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.errors[result.error] = self.errors.get(result.error, 0) + 1
        
        self.response_times.append(result.response_time)
        self.status_codes[result.status_code] = self.status_codes.get(result.status_code, 0) + 1
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("LOAD TEST SUMMARY")
        print("=" * 80)
        
        # Basic stats
        print(f"\nTotal Requests:      {self.total_requests}")
        print(f"Successful:          {self.successful_requests} ({self.successful_requests/self.total_requests*100:.1f}%)")
        print(f"Failed:              {self.failed_requests} ({self.failed_requests/self.total_requests*100:.1f}%)")
        print(f"Total Time:          {self.total_time:.2f}s")
        print(f"Requests/Second:     {self.total_requests/self.total_time:.2f}")
        
        # Response time stats
        if self.response_times:
            print(f"\nResponse Time Stats:")
            print(f"  Min:               {min(self.response_times):.3f}s")
            print(f"  Max:               {max(self.response_times):.3f}s")
            print(f"  Mean:              {statistics.mean(self.response_times):.3f}s")
            print(f"  Median:            {statistics.median(self.response_times):.3f}s")
            if len(self.response_times) > 1:
                print(f"  Std Dev:           {statistics.stdev(self.response_times):.3f}s")
            
            # Percentiles
            sorted_times = sorted(self.response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p90 = sorted_times[int(len(sorted_times) * 0.90)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            
            print(f"\nPercentiles:")
            print(f"  P50:               {p50:.3f}s")
            print(f"  P90:               {p90:.3f}s")
            print(f"  P95:               {p95:.3f}s")
            print(f"  P99:               {p99:.3f}s")
        
        # Status codes
        print(f"\nStatus Codes:")
        for code, count in sorted(self.status_codes.items()):
            print(f"  {code}:               {count} ({count/self.total_requests*100:.1f}%)")
        
        # Errors
        if self.errors:
            print(f"\nErrors:")
            for error, count in sorted(self.errors.items(), key=lambda x: x[1], reverse=True):
                print(f"  {error[:60]:60} {count}")
        
        print("=" * 80)


class LoadTester:
    """Load tester for ChatCoach API."""
    
    def __init__(
        self, 
        base_url: str, 
        timeout: float = 60.0,
        image_url: str | None = None,
        disable_cache: bool = False,
        sign_secret: str = "",
    ):
        """Initialize load tester.
        
        Args:
            base_url: Base URL of the API
            timeout: Request timeout in seconds
            image_url: Optional custom image URL to test
            disable_cache: If True, bypass cache by using unique session IDs
            sign_secret: Secret for generating sign (default from config.yaml)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.image_url = image_url
        self.disable_cache = disable_cache
        self.sign_secret = sign_secret
        self.stats = LoadTestStats()
        # Use timestamp to ensure unique counters across test runs
        self._request_counter = int(time.time() * 1000)  # milliseconds since epoch
    
    async def make_request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        method: str = "POST",
        payload: Dict[str, Any] = None,
    ) -> TestResult:
        """Make a single request and measure performance.
        
        Args:
            client: HTTP client
            endpoint: API endpoint
            method: HTTP method
            payload: Request payload
            
        Returns:
            TestResult with metrics
        """
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method == "POST":
                # Generate unique payload if cache is disabled
                if self.disable_cache and payload:
                    payload = create_test_payload(
                        image_url=self.image_url,
                        disable_cache=True,
                        request_index=self._request_counter,
                        sign_secret=self.sign_secret,
                    )
                    self._request_counter += 1
                
                response = await client.post(url, json=payload)
            elif method == "GET":
                response = await client.get(url)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response_time = time.time() - start_time
            
            # Extract error details for non-200 responses
            error_msg = ""
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                        # Try to get detailed error message
                        error_msg = error_data.get("detail", f"HTTP {response.status_code}")
                        # If detail is a list (validation errors), format it
                        if isinstance(error_msg, list):
                            error_parts = []
                            for e in error_msg[:3]:
                                loc = e.get('loc', [])
                                field = loc[-1] if loc else 'field'
                                msg = e.get('msg', '')
                                error_parts.append(f"{field}: {msg}")
                            error_msg = "; ".join(error_parts)
                    else:
                        error_msg = f"HTTP {response.status_code}"
                except Exception:
                    error_msg = f"HTTP {response.status_code}"
            
            return TestResult(
                success=response.status_code == 200,
                status_code=response.status_code,
                response_time=response_time,
                response_size=len(response.content),
                error=error_msg,
            )
            
        except httpx.TimeoutException:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                error="Timeout",
            )
        except Exception as e:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                error=str(e)[:100],
            )
    
    async def run_concurrent_requests(
        self,
        num_requests: int,
        concurrent: int,
        endpoint: str,
        method: str = "POST",
        payload: Dict[str, Any] = None,
    ):
        """Run concurrent requests.
        
        Args:
            num_requests: Total number of requests to make
            concurrent: Number of concurrent requests
            endpoint: API endpoint
            method: HTTP method
            payload: Request payload
        """
        print(f"\nStarting load test:")
        print(f"  Endpoint:          {endpoint}")
        print(f"  Total Requests:    {num_requests}")
        print(f"  Concurrent:        {concurrent}")
        print(f"  Method:            {method}")
        if self.image_url:
            print(f"  Image URL:         {self.image_url}")
        if self.disable_cache:
            print(f"  Cache:             DISABLED (unique session per request)")
        else:
            print(f"  Cache:             ENABLED")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(concurrent)
            
            async def bounded_request():
                async with semaphore:
                    return await self.make_request(client, endpoint, method, payload)
            
            # Start timer
            start_time = time.time()
            
            # Create all tasks
            tasks = [bounded_request() for _ in range(num_requests)]
            
            # Run with progress
            completed = 0
            for coro in asyncio.as_completed(tasks):
                result = await coro
                self.stats.add_result(result)
                completed += 1
                
                # Print progress every 10%
                if completed % max(1, num_requests // 10) == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {completed}/{num_requests} ({completed/num_requests*100:.0f}%) - {rate:.1f} req/s")
            
            # End timer
            self.stats.total_time = time.time() - start_time
    
    async def run_ramp_up_test(
        self,
        max_concurrent: int,
        step: int,
        requests_per_step: int,
        endpoint: str,
        payload: Dict[str, Any] = None,
    ):
        """Run ramp-up test to find maximum concurrency.
        
        Args:
            max_concurrent: Maximum concurrent requests to test
            step: Increment step for concurrency
            requests_per_step: Number of requests per concurrency level
            endpoint: API endpoint
            payload: Request payload
        """
        print(f"\nStarting ramp-up test:")
        print(f"  Endpoint:          {endpoint}")
        print(f"  Max Concurrent:    {max_concurrent}")
        print(f"  Step:              {step}")
        print(f"  Requests/Step:     {requests_per_step}")
        
        results = []
        
        for concurrent in range(step, max_concurrent + 1, step):
            print(f"\n--- Testing with {concurrent} concurrent requests ---")
            
            # Reset stats for this level
            self.stats = LoadTestStats()
            
            # Run test
            await self.run_concurrent_requests(
                num_requests=requests_per_step,
                concurrent=concurrent,
                endpoint=endpoint,
                payload=payload,
            )
            
            # Collect results
            success_rate = self.stats.successful_requests / self.stats.total_requests * 100
            avg_response_time = statistics.mean(self.stats.response_times) if self.stats.response_times else 0
            throughput = self.stats.total_requests / self.stats.total_time
            
            results.append({
                'concurrent': concurrent,
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'throughput': throughput,
                'failed': self.stats.failed_requests,
            })
            
            print(f"\nResults for {concurrent} concurrent:")
            print(f"  Success Rate:      {success_rate:.1f}%")
            print(f"  Avg Response Time: {avg_response_time:.3f}s")
            print(f"  Throughput:        {throughput:.2f} req/s")
            print(f"  Failed Requests:   {self.stats.failed_requests}")
            
            # Stop if success rate drops below 95%
            if success_rate < 95:
                print(f"\n⚠️  Success rate dropped below 95% at {concurrent} concurrent requests")
                print(f"    Recommended max concurrency: {concurrent - step}")
                break
        
        # Print summary table
        print("\n" + "=" * 80)
        print("RAMP-UP TEST SUMMARY")
        print("=" * 80)
        print(f"{'Concurrent':>12} {'Success %':>12} {'Avg Time (s)':>15} {'Throughput':>12} {'Failed':>10}")
        print("-" * 80)
        for r in results:
            print(f"{r['concurrent']:>12} {r['success_rate']:>11.1f}% {r['avg_response_time']:>14.3f}s {r['throughput']:>11.2f} {r['failed']:>10}")
        print("=" * 80)


def generate_sign(session_id: str, secret: str = "") -> str:
    """Generate MD5 sign for request validation.
    
    Args:
        session_id: Session ID
        secret: Sign secret (default from config.yaml)
    
    Returns:
        MD5 hash string
    """
    raw = f"{session_id}ChatCoach{secret}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def create_test_payload(
    image_url: str | None = None,
    disable_cache: bool = False,
    request_index: int = 0,
    sign_secret: str = "",
) -> Dict[str, Any]:
    """Create a test payload for the predict endpoint.
    
    Args:
        image_url: Optional custom image URL to test
        disable_cache: If True, use unique session_id to bypass cache
        request_index: Request index for unique session_id generation
        sign_secret: Secret for generating sign (default from config.yaml)
    
    Returns:
        Test payload dictionary
    """
    # Use provided URL or default
    content_url = image_url or "https://test-r2.zhizitech.org/test_discord_2.png"
    
    # Generate unique session_id if cache is disabled
    session_id = f"load_test_session_{request_index}" if disable_cache else "load_test_session"
    
    # Generate sign
    sign = generate_sign(session_id, sign_secret)
    
    payload = {
        "user_id": "load_test_user",
        "session_id": session_id,
        "request_id": f"load_test_request_{request_index}",
        "language": "en",
        "scene": 1,
        "scene_analysis": True,
        "reply": True,
        "other_properties": "",  # Empty string is valid
        "content": [content_url],
        "sign": sign,
    }
    
    # Add force_regenerate flag if cache is disabled
    if disable_cache:
        payload["force_regenerate"] = True
    
    return payload


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load test ChatCoach API")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--endpoint", default="/api/v1/ChatAnalysis/predict", help="API endpoint to test")
    parser.add_argument("--concurrent", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds")
    parser.add_argument("--ramp-up", action="store_true", help="Run ramp-up test to find max concurrency")
    parser.add_argument("--max-concurrent", type=int, default=50, help="Max concurrent for ramp-up test")
    parser.add_argument("--step", type=int, default=5, help="Step size for ramp-up test")
    parser.add_argument("--health-check", action="store_true", help="Test health check endpoint")
    parser.add_argument("--image-url", type=str, help="Custom image URL to test (default: test_discord_2.png)")
    parser.add_argument("--disable-cache", action="store_true", help="Disable cache by using unique session IDs")
    parser.add_argument("--sign-secret", type=str, default="", 
                        help="Sign secret for request validation (default from config.yaml)")
    
    args = parser.parse_args()
    
    # Print current configuration
    print("\n" + "=" * 80)
    print("LOAD TEST CONFIGURATION")
    print("=" * 80)
    
    # Try to load and print LLM configuration
    try:
        import sys
        from pathlib import Path
        
        # Add project root to path
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from app.core.config import settings
        
        print(f"\nApplication Configuration:")
        print(f"  Default Provider:    {settings.llm.default_provider} (fallback)")
        print(f"  Default Model:       {settings.llm.default_model} (fallback)")
        
        # Try to load actual LLM adapter config
        try:
            llm_adapter_path = project_root / "core" / "llm_adapter"
            if str(llm_adapter_path) not in sys.path:
                sys.path.insert(0, str(llm_adapter_path))
            
            from llm_adapter import ConfigManager
            
            config_path = llm_adapter_path / "config.yaml"
            if config_path.exists():
                config_manager = ConfigManager(str(config_path))
                default_provider = config_manager.get_default_provider()
                provider_config = config_manager.get_provider_config(default_provider)
                
                print(f"\nActual LLM Configuration (from core/llm_adapter/config.yaml):")
                print(f"  Default Provider:    {default_provider}")
                print(f"  Cheap Model:         {provider_config.models.cheap}")
                print(f"  Normal Model:        {provider_config.models.normal}")
                print(f"  Premium Model:       {provider_config.models.premium}")
                print(f"  Multimodal Model:    {provider_config.models.multimodal}")
                
                # Show proxy status
                proxy_url = config_manager.get_proxy_url()
                if proxy_url:
                    print(f"  Proxy:               {proxy_url} (ENABLED)")
                else:
                    print(f"  Proxy:               DISABLED")
            else:
                print(f"\n⚠️  LLM config file not found: {config_path}")
        except Exception as e:
            import os
            print(f"\n⚠️  Could not load LLM adapter config: {e}")
            print(f"    Hint: Make sure .env file exists and contains LLM_DEFAULT_PROVIDER")
            print(f"    Current LLM_DEFAULT_PROVIDER: {os.getenv('LLM_DEFAULT_PROVIDER', 'NOT SET')}")
        
        print(f"\nMerge Step Configuration:")
        print(f"  USE_MERGE_STEP:      {settings.use_merge_step}")
        
        print(f"\nCache Configuration:")
        print(f"  NO_REPLY_CACHE:      {settings.no_reply_cache}")
        print(f"  NO_PERSONA_CACHE:    {settings.no_persona_cache}")
        
        print(f"\nTrace Configuration:")
        print(f"  TRACE_ENABLED:       {settings.trace.enabled}")
        print(f"  TRACE_LEVEL:         {settings.trace.level}")
        print(f"  TRACE_LOG_PROMPT:    {settings.trace.log_llm_prompt}")
        
    except Exception as e:
        print(f"\n⚠️  Could not load configuration: {e}")
        print("   (This is normal if running outside the project directory)")
    
    print("=" * 80)
    
    # Create tester
    tester = LoadTester(
        base_url=args.url,
        timeout=args.timeout,
        image_url=args.image_url,
        disable_cache=args.disable_cache,
        sign_secret=args.sign_secret,
    )
    
    # Health check test
    if args.health_check:
        print("\n=== Health Check Test ===")
        await tester.run_concurrent_requests(
            num_requests=10,
            concurrent=5,
            endpoint="/health",
            method="GET",
        )
        tester.stats.print_summary()
        return
    
    # Create payload
    payload = create_test_payload(
        image_url=args.image_url,
        disable_cache=args.disable_cache,
        request_index=0,
        sign_secret=args.sign_secret,
    )
    
    # Run appropriate test
    if args.ramp_up:
        await tester.run_ramp_up_test(
            max_concurrent=args.max_concurrent,
            step=args.step,
            requests_per_step=args.requests // (args.max_concurrent // args.step),
            endpoint=args.endpoint,
            payload=payload,
        )
    else:
        await tester.run_concurrent_requests(
            num_requests=args.requests,
            concurrent=args.concurrent,
            endpoint=args.endpoint,
            payload=payload,
        )
        tester.stats.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
