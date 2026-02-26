# 串行与并行处理流程图

## 决策流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Request arrives at predict()                  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Read configuration:    │
                    │ - use_merge_step       │
                    │ - use_merge_step_parallel │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Compute:               │
                    │ use_parallel =         │
                    │   use_merge_step AND   │
                    │   use_merge_step_parallel │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Check request:         │
                    │ has_images =           │
                    │   any(_is_url(url))    │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Decide mode:           │
                    │ should_use_parallel =  │
                    │   use_parallel AND     │
                    │   has_images           │
                    └────────────┬───────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
                ▼                                 ▼
    ┌───────────────────┐           ┌───────────────────┐
    │ should_use_parallel│           │ should_use_parallel│
    │     = True         │           │     = False        │
    └─────────┬─────────┘           └─────────┬─────────┘
              │                                 │
              ▼                                 ▼
    ┌─────────────────┐             ┌─────────────────────┐
    │ PARALLEL MODE   │             │   SERIAL MODE       │
    │                 │             │                     │
    │ asyncio.gather()│             │   for loop          │
    └─────────────────┘             └─────────────────────┘
```

## 并行处理流程（PARALLEL）

```
┌─────────────────────────────────────────────────────────────────┐
│                    PARALLEL PROCESSING MODE                      │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Log: "Processing X     │
                    │ images in PARALLEL"    │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Create tasks:          │
                    │ [process_single_content│
                    │  (url, idx) for ...]   │
                    └────────────┬───────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │        Execute all tasks concurrently       │
        │     content_results = await asyncio.gather()│
        └────────────┬───────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        │            │            │            │
        ▼            ▼            ▼            ▼
    ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
    │Image 1│  │Image 2│  │Image 3│  │Image N│
    │       │  │       │  │       │  │       │
    │ 7s    │  │ 7s    │  │ 7s    │  │ 7s    │
    └───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘
        │          │          │          │
        └──────────┴──────────┴──────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Sort by index to       │
        │ maintain original order│
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Log: "Parallel         │
        │ processing completed"  │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Return results         │
        └────────────────────────┘

Total time: ~7s (max of all parallel tasks)
```

## 串行处理流程（SERIAL）

```
┌─────────────────────────────────────────────────────────────────┐
│                     SERIAL PROCESSING MODE                       │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Log: "Processing X     │
                    │ images in SERIAL"      │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ for content_url in     │
                    │   request.content:     │
                    └────────────┬───────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
                ▼                ▼                ▼
        ┌───────────┐    ┌───────────┐    ┌───────────┐
        │ Image 1   │    │ Image 2   │    │ Image 3   │
        │           │    │           │    │           │
        │ Process   │───▶│ Process   │───▶│ Process   │
        │ 7s        │    │ 7s        │    │ 7s        │
        └───────────┘    └───────────┘    └───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Check use_merge_step   │
                    └────────────┬───────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
                ▼                                 ▼
    ┌───────────────────┐           ┌───────────────────┐
    │ use_merge_step    │           │ use_merge_step    │
    │     = True        │           │     = False       │
    └─────────┬─────────┘           └─────────┬─────────┘
              │                                 │
              ▼                                 ▼
    ┌─────────────────┐             ┌─────────────────────┐
    │ get_merge_step_ │             │ get_screenshot_     │
    │ analysis_result()│             │ analysis_result()   │
    │                 │             │                     │
    │ (strategy=      │             │ (traditional flow)  │
    │  "serial")      │             │                     │
    └─────────┬───────┘             └─────────┬───────────┘
              │                                 │
              └────────────┬────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │ Cache result           │
              │ (if not merge_step)    │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │ Return results         │
              └────────────────────────┘

