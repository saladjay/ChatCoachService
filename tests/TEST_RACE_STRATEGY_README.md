# Race Strategy Test Suite

## 概述

这个测试套件验证 multimodal 和 premium 模型之间的竞速策略，确保：
1. 快速响应用户（使用先完成的有效结果）
2. Premium 结果被正确缓存
3. 异常情况被正确处理

## 测试场景

### Test 1: Premium 先完成且有效
```
时间线:
T=0s:  启动 multimodal 和 premium
T=3s:  Premium 完成 ✓ (有效)
T=5s:  Multimodal 完成 (被忽略)

预期结果:
✓ 使用 Premium 结果
✓ Premium 模型: gemini-2.0-flash
✓ 响应时间: 3秒
```

### Test 2: Multimodal 先完成且有效
```
时间线:
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓ (有效)
T=4s:  Premium 完成 ✓ (后台)

预期结果:
✓ 使用 Multimodal 结果
✓ Multimodal 模型: ministral-3b
✓ 响应时间: 2秒
✓ Premium 任务继续在后台运行
✓ Premium 完成后被缓存
```

### Test 3: Premium 失败，Multimodal 成功
```
时间线:
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓ (有效)
T=3s:  Premium 完成 ✗ (失败/无效)

预期结果:
✓ 使用 Multimodal 结果
✓ Premium 结果为 None
✓ 系统容错，不影响用户
```

### Test 4: 两者都失败
```
时间线:
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✗ (失败)
T=3s:  Premium 完成 ✗ (失败)

预期结果:
✓ 没有有效结果
✓ 应该抛出 ValueError
✓ 不生成回复
```

### Test 5: 后台缓存模拟
```
时间线:
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓ → 立即返回
T=2s:  创建后台缓存任务
T=5s:  Premium 完成 ✓ → 后台缓存

预期结果:
✓ 用户在 2秒 得到响应
✓ Premium 在 5秒 完成
✓ Cache service 被调用
✓ 数据被正确缓存
```

### Test 6: 两个模型都很快完成
```
时间线:
T=0s:  启动 multimodal 和 premium
T=1s:  Multimodal 完成 ✓ → 立即返回
T=1s:  开始生成响应（基于 multimodal）
T=2.5s: Premium 完成 ✓ → 后台缓存（慢1.5秒）

预期结果:
✓ 使用 Multimodal 结果（先完成）
✓ 响应时间: 1秒（不等待 premium）
✓ Premium 慢1.5秒，在后台完成
✓ 体现"先到先得"原则：不等待较慢的模型
```

**关键点**: 这个测试验证"先到先得"策略 - 系统会立即使用先完成的结果，而不是等待可能质量更好的 premium 模型。即使 premium 只慢1.5秒，系统也不会等待，优先保证快速响应。

### Test 7: 验证器拒绝两个结果
```
时间线:
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✗ (数据无效)
T=3s:  Premium 完成 ✗ (数据无效)

预期结果:
✓ 验证器拒绝两个结果
✓ 没有有效结果
✓ 应该抛出错误
```

## 运行测试

### 使用 pytest

```bash
# 运行所有测试
pytest tests/test_race_strategy.py -v

# 运行特定测试
pytest tests/test_race_strategy.py::test_premium_wins_completes_first -v

# 显示详细输出
pytest tests/test_race_strategy.py -v -s

# 生成覆盖率报告
pytest tests/test_race_strategy.py --cov=app.services.screenshot_parser --cov-report=html
```

### 直接运行

```bash
# 运行所有测试
python tests/test_race_strategy.py
```

### 预期输出

```
================================================================================
Running Race Strategy Tests
================================================================================

✓ Test 1 passed: Premium wins when it completes first
✓ Test 2 passed: Multimodal wins, premium completes in background
✓ Test 3 passed: Multimodal used when premium fails
✓ Test 4 passed: Both models failed as expected
✓ Test 5 passed: Background caching works correctly
✓ Test 6 passed: Premium used when both complete quickly
✓ Test 7 passed: No winner when validator rejects both

================================================================================
All tests completed!
================================================================================
```

## 测试技术

### Mock 技术

1. **AsyncMock**: 模拟异步函数
   ```python
   async def mock_multimodal():
       await asyncio.sleep(0.02)  # 模拟延迟
       return ("multimodal", MockLLMResult(...))
   ```

