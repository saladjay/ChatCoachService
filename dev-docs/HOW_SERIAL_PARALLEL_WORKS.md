# 串行与并行处理工作原理

## 代码逻辑

### 配置变量

```python
# app/core/config.py
use_merge_step: bool = False              # 是否使用 merge_step
use_merge_step_parallel: bool = True      # 是否并行处理（仅在 merge_step 时有效）
```

### 决策逻辑

```python
# app/api/v1/predict.py - handle_image()

# 1. 读取配置
use_merge_step = settings.use_merge_step
use_parallel = settings.use_merge_step_parallel and use_merge_step

# 2. 判断是否有图片
has_images = any(_is_url(url) for url in request.content)
should_use_parallel = use_parallel and has_images

# 3. 选择处理模式
if should_use_parallel:
    # 并行处理模式
    # 使用 asyncio.gather() 同时处理所有图片
    pass
else:
    # 串行处理模式
    # 使用 for 循环逐个处理图片
    for content_url in request.content:
        if use_merge_step:
            # 串行 merge_step
            image_result = await get_merge_step_analysis_result(...)
        else:
            # 传统流程
            image_result = await get_screenshot_analysis_result(...)
```

## 触发条件

### 并行处理（PARALLEL）

**条件：**
```
USE_MERGE_STEP=true
AND
USE_MERGE_STEP_PARALLEL=true
AND
请求包含至少一张图片
```

**代码路径：**
```python
if should_use_parallel:  # True
    # 并行处理
    content_tasks = [process_single_content(url, idx) for ...]
    content_results = await asyncio.gather(*content_tasks)
```

**日志标识：**
```
INFO - Using merge_step optimized flow with PARALLEL processing
INFO - Processing 3 images in PARALLEL
INFO - Parallel processing completed: 3 items processed in original order
```

### 串行处理（SERIAL）

**条件：**
```
(USE_MERGE_STEP=false)
OR
(USE_MERGE_STEP=true AND USE_MERGE_STEP_PARALLEL=false)
OR
(请求不包含图片)
```

**代码路径：**
```python
else:  # should_use_parallel = False
    # 串行处理
    for content_url in request.content:
        if use_merge_step:
            # 串行 merge_step
            image_result = await get_merge_step_analysis_result(...)
        else:
            # 传统流程
            image_result = await get_screenshot_analysis_result(...)
```

**日志标识：**
```
INFO - Using merge_step optimized flow with SERIAL processing
INFO - Processing 3 images in SERIAL (one by one)
INFO - Processing content: https://...
INFO - Screenshot analysis completed in 7089ms for ...
```

## 配置组合

### 组合 1：并行 merge_step（推荐）

```bash
# .env
USE_MERGE_STEP=true
USE_MERGE_STEP_PARALLEL=true
```

**行为：**
- 多图：并行处理（最快）
- 单图：正常处理
- 纯文本：串行处理

**性能：**
- 3张图片：~7s
- 吞吐量：~1.4 req/s

### 组合 2：串行 merge_step

```bash
# .env
USE_MERGE_STEP=true
USE_MERGE_STEP_PARALLEL=false
```

**行为：**
- 多图：串行处理（逐个）
- 单图：正常处理
- 纯文本：串行处理

**性能：**
- 3张图片：~21s
- 吞吐量：~0.5 req/s

### 组合 3：传统流程

```bash
# .env
USE_MERGE_STEP=false
USE_MERGE_STEP_PARALLEL=true  # 无效，被忽略
```

**行为：**
- 所有请求：串行传统流程
- `USE_MERGE_STEP_PARALLEL` 不起作用

**性能：**
- 3张图片：~21s（3次独立调用）
- 吞吐量：~0.5 req/s

## 验证方法

### 方法 1：使用验证脚本

```bash
python scripts/verify_serial_parallel.py
```

输出示例：
```
================================================================================
SERIAL VS PARALLEL MODE VERIFICATION
================================================================================

Current Configuration:
  USE_MERGE_STEP:          True
  USE_MERGE_STEP_PARALLEL: True

Computed Values:
  use_merge_step:          True
  use_parallel:            True

Test Scenarios:
--------------------------------------------------------------------------------

1. Single image
   Content count: 1
   Has images: True
   → Mode: PARALLEL

2. Multiple images (3)
   Content count: 3
   Has images: True
   → Mode: PARALLEL

3. Text only
   Content count: 1
   Has images: False
   → Mode: SERIAL (merge_step)
```

