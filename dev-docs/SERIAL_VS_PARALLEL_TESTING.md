# 串行 vs 并行处理测试

## 概述

系统现在支持通过环境变量 `USE_MERGE_STEP_PARALLEL` 控制多图处理是否使用并行模式。

## 环境变量

### `USE_MERGE_STEP_PARALLEL`

控制 merge_step 模式下是否并行处理多张图片。

**位置：** `.env` 文件

**值：**
- `true`：并行处理多张图片（默认，更快）
- `false`：串行处理多张图片（逐个处理）

**前提条件：**
- 仅在 `USE_MERGE_STEP=true` 时有效
- 仅影响多图场景（单图无影响）

**示例：**
```bash
# .env 文件
USE_MERGE_STEP=true
USE_MERGE_STEP_PARALLEL=true  # 启用并行处理
```

## 性能对比

### 预期性能（3张图片）

| 模式 | 响应时间 (P50) | 吞吐量 | 性能提升 |
|-----|---------------|--------|---------|
| 串行 | ~21s | ~0.5 req/s | 基准 |
| 并行 | ~7s | ~1.4 req/s | +67% |

### 计算公式

```
性能提升 = (串行时间 - 并行时间) / 串行时间 × 100%
         = (21s - 7s) / 21s × 100%
         = 67%
```

## 测试方法

### 方法 1：自动化脚本（推荐）

使用提供的脚本自动测试两种模式：

**Windows (PowerShell):**
```powershell
.\scripts\test_serial_vs_parallel.ps1
```

**Linux/Mac (Bash):**
```bash
bash scripts/test_serial_vs_parallel.sh
```

脚本会：
1. 设置 `USE_MERGE_STEP_PARALLEL=false` 并运行测试
2. 设置 `USE_MERGE_STEP_PARALLEL=true` 并运行测试
3. 自动对比两次测试结果

### 方法 2：手动测试

#### 步骤 1：测试串行模式

1. 修改 `.env` 文件：
   ```bash
   USE_MERGE_STEP=true
   USE_MERGE_STEP_PARALLEL=false
   ```

2. 重启服务：
   ```bash
   # Windows
   .\start_server.ps1
   
   # Linux/Mac
   bash start_server.sh
   ```

3. 运行负载测试：
   ```bash
   python tests/load_test.py \
     --concurrent 5 \
     --requests 20 \
     --disable-cache \
     --multi-images \
       https://test-r2.zhizitech.org/test_discord_2.png \
       https://test-r2.zhizitech.org/test_discord_3.png \
       https://test-r2.zhizitech.org/test_discord_4.png
   ```

4. 记录结果（特别是 P50 响应时间）

#### 步骤 2：测试并行模式

1. 修改 `.env` 文件：
   ```bash
   USE_MERGE_STEP=true
   USE_MERGE_STEP_PARALLEL=true
   ```

2. 重启服务

3. 运行相同的负载测试

4. 记录结果并对比

### 方法 3：使用 load_test.py 的 --test-both-modes

```bash
python tests/load_test.py \
  --concurrent 5 \
  --requests 20 \
  --disable-cache \
  --multi-images \
    https://test-r2.zhizitech.org/test_discord_2.png \
    https://test-r2.zhizitech.org/test_discord_3.png \
    https://test-r2.zhizitech.org/test_discord_4.png \
  --test-both-modes
```

**注意：** 这个方法需要在两次测试之间手动修改 `.env` 并重启服务。

## 测试输出示例

### 串行模式输出

```
Starting load test:
  Endpoint:          /api/v1/ChatAnalysis/predict
  Total Requests:    20
  Concurrent:        5
  Method:            POST
  Language:          en
  Images:            3 images (multi-image test)
    1. https://test-r2.zhizitech.org/test_discord_2.png
    2. https://test-r2.zhizitech.org/test_discord_3.png
    3. https://test-r2.zhizitech.org/test_discord_4.png
  Cache:             DISABLED (unique session per request)

================================================================================
LOAD TEST SUMMARY
================================================================================

Total Requests:      20
Successful:          20 (100.0%)
Failed:              0 (0.0%)
Total Time:          84.23s
Requests/Second:     0.24

Response Time Stats:
  Min:               20.456s
  Max:               21.789s
  Mean:              21.058s
  Median:            21.034s
  P50:               21.034s
  P90:               21.456s
  P95:               21.623s
  P99:               21.756s
```

### 并行模式输出

