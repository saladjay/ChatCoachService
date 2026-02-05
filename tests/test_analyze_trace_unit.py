"""Unit tests for analyze_trace.py - None value handling and step_end filtering."""

import json
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path to import analyze_trace
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

import analyze_trace


def create_test_trace_with_none_values():
    """Create a test trace file with None values in model/provider fields."""
    trace_data = {
        "events": [
            # First call with None values
            {
                "ts": "2026-02-05T13:00:00.000000",
                "type": "llm_call_start",
                "call_id": "call_1",
                "prompt": "Test prompt 1"
            },
            {
                "ts": "2026-02-05T13:00:00.500000",
                "type": "llm_call_end",
                "call_id": "call_1",
                "task_type": "scene",
                "provider": None,  # None value
                "model": None,     # None value
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
                "duration_ms": 500,
                "text": "Test response"
            },
            # Second call with step_end (merge_step) - has LLM metadata
            {
                "ts": "2026-02-05T13:00:01.000000",
                "type": "step_start",
                "step_id": "test_step",
                "prompt": "Test prompt 2"
            },
            {
                "ts": "2026-02-05T13:00:01.800000",
                "type": "step_end",
                "step_id": "test_step",
                "step_name": "merge_step_llm",
                "task_type": None,  # None value
                "provider": "openai",
                "model": None,      # None value
                "input_tokens": 200,
                "output_tokens": 100,
                "cost_usd": 0.002,
                "duration_ms": 800
            },
            # Third call with valid values
            {
                "ts": "2026-02-05T13:00:02.000000",
                "type": "llm_call_start",
                "call_id": "call_3",
                "prompt": "Test prompt 3"
            },
            {
                "ts": "2026-02-05T13:00:02.600000",
                "type": "llm_call_end",
                "call_id": "call_3",
                "task_type": "generation",
                "provider": "gemini",
                "model": "gemini-1.5-flash",
                "input_tokens": 150,
                "output_tokens": 75,
                "cost_usd": 0.0015,
                "duration_ms": 600,
                "text": "Another response"
            },
            # Non-LLM step_end (should be filtered out)
            {
                "ts": "2026-02-05T13:00:03.000000",
                "type": "step_end",
                "step_id": "non_llm_step",
                "step_name": "persona_inference",
                "duration_ms": 100,
                "result": {"pacing": "slow", "confidence": 0.7}
            }
        ]
    }
    
    # Create temporary trace file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(trace_data, f, indent=2)
        return f.name


def test_none_value_handling():
    """Test that analyze_trace.py handles None values correctly."""
    print("=" * 80)
    print("TEST: None Value Handling")
    print("=" * 80)
    
    trace_file = create_test_trace_with_none_values()
    
    try:
        # Parse the trace
        with open(trace_file, 'r', encoding='utf-8') as f:
            trace_data = json.load(f)
        
        entries = trace_data.get("events", [])
        llm_calls = analyze_trace.extract_llm_calls(entries)
        
        print(f"\n✓ Successfully parsed {len(llm_calls)} LLM calls")
        
        # Should have 3 LLM calls (2 llm_call_end + 1 step_end with LLM metadata)
        # The non-LLM step_end should be filtered out
        assert len(llm_calls) == 3, f"Expected 3 LLM calls, got {len(llm_calls)}"
        print("✓ Correct number of LLM calls (non-LLM step_end filtered out)")
        
        # Verify all calls have non-None values for critical fields
        for i, call in enumerate(llm_calls, 1):
            print(f"\nCall {i}:")
            print(f"  task_type: {call['task_type']!r}")
            print(f"  provider:  {call['provider']!r}")
            print(f"  model:     {call['model']!r}")
            
            # Verify no None values
            assert call['task_type'] is not None, f"Call {i} has None task_type"
            assert call['provider'] is not None, f"Call {i} has None provider"
            assert call['model'] is not None, f"Call {i} has None model"
            
            # Verify default values are used where needed
            if call['task_type'] == 'unknown':
                print(f"  ✓ Default 'unknown' used for task_type")
            if call['provider'] == 'unknown':
                print(f"  ✓ Default 'unknown' used for provider")
            if call['model'] == 'unknown':
                print(f"  ✓ Default 'unknown' used for model")
        
        print("\n✓ All None values handled correctly")
        
    finally:
        # Clean up
        Path(trace_file).unlink()


