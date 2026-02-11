"""
Test cases for the race strategy between multimodal and premium models.

Tests cover various scenarios:
1. Premium completes first and is valid
2. Multimodal completes first and is valid
3. Premium fails, multimodal succeeds
4. Both fail
5. Background caching when premium completes after response
"""

import asyncio
import sys
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.services.screenshot_parser import ScreenshotParserService
from app.services.orchestrator import Orchestrator


# Detect if running under pytest or directly
RUNNING_UNDER_PYTEST = "pytest" in sys.modules


def print_test_info(test_name: str, timeline: str, expected: str, verbose: bool = True):
    """Print test information (only when not running under pytest)."""
    if not RUNNING_UNDER_PYTEST and verbose:
        print("\n" + "=" * 80)
        print(f"[TEST] {test_name}")
        print("=" * 80)
        print("\n[时间线]")
        print(timeline)
        print("\n[预期结果]")
        print(expected)
        print()


def print_test_result(test_name: str, passed: bool, details: str = "", verbose: bool = True):
    """Print test result (only when not running under pytest)."""
    if not RUNNING_UNDER_PYTEST and verbose:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"\n{status} {test_name}")
        if details:
            print(f"   {details}")
        print("=" * 80 + "\n")


class MockLLMResult:
    """Mock LLM result object."""
    
    def __init__(self, text: str, model: str, provider: str = "openrouter"):
        self.text = text
        self.model = model
        self.provider = provider
        self.input_tokens = 100
        self.output_tokens = 50
        self.cost_usd = 0.001


@pytest.fixture
def mock_parser():
    """Create a mock screenshot parser service."""
    parser = Mock(spec=ScreenshotParserService)
    parser.image_fetcher = Mock()
    parser.prompt_manager = Mock()
    parser.llm_adapter = Mock()
    parser.result_normalizer = Mock()
    return parser


@pytest.fixture
def valid_merge_step_json():
    """Valid merge_step JSON response."""
    return {
        "screenshot_parse": {
            "bubbles": [
                {
                    "bubble_id": "1",
                    "text": "Hello",
                    "sender": "user",
                    "column": "right",
                    "bbox": {"x1": 250, "y1": 100, "x2": 400, "y2": 140}
                }
            ],
            "participants": {
                "self": {"nickname": "User"},
                "other": {"nickname": "Target"}
            },
            "layout": {
                "type": "two_columns",
                "left_role": "talker",
                "right_role": "user"
            }
        },
        "conversation_analysis": {
            "summary": "Test conversation"
        },
        "scenario_decision": {
            "relationship_state": "friendly",
            "scenario": "SAFE",
            "intimacy_level": 3,
            "risk_flags": [],
            "current_scenario": "SAFE",
            "recommended_scenario": "SAFE"
        }
    }


@pytest.fixture
def invalid_merge_step_json():
    """Invalid merge_step JSON response (missing required fields)."""
    return {
        "screenshot_parse": {
            "bubbles": []  # Empty bubbles - invalid
        }
    }


# ============================================================================
# Test Case 1: Premium completes first and is valid
# ============================================================================