```
Starting load test:
  Endpoint:          /api/v1/ChatAnalysis/predict
  Total Requests:    20
  Concurrent:        5
  Method:            POST
  Language:          en
  Images:            3 images (multi-image test)
    1. https://test-r2.zhizitech.org/test_discord_2.png
    2. https://test-r2.zhizitech.org/test_discord_3.png
    3. https://test-r2.zhizitech.org/test_discord_4.png
  Cache:             DISABLED (unique session per request)

================================================================================
LOAD TEST SUMMARY
================================================================================

Total Requests:      20
Successful:          20 (100.0%)
Failed:              0 (0.0%)
Total Time:          28.45s
Requests/Second:     0.70

Response Time Stats:
  Min:               6.823s
  Max:               7.456s
  Mean:              7.113s
  Median:            7.089s
  P50:               7.089s
  P90:               7.289s
  P95:               7.356s
  P99:               7.434s
```

### 对比结果

```
================================================================================
SERIAL VS PARALLEL COMPARISON
================================================================================

Metric                    Serial               Parallel             Improvement    
--------------------------------------------------------------------------------
Total Time                            84.23s               28.45s            66.2%
Mean Response Time                   21.058s                7.113s            66.2%
P50 Response Time                    21.034s                7.089s            66.3%
Throughput (req/s)                      0.24                 0.70           191.7%
Success Rate                         100.0%               100.0%             0.0%

================================================================================
✅ Parallel processing is working! Significant performance improvement detected.
================================================================================
```

## 日志验证

### 串行模式日志

```
INFO - Using merge_step optimized flow with SERIAL processing
INFO - Processing 3 images in SERIAL
INFO - Processing content: https://test-r2.zhizitech.org/test_discord_2.png
INFO - Screenshot analysis completed in 7089ms for test_discord_2.png
INFO - Processing content: https://test-r2.zhizitech.org/test_discord_3.png
INFO - Screenshot analysis completed in 7123ms for test_discord_3.png
INFO - Processing content: https://test-r2.zhizitech.org/test_discord_4.png
INFO - Screenshot analysis completed in 6956ms for test_discord_4.png
```

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
INFO - Parallel processing completed: 3 images processed in original order
```

## 故障排查

### 问题 1：并行模式没有性能提升

**症状：** 并行模式的响应时间与串行模式相似（~21s）

**可能原因：**
1. `USE_MERGE_STEP_PARALLEL` 未设置为 `true`
2. 服务未重启，仍使用旧配置
3. 并行处理代码未生效

**解决方案：**
1. 检查 `.env` 文件：
   ```bash
   USE_MERGE_STEP=true
   USE_MERGE_STEP_PARALLEL=true
   ```

2. 重启服务

3. 检查日志，应该看到：
   ```
   INFO - Using merge_step optimized flow with PARALLEL processing
   INFO - Processing 3 images in PARALLEL
   ```

### 问题 2：串行模式响应时间过长

**症状：** 串行模式响应时间 > 25s（3张图片）

**可能原因：**
- LLM API 响应慢
- 网络延迟高
- 系统资源不足

**解决方案：**
1. 检查 LLM API 状态
2. 使用更快的 LLM 模型
3. 检查网络连接

### 问题 3：并行模式成功率低

**症状：** 并行模式成功率 < 95%

**可能原因：**
- 并发数过高导致资源竞争
- LLM API 限流
- 系统资源不足

**解决方案：**
1. 降低并发数：`--concurrent 3`
2. 增加超时时间：`--timeout 120`
3. 检查系统资源使用率

## 配置建议

### 生产环境

```bash
# .env
USE_MERGE_STEP=true
USE_MERGE_STEP_PARALLEL=true  # 启用并行处理以获得最佳性能
```

### 开发/调试环境

```bash
# .env
USE_MERGE_STEP=true
USE_MERGE_STEP_PARALLEL=false  # 串行处理便于调试
```

### 稳定性优先

```bash
# .env
USE_MERGE_STEP=true
USE_MERGE_STEP_PARALLEL=false  # 串行处理更稳定
```

## 相关文件

- `app/core/config.py`：配置定义
- `app/api/v1/predict.py`：并行/串行处理实现
- `tests/load_test.py`：负载测试工具
- `scripts/test_serial_vs_parallel.ps1`：Windows 测试脚本
- `scripts/test_serial_vs_parallel.sh`：Linux/Mac 测试脚本
- `.env.example`：配置示例

## 总结

通过 `USE_MERGE_STEP_PARALLEL` 环境变量，我们可以：

1. ✅ 灵活控制是否使用并行处理
2. ✅ 在性能和稳定性之间权衡
3. ✅ 方便地进行性能对比测试
4. ✅ 根据不同环境选择合适的模式

并行处理在多图场景下可以带来显著的性能提升（~67%），但需要确保系统资源充足。
