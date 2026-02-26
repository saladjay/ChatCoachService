# 负载测试：多图并发处理

## 概述

`load_test.py` 现在支持多图并发处理测试，用于验证并行图片处理功能的性能和稳定性。

## 新增功能

### `--multi-images` 参数

允许指定多个图片 URL 进行测试，模拟真实场景中用户上传多张截图的情况。

```bash
python tests/load_test.py --multi-images url1 url2 url3
```

## 使用示例

### 1. 单图测试（默认）

测试单张图片的处理性能：

```bash
python tests/load_test.py \
  --url http://localhost:8000 \
  --concurrent 10 \
  --requests 100
```

### 2. 多图测试（3张图片）

测试并行处理 3 张图片的性能：

```bash
python tests/load_test.py \
  --url http://localhost:8000 \
  --concurrent 10 \
  --requests 100 \
  --multi-images \
    https://test-r2.zhizitech.org/test_discord_2.png \
    https://test-r2.zhizitech.org/test_discord_3.png \
    https://test-r2.zhizitech.org/test_discord_4.png
```

### 3. 多图测试 + 禁用缓存

测试真实的并行处理性能（每次请求都会调用 LLM）：

```bash
python tests/load_test.py \
  --url http://localhost:8000 \
  --concurrent 5 \
  --requests 50 \
  --disable-cache \
  --multi-images \
    https://test-r2.zhizitech.org/test_discord_2.png \
    https://test-r2.zhizitech.org/test_discord_3.png \
    https://test-r2.zhizitech.org/test_discord_4.png
```

### 4. 多图渐进式测试

找出系统在多图场景下的最大并发能力：

```bash
python tests/load_test.py \
  --url http://localhost:8000 \
  --ramp-up \
  --max-concurrent 20 \
  --step 2 \
  --disable-cache \
  --multi-images \
    https://test-r2.zhizitech.org/test_discord_2.png \
    https://test-r2.zhizitech.org/test_discord_3.png \
    https://test-r2.zhizitech.org/test_discord_4.png
```

## 测试场景对比

### 场景 1：单图 vs 多图（串行处理）

**单图（USE_MERGE_STEP=false）：**
```bash
python tests/load_test.py --concurrent 10 --requests 100
```

预期：
- 响应时间：~7s
- 吞吐量：~1.4 req/s

**3张图（USE_MERGE_STEP=false）：**
```bash
python tests/load_test.py --concurrent 10 --requests 100 \
  --multi-images url1 url2 url3
```

预期：
- 响应时间：~21s（3x 单图）
- 吞吐量：~0.5 req/s

### 场景 2：多图并行 vs 串行（merge_step）

**3张图串行（USE_MERGE_STEP=true，并行处理未启用）：**
```bash
python tests/load_test.py --concurrent 10 --requests 100 \
  --multi-images url1 url2 url3
```

预期：
- 响应时间：~21s
- 吞吐量：~0.5 req/s

**3张图并行（USE_MERGE_STEP=true，并行处理已启用）：**
```bash
python tests/load_test.py --concurrent 10 --requests 100 \
  --multi-images url1 url2 url3
```

预期：
- 响应时间：~7s（与单图相同！）
- 吞吐量：~1.4 req/s
- 性能提升：67%

### 场景 3：缓存命中 vs 缓存未命中

**缓存命中（默认）：**
```bash
python tests/load_test.py --concurrent 50 --requests 500 \
  --multi-images url1 url2 url3
```

预期：
- 响应时间：< 100ms
- 吞吐量：> 100 req/s

**缓存未命中（--disable-cache）：**
```bash
python tests/load_test.py --concurrent 10 --requests 100 \
  --disable-cache \
  --multi-images url1 url2 url3
```

预期：
- 响应时间：~7s（并行）或 ~21s（串行）
- 吞吐量：~1.4 req/s（并行）或 ~0.5 req/s（串行）

## 性能指标

### 关键指标

1. **响应时间（Response Time）**
   - P50：中位数响应时间
   - P90：90% 的请求在此时间内完成
   - P95：95% 的请求在此时间内完成
   - P99：99% 的请求在此时间内完成

2. **吞吐量（Throughput）**
   - 每秒处理的请求数（req/s）
   - 多图并行处理应该接近单图的吞吐量

3. **成功率（Success Rate）**
   - 应该保持在 95% 以上
   - 如果低于 95%，说明系统过载

### 预期性能（3张图片）

| 场景 | 响应时间 (P50) | 吞吐量 | 成功率 |
|-----|---------------|--------|--------|
| 串行处理 | ~21s | ~0.5 req/s | > 95% |
| 并行处理 | ~7s | ~1.4 req/s | > 95% |
| 缓存命中 | < 100ms | > 100 req/s | > 99% |

## 测试输出示例

### 多图测试输出

