# Premium 后台任务 to_results 方法修复

## 问题描述

在 2026-02-10 的测试中发现，Premium 后台任务在尝试缓存结果时失败：

```
2026-02-10 11:52:35,998 - app.services.orchestrator - WARNING - [1770695546596] Background: Failed to cache premium result: 'MergeStepAdapter' object has no attribute 'to_results'
```

### 错误原因

代码中调用了不存在的 `merge_adapter.to_results()` 方法：

```python
# 错误的代码
premium_context, premium_scene = merge_adapter.to_results(premium_parsed)
```

但 `MergeStepAdapter` 类实际上有三个独立的方法：
- `to_context_result(merge_output, dialogs)` - 转换为 ContextResult
- `to_scene_analysis_result(merge_output)` - 转换为 SceneAnalysisResult
- `to_parsed_screenshot_data(merge_output, width, height)` - 转换为 ParsedScreenshotData

没有 `to_results()` 这个方法。

## 解决方案

### 修复 1：后台任务中的调用

```python
# 修复前（错误）
premium_context, premium_scene = merge_adapter.to_results(premium_parsed)

# 修复后（正确）
# 1. 提取 dialogs
screenshot_data = premium_parsed.get("screenshot_parse", {})
bubbles = screenshot_data.get("bubbles", [])

dialogs = []
for bubble in bubbles:
    dialogs.append({
        "speaker": bubble.get("sender", "user"),
        "text": bubble.get("text", ""),
        "timestamp": None,
    })

# 2. 分别调用两个方法
premium_context = merge_adapter.to_context_result(premium_parsed, dialogs)
premium_scene = merge_adapter.to_scene_analysis_result(premium_parsed)
```

### 修复 2：同步 premium 缓存中的调用

同样的修复应用到同步 premium 缓存的代码中（当 premium 在 multimodal 之前完成时）。

## 修改的文件

### `app/services/orchestrator.py`

**位置 1**：第 493-520 行（后台任务）
```python
async def cache_premium_when_ready():
    # ...
    if premium_result:
        premium_parsed = parse_json_with_markdown(premium_result.text)
        if validate_merge_step_result(premium_parsed):
            # 提取 dialogs
            screenshot_data = premium_parsed.get("screenshot_parse", {})
            bubbles = screenshot_data.get("bubbles", [])
            
            dialogs = []
            for bubble in bubbles:
                dialogs.append({
                    "speaker": bubble.get("sender", "user"),
                    "text": bubble.get("text", ""),
                    "timestamp": None,
                })
            
            # 正确调用
            premium_context = merge_adapter.to_context_result(premium_parsed, dialogs)
            premium_scene = merge_adapter.to_scene_analysis_result(premium_parsed)
```

**位置 2**：第 577-600 行（同步缓存）
```python
elif premium_result_or_task and premium_result_or_task != llm_result:
    premium_parsed = parse_json_with_markdown(premium_result_or_task.text)
    if validate_merge_step_result(premium_parsed):
        # 提取 dialogs
        screenshot_data = premium_parsed.get("screenshot_parse", {})
        bubbles = screenshot_data.get("bubbles", [])
        
        dialogs = []
        for bubble in bubbles:
            dialogs.append({
                "speaker": bubble.get("sender", "user"),
                "text": bubble.get("text", ""),
                "timestamp": None,
            })
        
        # 正确调用
        premium_context = merge_adapter.to_context_result(premium_parsed, dialogs)
        premium_scene = merge_adapter.to_scene_analysis_result(premium_parsed)
```

## 预期效果

修复后，Premium 后台任务应该能够正确缓存结果，并打印完整的日志：

```
[1770695546596] Background: Premium task completed, processing result
[1770695546596] Background: Premium result is valid
[1770695546596] Background: Logging premium extraction details
[1770695546596] merge_step [premium|google/gemini-2.0-flash-001] Participants: User='Zhang', Target='徐康'
[1770695546596] FINAL [premium|google/gemini-2.0-flash-001] Layout: left=talker, right=user
[1770695546596] FINAL [premium|google/gemini-2.0-flash-001] Extracted 8 bubbles (sorted top->bottom):
[1770695546596]   [1] talker(left) OK bbox=[0,160,300,250]: 真是的假的
...
[1770695546596] Background: Premium result cached successfully
```

## 为什么会出现这个错误

这个错误是在之前添加 Premium 日志增强时引入的。当时添加了调用 `_log_merge_step_extraction` 的代码，但错误地假设存在一个 `to_results()` 方法来同时获取 context 和 scene。

实际上，主流程中使用的是：
```python
# 主流程中的正确代码
context = adapter.to_context_result(parsed_json, dialogs)
scene = adapter.to_scene_analysis_result(parsed_json)
```

但在后台任务中错误地写成了：
```python
# 错误的代码
premium_context, premium_scene = merge_adapter.to_results(premium_parsed)
```

## 测试验证

修复后，运行相同的测试应该能看到完整的 Premium 日志输出，不再有错误。

---

**修复时间**：2026-02-10  
**修复人员**：Kiro AI Assistant  
**状态**：✅ 已修复