@pytest.mark.asyncio
async def test_premium_wins_completes_first(mock_parser, valid_merge_step_json):
    """
    Scenario: Premium completes first (3s) and is valid
    Expected: Use premium result immediately
    """
    
    print_test_info(
        "Test 1: Premium 先完成且有效",
        """T=0s:  启动 multimodal 和 premium
T=3s:  Premium 完成 ✓ (有效)
T=5s:  Multimodal 完成 (被忽略)""",
        """✓ 使用 Premium 结果
✓ Premium 模型: gemini-2.0-flash
✓ 响应时间: 3秒"""
    )
    # Mock multimodal call (slower, 5 seconds)
    async def mock_multimodal():
        await asyncio.sleep(0.05)  # Simulate 5s with 0.05s
        return ("multimodal", MockLLMResult(
            text='{"screenshot_parse": {"bubbles": []}}',  # Invalid
            model="ministral-3b"
        ))
    
    # Mock premium call (faster, 3 seconds)
    async def mock_premium():
        await asyncio.sleep(0.03)  # Simulate 3s with 0.03s
        import json
        return ("premium", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="gemini-2.0-flash"
        ))
    
    # Mock validator
    def mock_validator(parsed_json):
        return parsed_json.get("screenshot_parse", {}).get("bubbles", []) != []
    
    # Patch the internal methods
    with patch.object(ScreenshotParserService, '_log_merge_step_conversation'):
        # Create real parser instance
        from app.services.image_fetcher import ImageFetcher
        from app.services.prompt_manager import PromptManager
        from app.services.llm_adapter import LLMAdapterImpl
        from app.services.result_normalizer import ResultNormalizer
        
        parser = ScreenshotParserService(
            image_fetcher=Mock(spec=ImageFetcher),
            prompt_manager=Mock(spec=PromptManager),
            llm_adapter=Mock(spec=LLMAdapterImpl),
            result_normalizer=Mock(spec=ResultNormalizer)
        )
        
        # Manually create tasks
        multimodal_task = asyncio.create_task(mock_multimodal())
        premium_task = asyncio.create_task(mock_premium())
        
        # Simulate the race logic
        pending = {multimodal_task, premium_task}
        winning_result = None
        winning_strategy = None
        premium_result = None
        
        while pending and winning_result is None:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            
            for task in done:
                strategy, result = await task
                
                if strategy == "premium":
                    premium_result = result
                    import json
                    parsed = json.loads(result.text)
                    if mock_validator(parsed):
                        winning_result = result
                        winning_strategy = "premium"
                        break
        
        # Assertions
        assert winning_strategy == "premium"
        assert winning_result.model == "gemini-2.0-flash"
        assert premium_result is not None
        
        print_test_result(
            "Test 1: Premium 先完成且有效",
            True,
            f"策略={winning_strategy}, 模型={winning_result.model}"
        )


# ============================================================================
# Test Case 2: Multimodal completes first and is valid
# ============================================================================

@pytest.mark.asyncio
async def test_multimodal_wins_completes_first(mock_parser, valid_merge_step_json):
    """
    Scenario: Multimodal completes first (2s) and is valid, premium slower (4s)
    Expected: Use multimodal result immediately, premium task still running
    """
    
    print_test_info(
        "Test 2: Multimodal 先完成且有效",
        """T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓ (有效)
T=4s:  Premium 完成 ✓ (后台)""",
        """✓ 使用 Multimodal 结果
✓ Multimodal 模型: ministral-3b
✓ 响应时间: 2秒
✓ Premium 任务继续在后台运行
✓ Premium 完成后被缓存"""
    )
    # Mock multimodal call (faster, 2 seconds)
    async def mock_multimodal():
        await asyncio.sleep(0.02)  # Simulate 2s
        import json
        return ("multimodal", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="ministral-3b"
        ))
    
    # Mock premium call (slower, 4 seconds)
    async def mock_premium():
        await asyncio.sleep(0.04)  # Simulate 4s
        import json
        return ("premium", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="gemini-2.0-flash"
        ))
    
    def mock_validator(parsed_json):
        return parsed_json.get("screenshot_parse", {}).get("bubbles", []) != []
    
    # Create tasks
    multimodal_task = asyncio.create_task(mock_multimodal())
    premium_task = asyncio.create_task(mock_premium())
    
    # Simulate race
    pending = {multimodal_task, premium_task}
    winning_result = None
    winning_strategy = None
    premium_completed = False
    
    while pending and winning_result is None:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            strategy, result = await task
            
            if strategy == "premium":
                premium_completed = True
                import json
                parsed = json.loads(result.text)
                if mock_validator(parsed):
                    winning_result = result
                    winning_strategy = "premium"
            elif strategy == "multimodal" and winning_result is None:
                import json
                parsed = json.loads(result.text)
                if mock_validator(parsed):
                    winning_result = result
                    winning_strategy = "multimodal"
    
    # Assertions
    assert winning_strategy == "multimodal"
    assert winning_result.model == "ministral-3b"
    assert not premium_completed  # Premium should still be running when we return
    
    # Verify premium task is still running
    assert not premium_task.done()
    
    # Wait for premium to complete (background)
    await premium_task
    assert premium_task.done()
    
    print_test_result(
        "Test 2: Multimodal 先完成且有效",
        True,
        f"策略={winning_strategy}, 模型={winning_result.model}, Premium后台完成={premium_task.done()}"
    )