Total time: ~21s (sum of all sequential tasks)
```

## 配置组合对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION COMBINATIONS                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Parallel merge_step (RECOMMENDED)                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Config:                                                                  │
│   USE_MERGE_STEP=true                                                   │
│   USE_MERGE_STEP_PARALLEL=true                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Flow:                                                                    │
│   Request → Check images → PARALLEL → asyncio.gather() → Results       │
├─────────────────────────────────────────────────────────────────────────┤
│ Performance (3 images):                                                  │
│   Time: ~7s                                                             │
│   Throughput: ~1.4 req/s                                                │
│   Improvement: ~67% faster than serial                                  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Serial merge_step                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Config:                                                                  │
│   USE_MERGE_STEP=true                                                   │
│   USE_MERGE_STEP_PARALLEL=false                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Flow:                                                                    │
│   Request → Check images → SERIAL → for loop → Results                 │
├─────────────────────────────────────────────────────────────────────────┤
│ Performance (3 images):                                                  │
│   Time: ~21s                                                            │
│   Throughput: ~0.5 req/s                                                │
│   Benefit: More stable, easier to debug                                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 3. Traditional flow                                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ Config:                                                                  │
│   USE_MERGE_STEP=false                                                  │
│   USE_MERGE_STEP_PARALLEL=true (ignored)                               │
├─────────────────────────────────────────────────────────────────────────┤
│ Flow:                                                                    │
│   Request → SERIAL → screenshot_parse → context_build → scenario       │
├─────────────────────────────────────────────────────────────────────────┤
│ Performance (3 images):                                                  │
│   Time: ~21s (3 independent calls)                                     │
│   Throughput: ~0.5 req/s                                                │
│   Benefit: Most compatible, most stable                                │
└─────────────────────────────────────────────────────────────────────────┘
```

## 触发条件真值表

```
┌──────────────┬──────────────────────┬────────────┬──────────────────┐
│ USE_MERGE_   │ USE_MERGE_STEP_      │ Has        │ Processing       │
│ STEP         │ PARALLEL             │ Images     │ Mode             │
├──────────────┼──────────────────────┼────────────┼──────────────────┤
│ false        │ false                │ false      │ SERIAL           │
│ false        │ false                │ true       │ SERIAL           │
│ false        │ true                 │ false      │ SERIAL           │
│ false        │ true                 │ true       │ SERIAL           │
│ true         │ false                │ false      │ SERIAL           │
│ true         │ false                │ true       │ SERIAL           │
│ true         │ true                 │ false      │ SERIAL           │
│ true         │ true                 │ true       │ PARALLEL ✓       │
└──────────────┴──────────────────────┴────────────┴──────────────────┘

Key insight: Only ONE combination triggers PARALLEL mode!
```

## 代码执行路径

```
app/api/v1/predict.py:handle_image()
│
├─ Line 1313-1318: Read configuration and log mode
│  │
│  ├─ use_merge_step = settings.use_merge_step
│  ├─ use_parallel = settings.use_merge_step_parallel and use_merge_step
│  │
│  └─ Log: "Using merge_step optimized flow with PARALLEL/SERIAL processing"
│
├─ Line 1323-1325: Determine processing mode
│  │
│  ├─ has_images = any(_is_url(url) for url in request.content)
│  └─ should_use_parallel = use_parallel and has_images
│
├─ Line 1327-1445: PARALLEL PROCESSING BRANCH
│  │
│  ├─ if should_use_parallel:
│  │
│  ├─ Define process_single_content(url, index)
│  │  │
│  │  ├─ Handle text content
│  │  ├─ Handle image content
│  │  │  └─ await get_merge_step_analysis_result(..., strategy="parallel")
│  │  └─ Return (index, kind, url, result)
│  │
│  ├─ Create tasks: [process_single_content(url, idx) for ...]
│  ├─ Execute: content_results = await asyncio.gather(*content_tasks)
│  ├─ Sort: sorted(content_results, key=lambda x: x[0])
│  └─ Extract: items = [(kind, url, result) for ...]
│
└─ Line 1447-1520: SERIAL PROCESSING BRANCH
   │
   ├─ else:  # should_use_parallel = False
   │
   ├─ for content_url in request.content:
   │  │
   │  ├─ Handle text content
   │  │
   │  ├─ Handle image content
   │  │  │
   │  │  ├─ if use_merge_step:
   │  │  │  └─ await get_merge_step_analysis_result(..., strategy="serial")
   │  │  │
   │  │  └─ else:
   │  │     └─ await get_screenshot_analysis_result(...)
   │  │
   │  └─ Cache result (if not merge_step)
   │
   └─ items.append((kind, url, result))
```

## 性能对比图

```
Response Time (3 images):

PARALLEL:  ████████ 7s
           ▲
           │ 67% faster
           │
SERIAL:    ████████████████████████ 21s


Throughput (requests/second):

PARALLEL:  ████████████████ 1.4 req/s
           ▲
           │ 3x improvement
           │
SERIAL:    █████ 0.5 req/s


Resource Usage:

PARALLEL:  ████████████████████ High concurrency
           │ More memory
           │ More CPU during burst
           │
SERIAL:    ████████ Steady usage
           │ Less memory
           │ Predictable CPU
```

## 日志标识对比

### 并行模式日志