### 方法 2：查看服务日志

**启动服务：**
```bash
# Windows
.\start_server.ps1

# Linux/Mac
bash start_server.sh
```

**发送测试请求：**
```bash
curl -X POST http://localhost:8000/api/v1/ChatAnalysis/predict \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "session_id": "test_session",
    "content": [
      "https://test-r2.zhizitech.org/test_discord_2.png",
      "https://test-r2.zhizitech.org/test_discord_3.png",
      "https://test-r2.zhizitech.org/test_discord_4.png"
    ],
    "language": "en",
    "scene": 1,
    "sign": "..."
  }'
```

**查看日志：**

**并行模式：**
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

**串行模式：**
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

### 方法 3：使用负载测试

**测试并行：**
```bash
# 设置环境变量
export USE_MERGE_STEP=true
export USE_MERGE_STEP_PARALLEL=true

# 运行测试
python tests/load_test.py \
  --concurrent 5 \
  --requests 20 \
  --disable-cache \
  --multi-images \
    https://test-r2.zhizitech.org/test_discord_2.png \
    https://test-r2.zhizitech.org/test_discord_3.png \
    https://test-r2.zhizitech.org/test_discord_4.png
```

**预期结果：**
- P50 响应时间：~7s
- 日志显示 "PARALLEL processing"

**测试串行：**
```bash
# 设置环境变量
export USE_MERGE_STEP=true
export USE_MERGE_STEP_PARALLEL=false

# 重启服务
# 运行相同测试
```

**预期结果：**
- P50 响应时间：~21s
- 日志显示 "SERIAL processing"

## 常见问题

### Q1: 为什么设置了 USE_MERGE_STEP_PARALLEL=true 但还是串行？

**可能原因：**

1. **USE_MERGE_STEP=false**
   - `USE_MERGE_STEP_PARALLEL` 只在 `USE_MERGE_STEP=true` 时有效
   - 解决：设置 `USE_MERGE_STEP=true`

2. **服务未重启**
   - 修改 `.env` 后需要重启服务
   - 解决：重启服务

3. **请求只有一张图片**
   - 单图无法体现并行优势
   - 解决：使用多图测试（至少2张）

4. **请求不包含图片**
   - 纯文本请求总是串行
   - 解决：确保请求包含图片 URL

### Q2: 如何确认当前使用的是哪种模式？

**方法 1：查看启动日志**
```bash
python scripts/verify_serial_parallel.py
```

**方法 2：查看请求日志**
- 并行：`"Processing X images in PARALLEL"`
- 串行：`"Processing X images in SERIAL (one by one)"`

**方法 3：测量响应时间**
- 并行：3张图片 ~7s
- 串行：3张图片 ~21s

### Q3: 串行模式有什么优势？

**优势：**
1. **更稳定**：逐个处理，资源占用平稳
2. **更容易调试**：日志按顺序输出
3. **更少并发**：减少对 LLM API 的并发压力

**适用场景：**
- 开发和调试环境
- LLM API 有严格的并发限制
- 系统资源有限

## 代码位置

### 配置定义
- `app/core/config.py` line 208-209

### 处理逻辑
- `app/api/v1/predict.py` line 1310-1500
  - Line 1313-1318: 决策逻辑
  - Line 1320-1325: 模式判断
  - Line 1327-1445: 并行处理
  - Line 1447-1520: 串行处理

### 日志输出
- Line 1313-1318: 模式日志
- Line 1325: 并行日志
- Line 1450: 串行日志

## 总结

**触发串行处理的条件（满足任一）：**
1. `USE_MERGE_STEP=false`（传统流程）
2. `USE_MERGE_STEP_PARALLEL=false`（串行 merge_step）
3. 请求不包含图片（纯文本）

**触发并行处理的条件（全部满足）：**
1. `USE_MERGE_STEP=true`
2. `USE_MERGE_STEP_PARALLEL=true`
3. 请求包含至少一张图片

**验证方法：**
1. 运行 `python scripts/verify_serial_parallel.py`
2. 查看服务日志中的模式标识
3. 测量响应时间（串行 ~21s，并行 ~7s）