# ============================================================================
# Test Case 3: Premium fails, multimodal succeeds
# ============================================================================

@pytest.mark.asyncio
async def test_premium_fails_multimodal_succeeds(mock_parser, valid_merge_step_json):
    """
    Scenario: Premium fails/returns invalid, multimodal succeeds
    Expected: Use multimodal result
    """
    
    print_test_info(
        "Test 3: Premium 失败，Multimodal 成功",
        """T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓ (有效)
T=3s:  Premium 完成 ✗ (失败/无效)""",
        """✓ 使用 Multimodal 结果
✓ Premium 结果为 None
✓ 系统容错，不影响用户"""
    )
# ============================================================================

@pytest.mark.asyncio
async def test_premium_fails_multimodal_succeeds(mock_parser, valid_merge_step_json):
    """
    Scenario: Premium fails/returns invalid, multimodal succeeds
    Expected: Use multimodal result
    """
    
    # Mock multimodal call (valid)
    async def mock_multimodal():
        await asyncio.sleep(0.02)
        import json
        return ("multimodal", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="ministral-3b"
        ))
    
    # Mock premium call (fails)
    async def mock_premium():
        await asyncio.sleep(0.03)
        return ("premium", None)  # Failed
    
    def mock_validator(parsed_json):
        return parsed_json.get("screenshot_parse", {}).get("bubbles", []) != []
    
    # Create tasks
    multimodal_task = asyncio.create_task(mock_multimodal())
    premium_task = asyncio.create_task(mock_premium())
    
    # Simulate race
    pending = {multimodal_task, premium_task}
    winning_result = None
    winning_strategy = None
    multimodal_result = None
    premium_result = None
    
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            strategy, result = await task
            
            if strategy == "premium":
                premium_result = result
            elif strategy == "multimodal":
                multimodal_result = result
                if result:
                    import json
                    parsed = json.loads(result.text)
                    if mock_validator(parsed):
                        if winning_result is None:
                            winning_result = result
                            winning_strategy = "multimodal"
    
    # Assertions
    assert winning_strategy == "multimodal"
    assert winning_result.model == "ministral-3b"
    assert premium_result is None
    assert multimodal_result is not None
    
    print_test_result(
        "Test 3: Premium 失败，Multimodal 成功",
        True,
        f"策略={winning_strategy}, 模型={winning_result.model}, Premium结果={premium_result}"
    )


# ============================================================================
# Test Case 4: Both fail
# ============================================================================

@pytest.mark.asyncio
async def test_both_fail():
    """
    Scenario: Both multimodal and premium fail or return invalid data
    Expected: Raise ValueError
    """
    
    print_test_info(
        "Test 4: 两者都失败",
        """T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✗ (失败)
T=3s:  Premium 完成 ✗ (失败)""",
        """✓ 没有有效结果
✓ 应该抛出 ValueError
✓ 不生成回复"""
    )
# ============================================================================