```
INFO - Using merge_step optimized flow with PARALLEL processing
INFO - Processing 3 images in PARALLEL
DEBUG - screenshot_start: url=test_discord_2.png
DEBUG - screenshot_start: url=test_discord_3.png
DEBUG - screenshot_start: url=test_discord_4.png
DEBUG - screenshot_end: url=test_discord_2.png, duration=7089ms
DEBUG - screenshot_end: url=test_discord_3.png, duration=6882ms
DEBUG - screenshot_end: url=test_discord_4.png, duration=7234ms
INFO - Parallel processing completed: 3 items processed in original order
```

### 串行模式日志

```
INFO - Using merge_step optimized flow with SERIAL processing
INFO - Processing 3 images in SERIAL (one by one)
INFO - Processing content: https://test-r2.zhizitech.org/test_discord_2.png
INFO - Screenshot analysis completed in 7089ms for test_discord_2.png
INFO - Processing content: https://test-r2.zhizitech.org/test_discord_3.png
INFO - Screenshot analysis completed in 7123ms for test_discord_3.png
INFO - Processing content: https://test-r2.zhizitech.org/test_discord_4.png
INFO - Screenshot analysis completed in 6956ms for test_discord_4.png
```

## 缓存策略

```
┌─────────────────────────────────────────────────────────────────┐
│                         CACHE STRATEGY                           │
└─────────────────────────────────────────────────────────────────┘

PARALLEL MODE:
  ┌──────────────────────────────────────────────────────────┐
  │ get_merge_step_analysis_result()                         │
  │   ├─ Check cache at start (line 713-730)                │
  │   │  └─ Return cached result if found                   │
  │   │                                                      │
  │   ├─ Call LLM if cache miss                             │
  │   │                                                      │
  │   └─ Write cache at end (line 858-868)                  │
  │      └─ Cache with strategy="parallel"                  │
  └──────────────────────────────────────────────────────────┘
  
  No duplicate cache writes in parallel processing code

SERIAL MODE (merge_step):
  ┌──────────────────────────────────────────────────────────┐
  │ get_merge_step_analysis_result()                         │
  │   ├─ Check cache at start (line 713-730)                │
  │   │  └─ Return cached result if found                   │
  │   │                                                      │
  │   ├─ Call LLM if cache miss                             │
  │   │                                                      │
  │   └─ Write cache at end (line 858-868)                  │
  │      └─ Cache with strategy="serial"                    │
  └──────────────────────────────────────────────────────────┘
  
  No duplicate cache writes in serial processing code

SERIAL MODE (traditional):
  ┌──────────────────────────────────────────────────────────┐
  │ get_screenshot_analysis_result()                         │
  │   ├─ Check cache (line 579-650)                         │
  │   │  └─ Return cached result if found                   │
  │   │                                                      │
  │   └─ Call LLM if cache miss                             │
  └──────────────────────────────────────────────────────────┘
  
  ┌──────────────────────────────────────────────────────────┐
  │ handle_image() - Serial branch                           │
  │   └─ Write cache explicitly (line 1456-1467)            │
  │      └─ Cache with strategy="serial"                    │
  └──────────────────────────────────────────────────────────┘
  
  Cache write only for traditional flow (not merge_step)
```

## 总结

### 关键点

1. **触发条件**：只有当 `USE_MERGE_STEP=true` AND `USE_MERGE_STEP_PARALLEL=true` AND 请求包含图片时，才会触发并行处理

2. **性能差异**：并行处理比串行处理快约 67%（3张图片：7s vs 21s）

3. **代码路径**：决策逻辑在 `app/api/v1/predict.py` 的 `handle_image()` 函数中

4. **日志标识**：通过日志可以清楚地识别当前使用的处理模式

5. **缓存策略**：所有模式都正确处理缓存，没有重复写入

### 验证方法

1. 运行 `python scripts/verify_serial_parallel.py` 查看当前配置
2. 运行 `python scripts/explain_serial_parallel.py` 查看详细说明
3. 查看服务日志中的模式标识
4. 测量响应时间（串行 ~21s，并行 ~7s）

### 文档参考

- `dev-docs/HOW_SERIAL_PARALLEL_WORKS.md` - 工作原理详解
- `dev-docs/SERIAL_VS_PARALLEL_TESTING.md` - 测试指南
- `dev-docs/IMPLEMENTATION_CHECKLIST.md` - 实现清单
- `dev-docs/SERIAL_PARALLEL_FLOW_DIAGRAM.md` - 本文档（流程图）
