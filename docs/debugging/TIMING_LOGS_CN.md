# 时间日志配置说明

## 概述

时间日志功能为 ChatCoach API 提供详细的性能监控。它跟踪每个处理步骤的持续时间，帮助识别性能瓶颈。

## 配置方法

时间日志通过 trace 配置系统控制。启用时间日志：

### 环境变量配置

在 `.env` 文件中添加：

```bash
# 启用 trace 日志（必需）
TRACE_ENABLED=true

# 设置 trace 级别（建议使用 debug）
TRACE_LEVEL=debug

# 启用时间日志
TRACE_LOG_TIMING=true

# 可选：指定日志文件路径
TRACE_FILE_PATH=logs/trace.jsonl
```

## 记录的内容

当 `TRACE_LOG_TIMING=true` 时，会记录以下时间信息：

### Predict 端点
- **predict_start**: 收到请求
- **question_parsing**: 文本解析（Q&A）
- **prompt_building**: 提示词构建
- **create_llm_adapter**: LLM 适配器初始化
- **llm_call_start/end**: LLM API 调用
- **metrics_recording**: 指标收集
- **response_building**: 响应对象构建
- **text_qa_complete**: Q&A 总处理时间

### Handle Image 函数
- **handle_image_start**: 图像处理开始
- **screenshot_start/end**: 截图分析（每张图片）
- **scenario_analysis**: 场景分析耗时
- **reply_generation**: 回复生成耗时
- **handle_image_complete**: 图像处理总时间

## 日志格式

时间日志以 JSONL 格式写入 `logs/trace.jsonl`：

```json
{
  "level": "debug",
  "type": "screenshot_end",
  "task_type": "screenshot_parse",
  "url": "https://example.com/image.jpg",
  "session_id": "abc123",
  "user_id": "user456",
  "duration_ms": 1234,
  "ts": 1707234567.890
}
```

## 使用示例

### 开发环境启用时间日志

```bash
# 在 .env 文件中
TRACE_ENABLED=true
TRACE_LEVEL=debug
TRACE_LOG_TIMING=true
```

### 生产环境禁用时间日志

```bash
# 在 .env 文件中
TRACE_ENABLED=false
# 或
TRACE_LOG_TIMING=false
```

### 性能分析

```bash
# 查看时间日志
cat logs/trace.jsonl | grep "duration_ms"

# 查找慢操作（>1000ms）
cat logs/trace.jsonl | jq 'select(.duration_ms > 1000)'

# 计算截图分析平均时间
cat logs/trace.jsonl | jq 'select(.type == "screenshot_end") | .duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'
```

## 优势

1. **性能监控**: 跟踪每个步骤的处理时间
2. **瓶颈识别**: 轻松找到慢操作
3. **优化验证**: 验证性能改进效果
4. **生产调试**: 在不启用详细日志的情况下调查慢请求

## 注意事项

- 时间日志需要 `TRACE_ENABLED=true` 才能工作
- 日志默认写入 `logs/trace.jsonl`
- 使用 `TRACE_LEVEL=debug` 查看所有时间事件
- 时间日志对性能影响极小
- 按要求，LLM adapter 中不添加时间日志

## 快速开始

### 1. 编辑 `.env` 文件

```bash
TRACE_ENABLED=true
TRACE_LEVEL=debug
TRACE_LOG_TIMING=true
```

### 2. 重启服务器

```bash
python main.py
```

### 3. 查看日志

```bash
# 实时查看时间日志
tail -f logs/trace.jsonl | grep duration_ms

# 或使用 jq 格式化
tail -f logs/trace.jsonl | jq 'select(.duration_ms)'
```

## 常用分析命令

```bash
# 查找慢操作（>1000ms）
cat logs/trace.jsonl | jq 'select(.duration_ms > 1000)'

# 截图分析平均时间
cat logs/trace.jsonl | jq 'select(.type == "screenshot_end") | .duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'

# 按类型统计事件
cat logs/trace.jsonl | jq -r '.type' | sort | uniq -c

# 查看最近 10 条时间事件
tail -10 logs/trace.jsonl | jq 'select(.duration_ms)'
```

## 更多帮助

- 完整文档: `docs/TIMING_LOGS.md`
- 实现细节: `docs/TIMING_LOGS_IMPLEMENTATION.md`
- 示例脚本: `examples/timing_logs_example.py`
- 快速开始: `docs/TIMING_LOGS_QUICK_START.md`