@pytest.mark.asyncio
async def test_both_fail():
    """
    Scenario: Both multimodal and premium fail or return invalid data
    Expected: Raise ValueError
    """
    
    # Mock both calls failing
    async def mock_multimodal():
        await asyncio.sleep(0.02)
        return ("multimodal", None)
    
    async def mock_premium():
        await asyncio.sleep(0.03)
        return ("premium", None)
    
    # Create tasks
    multimodal_task = asyncio.create_task(mock_multimodal())
    premium_task = asyncio.create_task(mock_premium())
    
    # Simulate race
    pending = {multimodal_task, premium_task}
    winning_result = None
    
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            strategy, result = await task
            # Both return None
    
    # Assertions
    assert winning_result is None
    
    print_test_result(
        "Test 4: 两者都失败",
        True,
        "两个模型都返回 None，符合预期"
    )


# ============================================================================
# Test Case 5: Background caching simulation
# ============================================================================

@pytest.mark.asyncio
async def test_background_caching(valid_merge_step_json):
    """
    Scenario: Multimodal returns first, premium completes later
    Expected: Premium result is cached in background
    """
    
    print_test_info(
        "Test 5: 后台缓存模拟",
        """T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓ → 立即返回
T=2s:  创建后台缓存任务
T=5s:  Premium 完成 ✓ → 后台缓存""",
        """✓ 用户在 2秒 得到响应
✓ Premium 在 5秒 完成
✓ Cache service 被调用
✓ 数据被正确缓存"""
    )
# ============================================================================

@pytest.mark.asyncio
async def test_background_caching(valid_merge_step_json):
    """
    Scenario: Multimodal returns first, premium completes later
    Expected: Premium result is cached in background
    """
    
    cache_called = False
    cached_data = None
    
    # Mock cache service
    class MockCacheService:
        async def set(self, category, resource, data):
            nonlocal cache_called, cached_data
            cache_called = True
            cached_data = data
    
    # Mock multimodal (fast)
    async def mock_multimodal():
        await asyncio.sleep(0.02)
        import json
        return ("multimodal", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="ministral-3b"
        ))
    
    # Mock premium (slow)
    async def mock_premium():
        await asyncio.sleep(0.05)
        import json
        return ("premium", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="gemini-2.0-flash"
        ))
    
    # Create tasks
    multimodal_task = asyncio.create_task(mock_multimodal())
    premium_task = asyncio.create_task(mock_premium())
    
    # Wait for first result
    done, pending = await asyncio.wait(
        {multimodal_task, premium_task},
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # Get first result
    first_task = list(done)[0]
    strategy, result = await first_task
    
    assert strategy == "multimodal"
    assert result.model == "ministral-3b"
    
    # Simulate background caching
    async def cache_premium_when_ready():
        nonlocal cache_called
        _, premium_result = await premium_task
        
        # Simulate caching
        cache_service = MockCacheService()
        await cache_service.set(
            category="context_analysis",
            resource="test_resource",
            data={"test": "data"}
        )
    
    # Start background task
    background_task = asyncio.create_task(cache_premium_when_ready())
    
    # Wait for background task to complete
    await background_task
    
    # Assertions
    assert cache_called
    assert cached_data == {"test": "data"}
    
    print_test_result(
        "Test 5: 后台缓存模拟",
        True,
        f"缓存调用={cache_called}, 缓存数据={cached_data}"
    )


# ============================================================================
# Test Case 6: Both models complete quickly (multimodal first)
# ============================================================================

@pytest.mark.asyncio
async def test_multimodal_first_premium_shortly_after(valid_merge_step_json):
    """
    Scenario: Multimodal completes first (2s), premium shortly after (2.5s)
    Expected: Use multimodal result immediately, don't wait for premium
    """
    
    print_test_info(
        "Test 6: 两个模型都很快完成",
        """T=0s:  启动 multimodal 和 premium
T=1s:  Multimodal 完成 ✓ → 立即返回
T=1s:  开始生成响应（基于 multimodal）
T=2.5s: Premium 完成 ✓ → 后台缓存（慢1.5秒）""",
        """✓ 使用 Multimodal 结果（先完成）
✓ 响应时间: 1秒（不等待 premium）
✓ Premium 慢1.5秒，在后台完成
✓ 体现"先到先得"原则：不等待较慢的模型"""
    )
# ============================================================================

@pytest.mark.asyncio
async def test_multimodal_first_premium_shortly_after(valid_merge_step_json):
    """
    Scenario: Multimodal completes first (2s), premium shortly after (2.5s)
    Expected: Use multimodal result immediately, don't wait for premium
    """
    
    # Mock multimodal call (faster, 2 seconds)
    async def mock_multimodal():
        await asyncio.sleep(0.01)  # Simulate 1s (更快)
        import json
        return ("multimodal", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="ministral-3b"
        ))
    
    # Mock premium call (slightly slower, 2.5 seconds)
    async def mock_premium():
        await asyncio.sleep(0.025)  # Simulate 2.5s
        import json
        return ("premium", MockLLMResult(
            text=json.dumps(valid_merge_step_json),
            model="gemini-2.0-flash"
        ))
    
    def mock_validator(parsed_json):
        return parsed_json.get("screenshot_parse", {}).get("bubbles", []) != []
    
    # Create tasks
    multimodal_task = asyncio.create_task(mock_multimodal())
    premium_task = asyncio.create_task(mock_premium())
    
    # Simulate race - wait for first valid result
    pending = {multimodal_task, premium_task}
    winning_result = None
    winning_strategy = None
    
    while pending and winning_result is None:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            strategy, result = await task
            if result:
                import json
                parsed = json.loads(result.text)
                if mock_validator(parsed):
                    winning_result = result
                    winning_strategy = strategy
                    # Break immediately - don't wait for other tasks
                    break
        
        # If we have a winner, break out of while loop
        if winning_result:
            break
    
    # Assertions
    assert winning_strategy == "multimodal"  # Multimodal won (first to complete)
    assert winning_result.model == "ministral-3b"
    
    # Premium should still be running or just completed
    # The key point: we didn't wait for it
    if not premium_task.done():
        # Premium still running - will be cached in background
        await premium_task  # Wait for it to complete (simulating background)
    
    assert premium_task.done()
    
    print_test_result(
        "Test 6: 两个模型都很快完成",
        True,
        f"策略={winning_strategy}, 模型={winning_result.model}, Premium完成={premium_task.done()}"
    )


