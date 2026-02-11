#!/usr/bin/env python3
"""
Explain Serial vs Parallel Processing Logic

This script provides a detailed explanation of how serial and parallel processing
is triggered in the predict endpoint, with visual diagrams and examples.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_subsection(title: str):
    """Print a subsection header."""
    print("\n" + "-" * 80)
    print(f"  {title}")
    print("-" * 80 + "\n")


def print_code_block(code: str, language: str = "python"):
    """Print a code block with syntax highlighting."""
    print(f"```{language}")
    print(code)
    print("```\n")


def explain_configuration():
    """Explain the configuration variables."""
    print_section("CONFIGURATION VARIABLES")
    
    print("The serial/parallel processing is controlled by two environment variables:\n")
    
    print("1. USE_MERGE_STEP")
    print("   - Controls whether to use the optimized merge_step flow")
    print("   - Default: false")
    print(f"   - Current value: {settings.use_merge_step}")
    print("   - When false: Uses traditional separate flow (screenshot-analysis → context-build → scenario-analysis)")
    print("   - When true: Uses merge_step flow (combines all steps in one LLM call)\n")
    
    print("2. USE_MERGE_STEP_PARALLEL")
    print("   - Controls whether to process multiple images in parallel")
    print("   - Default: true")
    print(f"   - Current value: {settings.use_merge_step_parallel}")
    print("   - Only effective when USE_MERGE_STEP=true")
    print("   - When true: Process multiple images concurrently using asyncio.gather()")
    print("   - When false: Process images one by one in a for loop\n")


def explain_decision_logic():
    """Explain the decision logic."""
    print_section("DECISION LOGIC")
    
    print("The code uses the following logic to decide between serial and parallel:\n")
    
    print_code_block("""
# Step 1: Read configuration
use_merge_step = settings.use_merge_step
use_parallel = settings.use_merge_step_parallel and use_merge_step

# Step 2: Check if request contains images
has_images = any(_is_url(url) for url in request.content)

# Step 3: Decide processing mode
should_use_parallel = use_parallel and has_images

# Step 4: Execute based on decision
if should_use_parallel:
    # PARALLEL PROCESSING MODE
    # Use asyncio.gather() to process all images concurrently
    pass
else:
    # SERIAL PROCESSING MODE
    # Use for loop to process images one by one
    pass
""")
    
    print("Key points:")
    print("  • use_parallel is only True when BOTH use_merge_step AND use_merge_step_parallel are True")
    print("  • should_use_parallel is only True when use_parallel is True AND request contains images")
    print("  • If any condition is False, serial processing is used\n")


def explain_trigger_conditions():
    """Explain the trigger conditions."""
    print_section("TRIGGER CONDITIONS")
    
    print_subsection("Parallel Processing (PARALLEL)")
    
    print("Parallel processing is triggered when ALL of the following are true:\n")
    print("  ✓ USE_MERGE_STEP = true")
    print("  ✓ USE_MERGE_STEP_PARALLEL = true")
    print("  ✓ Request contains at least one image URL\n")
    
    print("Boolean expression:")
    print_code_block("should_use_parallel = (USE_MERGE_STEP and USE_MERGE_STEP_PARALLEL and has_images)")
    
    print("Code path:")
    print_code_block("""
if should_use_parallel:  # True
    # Create tasks for all images
    content_tasks = [process_single_content(url, idx) for ...]
    
    # Execute all tasks concurrently
    content_results = await asyncio.gather(*content_tasks)
    
    # Sort by index to maintain original order
    content_results_sorted = sorted(content_results, key=lambda x: x[0])
""")
    
    print("Log identifiers:")
    print("  • 'Using merge_step optimized flow with PARALLEL processing'")
    print("  • 'Processing X images in PARALLEL'")
    print("  • 'Parallel processing completed: X items processed in original order'\n")
    
    print_subsection("Serial Processing (SERIAL)")
    
    print("Serial processing is triggered when ANY of the following are true:\n")
    print("  • USE_MERGE_STEP = false (traditional flow)")
    print("  • USE_MERGE_STEP_PARALLEL = false (serial merge_step)")
    print("  • Request contains no images (text only)\n")
    
    print("Boolean expression:")
    print_code_block("should_use_parallel = False  # Any condition above")
    
    print("Code path:")
    print_code_block("""
else:  # should_use_parallel = False
    # Process images one by one
    for content_url in request.content:
        if use_merge_step:
            # Serial merge_step
            image_result = await get_merge_step_analysis_result(...)
        else:
            # Traditional flow
            image_result = await get_screenshot_analysis_result(...)