```
================================================================================
LOAD TEST CONFIGURATION
================================================================================

Application Configuration:
  Default Provider:    openrouter (fallback)
  Default Model:       google/gemini-2.0-flash-exp:free (fallback)

Actual LLM Configuration (from core/llm_adapter/config.yaml):
  Default Provider:    openrouter
  Cheap Model:         google/gemini-2.0-flash-exp:free
  Normal Model:        google/gemini-2.0-flash-exp:free
  Premium Model:       google/gemini-2.0-flash-exp:free
  Multimodal Model:    google/gemini-2.0-flash-exp:free

Merge Step Configuration:
  USE_MERGE_STEP:      True

Cache Configuration:
  NO_REPLY_CACHE:      False
  NO_PERSONA_CACHE:    False

================================================================================

Starting load test:
  Endpoint:          /api/v1/ChatAnalysis/predict
  Total Requests:    100
  Concurrent:        10
  Method:            POST
  Language:          en
  Images:            3 images (multi-image test)
    1. https://test-r2.zhizitech.org/test_discord_2.png
    2. https://test-r2.zhizitech.org/test_discord_3.png
    3. https://test-r2.zhizitech.org/test_discord_4.png
  Cache:             DISABLED (unique session per request)

  Progress: 10/100 (10%) - 1.4 req/s
  Progress: 20/100 (20%) - 1.4 req/s
  Progress: 30/100 (30%) - 1.4 req/s
  ...

================================================================================
LOAD TEST SUMMARY
================================================================================

Total Requests:      100
Successful:          100 (100.0%)
Failed:              0 (0.0%)
Total Time:          71.23s
Requests/Second:     1.40

Response Time Stats:
  Min:               6.823s
  Max:               7.456s
  Mean:              7.089s
  Median:            7.067s
  Std Dev:           0.142s

Percentiles:
  P50:               7.067s
  P90:               7.289s
  P95:               7.356s
  P99:               7.434s

Status Codes:
  200:               100 (100.0%)

================================================================================
```

## 命令行参数

### 新增参数

- `--multi-images URL1 URL2 URL3 ...`：指定多个图片 URL 进行测试
  - 可以指定任意数量的图片
  - 每个请求都会包含所有指定的图片
  - 用于测试并行图片处理功能

### 现有参数

- `--url URL`：API 基础 URL（默认：http://localhost:8000）
- `--endpoint PATH`：API 端点（默认：/api/v1/ChatAnalysis/predict）
- `--concurrent N`：并发请求数（默认：10）
- `--requests N`：总请求数（默认：100）
- `--timeout SECONDS`：请求超时时间（默认：60.0）
- `--image-url URL`：单个图片 URL（已弃用，使用 --multi-images）
- `--disable-cache`：禁用缓存（每个请求使用唯一 session_id）
- `--language CODE`：语言代码（默认：en）
- `--ramp-up`：渐进式测试，找出最大并发能力
- `--max-concurrent N`：渐进式测试的最大并发数（默认：50）
- `--step N`：渐进式测试的步长（默认：5）

## 测试最佳实践

### 1. 先测试单图，再测试多图

```bash
# 1. 单图基准测试
python tests/load_test.py --concurrent 10 --requests 100

# 2. 多图测试
python tests/load_test.py --concurrent 10 --requests 100 \
  --multi-images url1 url2 url3
```

### 2. 使用 --disable-cache 测试真实性能

缓存会显著提升性能，但不能反映真实的 LLM 调用性能：

```bash
python tests/load_test.py --concurrent 5 --requests 50 \
  --disable-cache \
  --multi-images url1 url2 url3
```

### 3. 使用渐进式测试找出系统极限

```bash
python tests/load_test.py --ramp-up \
  --max-concurrent 20 \
  --step 2 \
  --disable-cache \
  --multi-images url1 url2 url3
```

### 4. 监控系统资源

在测试期间监控：
- CPU 使用率
- 内存使用率
- 网络带宽
- Redis 连接数
- LLM API 调用次数

### 5. 测试不同数量的图片

```bash
# 2张图片
python tests/load_test.py --multi-images url1 url2

# 3张图片
python tests/load_test.py --multi-images url1 url2 url3

# 5张图片
python tests/load_test.py --multi-images url1 url2 url3 url4 url5

# 10张图片
python tests/load_test.py --multi-images url1 url2 url3 url4 url5 url6 url7 url8 url9 url10
```

## 故障排查

### 问题 1：响应时间过长

**症状：** P50 > 10s（3张图片）

**可能原因：**
- 并行处理未启用（检查 `USE_MERGE_STEP=true`）
- LLM API 响应慢
- 网络延迟高

**解决方案：**
1. 确认 `.env` 中 `USE_MERGE_STEP=true`
2. 检查 LLM API 状态
3. 使用更快的 LLM 模型

### 问题 2：成功率低

**症状：** Success Rate < 95%

**可能原因：**
- 并发数过高
- 超时时间过短
- LLM API 限流

**解决方案：**
1. 降低并发数：`--concurrent 5`
2. 增加超时时间：`--timeout 120`
3. 检查 LLM API 配额

### 问题 3：吞吐量低

**症状：** Throughput < 1 req/s（3张图片，并行处理）

**可能原因：**
- 串行处理而非并行
- 系统资源不足
- 数据库/Redis 瓶颈

**解决方案：**
1. 确认并行处理已启用
2. 检查系统资源使用率
3. 优化数据库查询

## 相关文件

- `tests/load_test.py`：负载测试脚本
- `dev-docs/PARALLEL_IMAGE_PROCESSING.md`：并行图片处理文档
- `.env`：环境配置（USE_MERGE_STEP）
- `LOAD_TEST_COMMAND.txt`：常用测试命令

## 总结

通过 `--multi-images` 参数，我们可以：

1. ✅ 测试多图并发处理性能
2. ✅ 验证并行处理功能的正确性
3. ✅ 对比串行 vs 并行的性能差异
4. ✅ 找出系统在多图场景下的最大并发能力
5. ✅ 模拟真实用户场景（多张截图）

这对于验证并行图片处理功能的性能提升至关重要。