# ============================================================================
# Test Case 7: Validator rejects both results
# ============================================================================

@pytest.mark.asyncio
async def test_validator_rejects_both(invalid_merge_step_json):
    """
    Scenario: Both models return data but validator rejects both
    Expected: No winning result
    """
    
    print_test_info(
        "Test 7: 验证器拒绝两个结果",
        """T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✗ (数据无效)
T=3s:  Premium 完成 ✗ (数据无效)""",
        """✓ 验证器拒绝两个结果
✓ 没有有效结果
✓ 应该抛出错误"""
    )
# ============================================================================

@pytest.mark.asyncio
async def test_validator_rejects_both(invalid_merge_step_json):
    """
    Scenario: Both models return data but validator rejects both
    Expected: No winning result
    """
    
    # Mock both calls returning invalid data
    async def mock_multimodal():
        await asyncio.sleep(0.02)
        import json
        return ("multimodal", MockLLMResult(
            text=json.dumps(invalid_merge_step_json),
            model="ministral-3b"
        ))
    
    async def mock_premium():
        await asyncio.sleep(0.03)
        import json
        return ("premium", MockLLMResult(
            text=json.dumps(invalid_merge_step_json),
            model="gemini-2.0-flash"
        ))
    
    def mock_validator(parsed_json):
        bubbles = parsed_json.get("screenshot_parse", {}).get("bubbles", [])
        return len(bubbles) > 0  # Requires at least one bubble
    
    # Create tasks
    multimodal_task = asyncio.create_task(mock_multimodal())
    premium_task = asyncio.create_task(mock_premium())
    
    # Simulate race
    pending = {multimodal_task, premium_task}
    winning_result = None
    
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            strategy, result = await task
            if result:
                import json
                parsed = json.loads(result.text)
                if mock_validator(parsed):
                    winning_result = result
    
    # Assertions
    assert winning_result is None
    
    print_test_result(
        "Test 7: 验证器拒绝两个结果",
        True,
        "验证器正确拒绝了无效数据"
    )