""")
    
    print("Log identifiers:")
    print("  • 'Using merge_step optimized flow with SERIAL processing'")
    print("  • 'Processing X images in SERIAL (one by one)'")
    print("  • 'Processing content: https://...'\n")


def explain_configuration_combinations():
    """Explain different configuration combinations."""
    print_section("CONFIGURATION COMBINATIONS")
    
    combinations = [
        {
            "name": "Parallel merge_step (RECOMMENDED)",
            "config": {
                "USE_MERGE_STEP": "true",
                "USE_MERGE_STEP_PARALLEL": "true",
            },
            "behavior": [
                "Multiple images: Parallel processing (fastest)",
                "Single image: Normal processing",
                "Text only: Serial processing",
            ],
            "performance": [
                "3 images: ~7s",
                "Throughput: ~1.4 req/s",
                "Performance gain: ~67% faster than serial",
            ],
        },
        {
            "name": "Serial merge_step",
            "config": {
                "USE_MERGE_STEP": "true",
                "USE_MERGE_STEP_PARALLEL": "false",
            },
            "behavior": [
                "Multiple images: Serial processing (one by one)",
                "Single image: Normal processing",
                "Text only: Serial processing",
            ],
            "performance": [
                "3 images: ~21s",
                "Throughput: ~0.5 req/s",
                "More stable, easier to debug",
            ],
        },
        {
            "name": "Traditional flow",
            "config": {
                "USE_MERGE_STEP": "false",
                "USE_MERGE_STEP_PARALLEL": "true",  # Ignored
            },
            "behavior": [
                "All requests: Serial traditional flow",
                "USE_MERGE_STEP_PARALLEL has no effect",
                "3 separate LLM calls per image",
            ],
            "performance": [
                "3 images: ~21s (3 independent calls)",
                "Throughput: ~0.5 req/s",
                "Most compatible, most stable",
            ],
        },
    ]
    
    for i, combo in enumerate(combinations, 1):
        print(f"\n{i}. {combo['name']}")
        print("\n   Configuration:")
        for key, value in combo["config"].items():
            print(f"     {key}={value}")
        
        print("\n   Behavior:")
        for behavior in combo["behavior"]:
            print(f"     • {behavior}")
        
        print("\n   Performance:")
        for perf in combo["performance"]:
            print(f"     • {perf}")
        print()


def explain_code_locations():
    """Explain where the code is located."""
    print_section("CODE LOCATIONS")
    
    locations = [
        {
            "file": "app/core/config.py",
            "lines": "202-203",
            "description": "Configuration variable definitions",
            "code": """
use_merge_step: bool = False
use_merge_step_parallel: bool = True
""",
        },
        {
            "file": "app/api/v1/predict.py",
            "lines": "1313-1318",
            "description": "Decision logic and mode logging",
            "code": """
use_merge_step = settings.use_merge_step
use_parallel = settings.use_merge_step_parallel and use_merge_step

if use_merge_step:
    if use_parallel:
        logger.info("Using merge_step optimized flow with PARALLEL processing")
    else:
        logger.info("Using merge_step optimized flow with SERIAL processing")
else:
    logger.info("Using traditional separate flow")
""",
        },
        {
            "file": "app/api/v1/predict.py",
            "lines": "1323-1325",
            "description": "Processing mode determination",
            "code": """
has_images = any(_is_url(url) for url in request.content)
should_use_parallel = use_parallel and has_images
""",
        },
        {
            "file": "app/api/v1/predict.py",
            "lines": "1327-1445",
            "description": "Parallel processing implementation",
            "code": """
if should_use_parallel:
    # PARALLEL PROCESSING MODE
    logger.info(f"Processing {len([url for url in request.content if _is_url(url)])} images in PARALLEL")
    
    async def process_single_content(content_url: str, index: int):
        # Process single image
        ...
    
    content_tasks = [process_single_content(url, idx) for ...]
    content_results = await asyncio.gather(*content_tasks)
    content_results_sorted = sorted(content_results, key=lambda x: x[0])
""",
        },
        {
            "file": "app/api/v1/predict.py",
            "lines": "1447-1520",
            "description": "Serial processing implementation",
            "code": """
else:
    # SERIAL PROCESSING MODE
    logger.info(f"Processing {num_images} images in SERIAL (one by one)")
    
    for content_url in request.content:
        if use_merge_step:
            image_result = await get_merge_step_analysis_result(...)
        else:
            image_result = await get_screenshot_analysis_result(...)
""",
        },
    ]
    
    for loc in locations:
        print(f"\nFile: {loc['file']}")
        print(f"Lines: {loc['lines']}")
        print(f"Description: {loc['description']}")
        print_code_block(loc["code"].strip())


def explain_verification_methods():
    """Explain how to verify the current mode."""
    print_section("VERIFICATION METHODS")
    
    print("There are three ways to verify which processing mode is being used:\n")
    
    print("1. Configuration Verification Script")
    print("   Run the verification script to see current configuration and expected behavior:\n")
    print_code_block("python scripts/verify_serial_parallel.py", "bash")
    
    print("2. Service Logs")
    print("   Start the service and check the logs for mode identifiers:\n")
    print_code_block("""