def test_print_summary_no_error():
    """Test that print_summary doesn't throw TypeError with None values."""
    print("\n" + "=" * 80)
    print("TEST: print_summary Function")
    print("=" * 80)
    
    trace_file = create_test_trace_with_none_values()
    
    try:
        with open(trace_file, 'r', encoding='utf-8') as f:
            trace_data = json.load(f)
        
        entries = trace_data.get("events", [])
        llm_calls = analyze_trace.extract_llm_calls(entries)
        
        # This should not raise TypeError
        try:
            analyze_trace.print_summary(llm_calls, "TEST TRACE")
            print("\n✓ print_summary executed successfully without TypeError")
        except TypeError as e:
            print(f"\n✗ print_summary failed with TypeError: {e}")
            raise
        
    finally:
        Path(trace_file).unlink()


def test_step_end_filtering():
    """Test that step_end events are correctly filtered."""
    print("\n" + "=" * 80)
    print("TEST: step_end Event Filtering")
    print("=" * 80)
    
    trace_data = {
        "events": [
            # step_end with LLM metadata (should be included)
            {
                "ts": "2026-02-05T13:00:00.000000",
                "type": "step_end",
                "step_id": "llm_step",
                "step_name": "merge_step_llm",
                "provider": "openai",
                "model": "gpt-4",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
                "duration_ms": 500
            },
            # step_end without LLM metadata (should be filtered out)
            {
                "ts": "2026-02-05T13:00:01.000000",
                "type": "step_end",
                "step_id": "non_llm_step",
                "step_name": "persona_inference",
                "duration_ms": 100,
                "result": {"pacing": "slow"}
            },
            # step_end with LLM metadata in result (should be included)
            {
                "ts": "2026-02-05T13:00:02.000000",
                "type": "step_end",
                "step_id": "llm_step_2",
                "step_name": "reply_generation_attempt_1",
                "duration_ms": 800,
                "result": {
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "cost_usd": 0.002
                }
            }
        ]
    }
    
    llm_calls = analyze_trace.extract_llm_calls(trace_data["events"])
    
    print(f"\n✓ Extracted {len(llm_calls)} LLM calls from 3 step_end events")
    
    # Should have 2 LLM calls (2 with LLM metadata, 1 without)
    assert len(llm_calls) == 2, f"Expected 2 LLM calls, got {len(llm_calls)}"
    print("✓ Correctly filtered out non-LLM step_end")
    
    # Verify the included calls have correct metadata
    assert llm_calls[0]['provider'] == 'openai'
    assert llm_calls[0]['model'] == 'gpt-4'
    print("✓ First call has correct metadata from top level")
    
    assert llm_calls[1]['provider'] == 'gemini'
    assert llm_calls[1]['model'] == 'gemini-1.5-flash'
    print("✓ Second call has correct metadata from result field")


def test_task_type_inference():
    """Test that task_type is correctly inferred from step_name."""
    print("\n" + "=" * 80)
    print("TEST: task_type Inference from step_name")
    print("=" * 80)
    
    trace_data = {
        "events": [
            {
                "ts": "2026-02-05T13:00:00.000000",
                "type": "step_end",
                "step_id": "step_1",
                "step_name": "merge_step_llm",
                "provider": "openai",
                "model": "gpt-4",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
                "duration_ms": 500
            },
            {
                "ts": "2026-02-05T13:00:01.000000",
                "type": "step_end",
                "step_id": "step_2",
                "step_name": "reply_generation_attempt_1",
                "provider": "gemini",
                "model": "gemini-1.5-flash",
                "input_tokens": 200,
                "output_tokens": 100,
                "cost_usd": 0.002,
                "duration_ms": 800
            }
        ]
    }
    
    llm_calls = analyze_trace.extract_llm_calls(trace_data["events"])
    
    print(f"\n✓ Extracted {len(llm_calls)} LLM calls")
    
    # Verify task_type inference
    assert llm_calls[0]['task_type'] == 'merge_step', f"Expected 'merge_step', got {llm_calls[0]['task_type']}"
    print("✓ Correctly inferred 'merge_step' from 'merge_step_llm'")
    
    assert llm_calls[1]['task_type'] == 'generation', f"Expected 'generation', got {llm_calls[1]['task_type']}"
    print("✓ Correctly inferred 'generation' from 'reply_generation_attempt_1'")


def run_all_tests():
    """Run all unit tests."""
    print("\n" + "=" * 80)
    print("RUNNING UNIT TESTS FOR analyze_trace.py")
    print("=" * 80 + "\n")
    
    try:
        test_none_value_handling()
        test_print_summary_no_error()
        test_step_end_filtering()
        test_task_type_inference()
        
        print("\n" + "=" * 80)
        print("✓ ALL TESTS PASSED!")
        print("=" * 80 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(run_all_tests())