2. **时间模拟**: 使用短延迟模拟长时间
   ```python
   await asyncio.sleep(0.02)  # 0.02秒 模拟 2秒
   await asyncio.sleep(0.05)  # 0.05秒 模拟 5秒
   ```

3. **Task 管理**: 手动创建和管理 asyncio.Task
   ```python
   task = asyncio.create_task(mock_function())
   assert not task.done()  # 验证任务还在运行
   await task  # 等待完成
   assert task.done()  # 验证任务已完成
   ```

4. **Mock 验证器**: 简单的验证逻辑
   ```python
   def mock_validator(parsed_json):
       return len(parsed_json.get("bubbles", [])) > 0
   ```

### 关键断言

```python
# 验证策略选择
assert winning_strategy == "premium"

# 验证模型
assert winning_result.model == "gemini-2.0-flash"

# 验证任务状态
assert not premium_task.done()  # 还在运行
assert premium_task.done()      # 已完成

# 验证缓存调用
assert cache_called
assert cached_data == expected_data
```

## 扩展测试

### 添加新测试场景

```python
@pytest.mark.asyncio
async def test_your_scenario():
    """
    Scenario: 描述你的场景
    Expected: 预期结果
    """
    
    # 1. 创建 mock 函数
    async def mock_multimodal():
        await asyncio.sleep(0.02)
        return ("multimodal", MockLLMResult(...))
    
    # 2. 创建任务
    task = asyncio.create_task(mock_multimodal())
    
    # 3. 执行测试逻辑
    result = await task
    
    # 4. 断言
    assert result is not None
    
    print("✓ Your test passed")
```

### 测试超时场景

```python
@pytest.mark.asyncio
async def test_timeout():
    """Test timeout handling."""
    
    async def slow_task():
        await asyncio.sleep(10)  # 很慢
        return "result"
    
    task = asyncio.create_task(slow_task())
    
    try:
        # 设置超时
        result = await asyncio.wait_for(task, timeout=0.1)
    except asyncio.TimeoutError:
        print("✓ Timeout handled correctly")
        task.cancel()
```

### 测试并发数量

```python
@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test multiple concurrent race operations."""
    
    async def single_race():
        # 模拟一次竞速
        await asyncio.sleep(0.02)
        return "result"
    
    # 创建 100 个并发竞速
    tasks = [asyncio.create_task(single_race()) for _ in range(100)]
    
    # 等待所有完成
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 100
    print("✓ Concurrent requests handled correctly")
```

## 性能基准

### 响应时间对比

| 场景 | 旧方案 | 新方案 | 提升 |
|------|--------|--------|------|
| Premium 先完成 (3s) | 3s | 3s | 0% |
| Multimodal 先完成 (2s) | 4s | 2s | 50% |
| Premium 失败 (2s) | 4s | 2s | 50% |

### 缓存效率

| 场景 | 缓存时机 | 影响用户 |
|------|----------|----------|
| Premium 先完成 | 同步缓存 | 否 |
| Premium 后完成 | 后台缓存 | 否 |
| Premium 失败 | 不缓存 | 否 |

## 故障排查

### 测试失败

1. **导入错误**
   ```bash
   # 确保在项目根目录运行
   cd /path/to/project
   python -m pytest tests/test_race_strategy.py
   ```

2. **异步错误**
   ```python
   # 确保使用 @pytest.mark.asyncio
   @pytest.mark.asyncio
   async def test_something():
       ...
   ```

3. **Mock 不工作**
   ```python
   # 确保 patch 路径正确
   with patch('app.services.screenshot_parser.ScreenshotParserService'):
       ...
   ```

### 调试技巧

```python
# 添加日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 打印中间结果
print(f"Task done: {task.done()}")
print(f"Result: {result}")

# 使用 pytest -s 查看输出
pytest tests/test_race_strategy.py -s
```

## 持续集成

### GitHub Actions

```yaml
name: Test Race Strategy

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      - name: Run tests
        run: pytest tests/test_race_strategy.py -v --cov
```

## 总结

这个测试套件全面覆盖了竞速策略的各种场景，确保：
- ✅ 快速响应（使用先完成的结果）
- ✅ Premium 优先（如果可用）
- ✅ 后台缓存（不阻塞用户）
- ✅ 异常处理（容错机制）
- ✅ 性能优化（50% 响应时间减少）
