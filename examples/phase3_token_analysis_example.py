"""
Phase 3 Token Analysis Example

This script demonstrates:
1. Running the complete conversation generation pipeline with Phase 3 optimizations
2. Enabling trace logging to capture LLM calls
3. Analyzing trace.jsonl to compare token usage with different configurations
4. Displaying model inputs and outputs for comparison

Usage:
    python examples/phase3_token_analysis_example.py
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from app.core.config import settings, PromptConfig
from app.core.container import ServiceContainer, ServiceMode
from app.models.schemas import Message
from app.models.api import GenerateReplyRequest
from app.observability.trace_logger import TraceLogger


async def run_complete_flow_with_config(
    user_id: str,
    conversation: list[Message],
    prompt_config: PromptConfig,
    run_label: str
) -> dict:
    """Run complete flow with specific configuration.
    
    Args:
        user_id: User ID
        conversation: Conversation messages
        prompt_config: Prompt configuration
        run_label: Label for this run (e.g., "baseline" or "optimized")
    
    Returns:
        Dictionary with results and token counts
    """
    # Update prompt configuration
    settings.prompt = prompt_config
    
    # Create container with REAL mode
    container = ServiceContainer(config=settings, mode=ServiceMode.REAL)
    
    # Create orchestrator
    orchestrator = container.create_orchestrator()
    
    # Convert conversation messages to dialogs format
    dialogs = [
        {
            "id": msg.id,
            "speaker": msg.speaker,
            "text": msg.content,
            "timestamp": msg.timestamp.isoformat()
        }
        for msg in conversation
    ]
    
    # Create request object
    request = GenerateReplyRequest(
        user_id=f"{user_id}_{run_label}",  # Add label to user_id to distinguish runs
        target_id="target_user",
        conversation_id="test_conv",
        dialogs=dialogs,
        quality="normal",
        language="en"
    )
    
    # Run the complete flow
    try:
        result = await orchestrator.generate_reply(request)
        
        return {
            "success": True,
            "result": result,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": str(e)
        }


def analyze_trace_file(trace_file: str, user_id_filter: str = None) -> dict:
    """Analyze trace.jsonl file to extract token usage.
    
    Args:
        trace_file: Path to trace file
        user_id_filter: Optional user_id to filter calls
    
    Returns:
        Dictionary with analysis results
    """
    if not os.path.exists(trace_file):
        return {
            "error": f"Trace file not found: {trace_file}",
            "llm_calls": []
        }
    
    llm_calls = []
    total_input_tokens = 0
    total_output_tokens = 0
    
    with open(trace_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                
                # Look for LLM call end entries (which have token counts)
                if entry.get("type") == "llm_call_end":
                    # Filter by user_id if specified
                    if user_id_filter and entry.get("user_id") != user_id_filter:
                        continue
                        
                    call_data = {
                        "timestamp": entry.get("ts"),
                        "task_type": entry.get("task_type"),
                        "provider": entry.get("provider"),
                        "model": entry.get("model"),
                        "input_tokens": entry.get("input_tokens", 0),
                        "output_tokens": entry.get("output_tokens", 0),
                        "cost_usd": entry.get("cost_usd", 0),
                        "prompt": "",  # Prompt is in the start event
                        "response": entry.get("text", "")
                    }
                    
                    llm_calls.append(call_data)
                    total_input_tokens += call_data["input_tokens"]
                    total_output_tokens += call_data["output_tokens"]
                    
            except json.JSONDecodeError:
                continue
    
    return {
        "llm_calls": llm_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "num_calls": len(llm_calls)
    }


def print_comparison_report(baseline: dict, optimized: dict):
    """Print comparison report between baseline and optimized configurations.
    
    Args:
        baseline: Analysis results from baseline configuration
        optimized: Analysis results from optimized configuration
    """
    print("\n" + "="*80)
    print("TOKEN USAGE COMPARISON REPORT")
    print("="*80)
    
    # Overall comparison
    print("\n📊 OVERALL COMPARISON")
    print("-" * 80)
    
    baseline_total = baseline.get("total_tokens", 0)
    optimized_total = optimized.get("total_tokens", 0)
    
    if baseline_total > 0:
        reduction = ((baseline_total - optimized_total) / baseline_total) * 100
    else:
        reduction = 0
    
    print(f"{'Metric':<30} {'Baseline':<15} {'Optimized':<15} {'Change':<15}")
    print("-" * 80)
    print(f"{'Total Tokens':<30} {baseline_total:<15} {optimized_total:<15} {reduction:>+.1f}%")
    print(f"{'Input Tokens':<30} {baseline.get('total_input_tokens', 0):<15} "
          f"{optimized.get('total_input_tokens', 0):<15} "
          f"{((baseline.get('total_input_tokens', 0) - optimized.get('total_input_tokens', 0)) / max(baseline.get('total_input_tokens', 1), 1) * 100):>+.1f}%")
    print(f"{'Output Tokens':<30} {baseline.get('total_output_tokens', 0):<15} "
          f"{optimized.get('total_output_tokens', 0):<15} "
          f"{((baseline.get('total_output_tokens', 0) - optimized.get('total_output_tokens', 0)) / max(baseline.get('total_output_tokens', 1), 1) * 100):>+.1f}%")
    print(f"{'Number of LLM Calls':<30} {baseline.get('num_calls', 0):<15} {optimized.get('num_calls', 0):<15}")
    
    # Per-call comparison
    print("\n📋 PER-CALL BREAKDOWN")
    print("-" * 80)
    
    baseline_calls = baseline.get("llm_calls", [])
    optimized_calls = optimized.get("llm_calls", [])
    
    for i, (b_call, o_call) in enumerate(zip(baseline_calls, optimized_calls), 1):
        print(f"\nCall #{i}: {b_call.get('task_type', 'unknown')}")
        print(f"  Model: {b_call.get('model', 'unknown')}")
        print(f"  Input Tokens:  {b_call.get('input_tokens', 0):>6} → {o_call.get('input_tokens', 0):>6} "
              f"({((b_call.get('input_tokens', 0) - o_call.get('input_tokens', 0)) / max(b_call.get('input_tokens', 1), 1) * 100):>+.1f}%)")
        print(f"  Output Tokens: {b_call.get('output_tokens', 0):>6} → {o_call.get('output_tokens', 0):>6} "
              f"({((b_call.get('output_tokens', 0) - o_call.get('output_tokens', 0)) / max(b_call.get('output_tokens', 1), 1) * 100):>+.1f}%)")


def print_detailed_call_info(call_data: dict, call_num: int):
    """Print detailed information about a single LLM call.
    
    Args:
        call_data: LLM call data
        call_num: Call number
    """
    print(f"\n{'='*80}")
    print(f"LLM CALL #{call_num}: {call_data.get('task_type', 'unknown').upper()}")
    print(f"{'='*80}")
    
    print(f"\n📌 Metadata:")
    print(f"  Provider: {call_data.get('provider', 'unknown')}")
    print(f"  Model: {call_data.get('model', 'unknown')}")
    print(f"  Timestamp: {call_data.get('timestamp', 'unknown')}")
    
    print(f"\n📊 Token Usage:")
    print(f"  Input Tokens:  {call_data.get('input_tokens', 0)}")
    print(f"  Output Tokens: {call_data.get('output_tokens', 0)}")
    print(f"  Total Tokens:  {call_data.get('input_tokens', 0) + call_data.get('output_tokens', 0)}")
    print(f"  Cost (USD):    ${call_data.get('cost_usd', 0):.6f}")
    
    print(f"\n📝 Prompt (Input):")
    print("-" * 80)
    prompt = call_data.get('prompt', '')
    if len(prompt) > 1000:
        print(prompt[:500])
        print(f"\n... [truncated {len(prompt) - 1000} characters] ...\n")
        print(prompt[-500:])
    else:
        print(prompt)
    
    print(f"\n💬 Response (Output):")
    print("-" * 80)
    response = call_data.get('response', '')
    if len(response) > 1000:
        print(response[:500])
        print(f"\n... [truncated {len(response) - 1000} characters] ...\n")
        print(response[-500:])
    else:
        print(response)


async def main():
    """Main function to run token analysis example."""
    print("="*80)
    print("PHASE 3 TOKEN ANALYSIS EXAMPLE")
    print("="*80)
    
    # Enable tracing
    settings.trace.enabled = True
    settings.trace.level = "debug"
    settings.trace.log_llm_prompt = True
    
    # Prepare test data
    user_id = "test_user_phase3"
    conversation = [
        Message(
            id="1",
            speaker="user",
            content="Hi! I'm feeling a bit nervous about our first date tomorrow.",
            timestamp=datetime.now()
        ),
        Message(
            id="2",
            speaker="assistant",
            content="That's completely normal! First dates can be exciting and nerve-wracking at the same time.",
            timestamp=datetime.now()
        ),
        Message(
            id="3",
            speaker="user",
            content="Yeah, I really like this person and don't want to mess it up.",
            timestamp=datetime.now()
        )
    ]
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    trace_file = "logs/trace.jsonl"
    
    # Clear previous trace file
    if os.path.exists(trace_file):
        os.remove(trace_file)
    
    # Configuration 1: Baseline (with reasoning, longer replies)
    print("\n" + "="*80)
    print("RUNNING BASELINE CONFIGURATION")
    print("="*80)
    print("Settings:")
    print("  - include_reasoning: True")
    print("  - max_reply_tokens: 200")
    print("  - use_compact_schemas: False")
    
    baseline_config = PromptConfig(
        include_reasoning=True,
        max_reply_tokens=200,
        use_compact_schemas=False
    )
    
    print("\n⏳ Running baseline flow...")
    baseline_result = await run_complete_flow_with_config(
        user_id=user_id,
        conversation=conversation,
        prompt_config=baseline_config,
        run_label="baseline"
    )
    
    if baseline_result["success"]:
        print("✅ Baseline flow completed successfully")
    else:
        print(f"❌ Baseline flow failed: {baseline_result['error']}")
        return
    
    # Configuration 2: Optimized (Phase 3 optimizations)
    print("\n" + "="*80)
    print("RUNNING OPTIMIZED CONFIGURATION (PHASE 3)")
    print("="*80)
    print("Settings:")
    print("  - include_reasoning: False")
    print("  - max_reply_tokens: 100")
    print("  - use_compact_schemas: True")
    
    optimized_config = PromptConfig(
        include_reasoning=False,
        max_reply_tokens=100,
        use_compact_schemas=True
    )
    
    print("\n⏳ Running optimized flow...")
    optimized_result = await run_complete_flow_with_config(
        user_id=user_id,
        conversation=conversation,
        prompt_config=optimized_config,
        run_label="optimized"
    )
    
    if optimized_result["success"]:
        print("✅ Optimized flow completed successfully")
    else:
        print(f"❌ Optimized flow failed: {optimized_result['error']}")
        return
    
    # Analyze trace file
    print("\n" + "="*80)
    print("ANALYZING TRACE FILE")
    print("="*80)
    
    print("\n📊 Analyzing baseline calls...")
    baseline_analysis = analyze_trace_file(trace_file, user_id_filter=f"{user_id}_baseline")
    
    print("📊 Analyzing optimized calls...")
    optimized_analysis = analyze_trace_file(trace_file, user_id_filter=f"{user_id}_optimized")
    
    # Print comparison report
    print_comparison_report(baseline_analysis, optimized_analysis)
    
    # Print detailed information for each call
    print("\n" + "="*80)
    print("DETAILED CALL INFORMATION - BASELINE")
    print("="*80)
    
    for i, call in enumerate(baseline_analysis.get("llm_calls", []), 1):
        print_detailed_call_info(call, i)
    
    print("\n" + "="*80)
    print("DETAILED CALL INFORMATION - OPTIMIZED")
    print("="*80)
    
    for i, call in enumerate(optimized_analysis.get("llm_calls", []), 1):
        print_detailed_call_info(call, i)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    baseline_total = baseline_analysis.get("total_tokens", 0)
    optimized_total = optimized_analysis.get("total_tokens", 0)
    
    if baseline_total > 0:
        reduction_pct = ((baseline_total - optimized_total) / baseline_total) * 100
        print(f"\n✅ Phase 3 optimizations achieved {reduction_pct:.1f}% token reduction")
        print(f"   Baseline:  {baseline_total} tokens")
        print(f"   Optimized: {optimized_total} tokens")
        print(f"   Saved:     {baseline_total - optimized_total} tokens")
    else:
        print("\n⚠️  Could not calculate token reduction (baseline has 0 tokens)")
    
    print(f"\n📁 Trace file saved: {trace_file}")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