# Start service
./start_server.ps1  # Windows
bash start_server.sh  # Linux/Mac

# Send test request
curl -X POST http://localhost:8000/api/v1/ChatAnalysis/predict \\
  -H "Content-Type: application/json" \\
  -d '{...}'

# Check logs for:
# Parallel: "Processing X images in PARALLEL"
# Serial: "Processing X images in SERIAL (one by one)"
""", "bash")
    
    print("3. Performance Testing")
    print("   Measure response time to determine mode:\n")
    print_code_block("""
# Test with 3 images
python tests/load_test.py \\
  --concurrent 5 \\
  --requests 20 \\
  --disable-cache \\
  --multi-images url1 url2 url3

# Expected results:
# Parallel: P50 ~7s
# Serial: P50 ~21s
""", "bash")


def explain_common_issues():
    """Explain common issues and solutions."""
    print_section("COMMON ISSUES")
    
    issues = [
        {
            "problem": "Parallel mode not working (response time still ~21s)",
            "symptoms": [
                "Set USE_MERGE_STEP_PARALLEL=true but response time is still slow",
                "Logs show 'SERIAL processing' instead of 'PARALLEL processing'",
            ],
            "causes": [
                "USE_MERGE_STEP=false (parallel only works with merge_step)",
                "Service not restarted after changing .env",
                "Request contains only one image (no parallelization benefit)",
                "Request contains no images (text only)",
            ],
            "solutions": [
                "Set USE_MERGE_STEP=true in .env",
                "Restart the service",
                "Test with multiple images (at least 2)",
                "Verify configuration with: python scripts/verify_serial_parallel.py",
            ],
        },
        {
            "problem": "Serial mode not working (response time still ~7s)",
            "symptoms": [
                "Set USE_MERGE_STEP_PARALLEL=false but response time is still fast",
                "Logs show 'PARALLEL processing' instead of 'SERIAL processing'",
            ],
            "causes": [
                "Service not restarted after changing .env",
                "Cache hit (returning cached results)",
            ],
            "solutions": [
                "Restart the service",
                "Use --disable-cache flag in load test",
                "Verify configuration with: python scripts/verify_serial_parallel.py",
            ],
        },
        {
            "problem": "Performance improvement not significant",
            "symptoms": [
                "Parallel mode enabled but performance gain is less than expected",
            ],
            "causes": [
                "Cache hit (not testing real LLM performance)",
                "Network latency high",
                "LLM API response slow",
                "System resources limited (CPU/memory)",
            ],
            "solutions": [
                "Use --disable-cache flag",
                "Check network connectivity",
                "Check LLM API status",
                "Monitor system resources",
            ],
        },
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. {issue['problem']}")
        
        print("\n   Symptoms:")
        for symptom in issue["symptoms"]:
            print(f"     • {symptom}")
        
        print("\n   Possible causes:")
        for cause in issue["causes"]:
            print(f"     • {cause}")
        
        print("\n   Solutions:")
        for solution in issue["solutions"]:
            print(f"     • {solution}")
        print()


def main():
    """Main function."""
    print("\n" + "=" * 80)
    print("  SERIAL VS PARALLEL PROCESSING - DETAILED EXPLANATION")
    print("=" * 80)
    
    explain_configuration()
    explain_decision_logic()
    explain_trigger_conditions()
    explain_configuration_combinations()
    explain_code_locations()
    explain_verification_methods()
    explain_common_issues()
    
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80 + "\n")
    
    print("Current Configuration:")
    print(f"  USE_MERGE_STEP:          {settings.use_merge_step}")
    print(f"  USE_MERGE_STEP_PARALLEL: {settings.use_merge_step_parallel}")
    print()
    
    use_parallel = settings.use_merge_step_parallel and settings.use_merge_step
    print("Computed Values:")
    print(f"  use_merge_step:          {settings.use_merge_step}")
    print(f"  use_parallel:            {use_parallel}")
    print()
    
    print("Expected Behavior:")
    if use_parallel:
        print("  • Multiple images: PARALLEL processing")
        print("  • Single image: Normal processing")
        print("  • Text only: SERIAL processing")
    elif settings.use_merge_step:
        print("  • All requests: SERIAL merge_step processing")
    else:
        print("  • All requests: SERIAL traditional flow")
    print()
    
    print("For more details, see:")
    print("  • dev-docs/HOW_SERIAL_PARALLEL_WORKS.md")
    print("  • dev-docs/SERIAL_VS_PARALLEL_TESTING.md")
    print("  • dev-docs/IMPLEMENTATION_CHECKLIST.md")
    print()


if __name__ == "__main__":
    main()