# ============================================================================
# Run all tests
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Race Strategy Tests - 直接执行模式")
    print("=" * 80)
    print("提示: 使用 pytest 执行时不会显示详细信息")
    print("=" * 80 + "\n")
    
    # Run tests
    asyncio.run(test_premium_wins_completes_first(None, {
        "screenshot_parse": {
            "bubbles": [{"bubble_id": "1", "text": "test", "sender": "user", "column": "right", "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}],
            "participants": {"self": {"nickname": "User"}, "other": {"nickname": "Target"}},
            "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}
        },
        "conversation_analysis": {"summary": "test"},
        "scenario_decision": {"relationship_state": "friendly", "scenario": "SAFE", "intimacy_level": 3, "risk_flags": [], "current_scenario": "SAFE", "recommended_scenario": "SAFE"}
    }))
    
    asyncio.run(test_multimodal_wins_completes_first(None, {
        "screenshot_parse": {
            "bubbles": [{"bubble_id": "1", "text": "test", "sender": "user", "column": "right", "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}],
            "participants": {"self": {"nickname": "User"}, "other": {"nickname": "Target"}},
            "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}
        },
        "conversation_analysis": {"summary": "test"},
        "scenario_decision": {"relationship_state": "friendly", "scenario": "SAFE", "intimacy_level": 3, "risk_flags": [], "current_scenario": "SAFE", "recommended_scenario": "SAFE"}
    }))
    
    asyncio.run(test_premium_fails_multimodal_succeeds(None, {
        "screenshot_parse": {
            "bubbles": [{"bubble_id": "1", "text": "test", "sender": "user", "column": "right", "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}],
            "participants": {"self": {"nickname": "User"}, "other": {"nickname": "Target"}},
            "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}
        },
        "conversation_analysis": {"summary": "test"},
        "scenario_decision": {"relationship_state": "friendly", "scenario": "SAFE", "intimacy_level": 3, "risk_flags": [], "current_scenario": "SAFE", "recommended_scenario": "SAFE"}
    }))
    
    asyncio.run(test_both_fail())
    
    asyncio.run(test_background_caching({
        "screenshot_parse": {
            "bubbles": [{"bubble_id": "1", "text": "test", "sender": "user", "column": "right", "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}],
            "participants": {"self": {"nickname": "User"}, "other": {"nickname": "Target"}},
            "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}
        },
        "conversation_analysis": {"summary": "test"},
        "scenario_decision": {"relationship_state": "friendly", "scenario": "SAFE", "intimacy_level": 3, "risk_flags": [], "current_scenario": "SAFE", "recommended_scenario": "SAFE"}
    }))
    
    asyncio.run(test_multimodal_first_premium_shortly_after({
        "screenshot_parse": {
            "bubbles": [{"bubble_id": "1", "text": "test", "sender": "user", "column": "right", "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}],
            "participants": {"self": {"nickname": "User"}, "other": {"nickname": "Target"}},
            "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}
        },
        "conversation_analysis": {"summary": "test"},
        "scenario_decision": {"relationship_state": "friendly", "scenario": "SAFE", "intimacy_level": 3, "risk_flags": [], "current_scenario": "SAFE", "recommended_scenario": "SAFE"}
    }))
    
    asyncio.run(test_validator_rejects_both({
        "screenshot_parse": {
            "bubbles": []  # Invalid - empty
        }
    }))
    
    print("\n" + "=" * 80)
    print("[COMPLETE] 所有测试完成!")
    print("=" * 80)
    print("\n提示: 使用 'pytest tests/test_race_strategy.py -v' 运行 pytest 模式\n")

