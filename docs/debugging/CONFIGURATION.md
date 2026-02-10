# Debug Configuration

## 概述

系统提供了灵活的调试配置，允许你控制日志级别和行为，特别是针对 LLM 竞速策略和对话提取日志。

## 环境变量

所有调试配置都通过环境变量控制，前缀为 `DEBUG_`。

### 竞速策略控制

#### `DEBUG_RACE_WAIT_ALL`

控制 LLM 竞速策略的行为。

**值：**
- `false`（默认）：**生产模式** - 第一个有效结果返回后立即停止，取消其他任务
  - 优点：更快，节省成本
  - 缺点：无法对比不同模型的结果
  
- `true`：**调试模式** - 等待所有模型完成，记录所有结果
  - 优点：可以对比不同模型的提取质量
  - 缺点：较慢，消耗更多 token

**示例：**
```env
# 生产环境（默认）
DEBUG_RACE_WAIT_ALL=false

# 调试环境（对比模型）
DEBUG_RACE_WAIT_ALL=true
```

### 日志控制

#### `DEBUG_LOG_MERGE_STEP_EXTRACTION`

控制是否打印 merge_step 提取的对话详情。

**值：**
- `true`（默认）：打印提取的 bubbles 详情
- `false`：不打印

**日志示例：**
```
INFO - [session] merge_step [multimodal|model] Participants: User='...', Target='...'
INFO - [session] RACE [multimodal|model] Layout: left=talker, right=user
INFO - [session] RACE [multimodal|model] Extracted 11 bubbles (sorted top→bottom):
INFO - [session]   [1] talker(left) OK bbox=[10,100,200,140]: 消息内容
INFO - [session]   [2] user(right) OK bbox=[250,150,440,190]: 回复内容
...
INFO - [session] FINAL [multimodal|model] Layout: left=talker, right=user
INFO - [session] FINAL [multimodal|model] Extracted 11 bubbles (sorted top→bottom):
INFO - [session]   [1] talker(left) OK bbox=[10,100,200,140]: 消息内容
INFO - [session]   [2] user(right) OK bbox=[250,150,440,190]: 回复内容
...
```

**日志标记说明：**
- RACE: 竞速过程中的日志（来自 screenshot_parser.py）
- FINAL: 最终结果日志（来自 orchestrator.py）
- OK: sender 与 column 的预期角色匹配
- MISMATCH: sender 与 column 的预期角色不匹配（可能是 LLM 错误）
- Layout: 显示左右列的角色映射（通常 left=talker, right=user）
- bbox=[x1,y1,x2,y2]: 完整的边界框坐标（左上角到右下角）

#### `DEBUG_LOG_SCREENSHOT_PARSE`

控制是否打印 screenshot_parse 提取的对话详情。

**值：**
- `true`（默认）：打印提取的 dialogs 详情
- `false`：不打印

#### `DEBUG_LOG_RACE_STRATEGY`

控制是否打印竞速策略的详细信息。

**值：**
- `true`（默认）：打印竞速过程、赢家、取消任务等信息
- `false`：只打印关键信息

**日志示例：**
```
INFO - [session] merge_step: multimodal returned JSON with keys: [...]
INFO - [session] merge_step: multimodal won (first valid)
INFO - [session] merge_step: Winner found, cancelling remaining tasks
INFO - [session] merge_step race done: multimodal won, model=..., total_results=1, wait_all=false
```

#### `DEBUG_LOG_LLM_CALLS`

控制是否打印详细的 LLM 调用信息（未来功能）。

**值：**
- `false`（默认）：不打印详细 LLM 调用信息
- `true`：打印详细信息

#### `DEBUG_LOG_VALIDATION`

控制是否打印验证详情（未来功能）。

**值：**
- `false`（默认）：不打印验证详情
- `true`：打印详细验证信息

## 使用场景

### 场景 1：生产环境（默认）

快速响应，最小日志。

```env
DEBUG_RACE_WAIT_ALL=false
DEBUG_LOG_MERGE_STEP_EXTRACTION=true
DEBUG_LOG_SCREENSHOT_PARSE=true
DEBUG_LOG_RACE_STRATEGY=false
DEBUG_LOG_LLM_CALLS=false
DEBUG_LOG_VALIDATION=false
```

### 场景 2：调试模型质量

对比不同模型的提取质量。

```env
DEBUG_RACE_WAIT_ALL=true  # 等待所有模型完成
DEBUG_LOG_MERGE_STEP_EXTRACTION=true  # 打印所有模型的提取结果
DEBUG_LOG_SCREENSHOT_PARSE=true
DEBUG_LOG_RACE_STRATEGY=true  # 打印竞速详情
DEBUG_LOG_LLM_CALLS=false
DEBUG_LOG_VALIDATION=false
```

**预期输出：**
```
INFO - [session] Starting merge_step race: multimodal vs premium
INFO - [session] merge_step: multimodal returned JSON with keys: [...]
INFO - [session] merge_step [multimodal|ministral-3b] Participants: User='...', Target='...'
INFO - [session] RACE [multimodal|ministral-3b] Layout: left=talker, right=user
INFO - [session] RACE [multimodal|ministral-3b] Extracted 11 bubbles (sorted top→bottom):
INFO - [session]   [1] talker(left) OK bbox=[10,100,200,140]: ...
INFO - [session]   [2] user(right) OK bbox=[250,150,440,190]: ...
...
INFO - [session] merge_step: multimodal won (first valid)

INFO - [session] merge_step: premium returned JSON with keys: [...]
INFO - [session] merge_step [premium|gemini-2.0-flash] Participants: User='...', Target='...'
INFO - [session] RACE [premium|gemini-2.0-flash] Layout: left=talker, right=user
INFO - [session] RACE [premium|gemini-2.0-flash] Extracted 11 bubbles (sorted top→bottom):
INFO - [session]   [1] talker(left) OK bbox=[10,95,200,135]: ...
INFO - [session]   [2] user(right) OK bbox=[250,145,440,185]: ...
...
INFO - [session] merge_step: premium also valid (but came second)

INFO - [session] merge_step race done: multimodal won, model=..., total_results=2, wait_all=true

INFO - [session] merge_step [multimodal|ministral-3b] Participants: User='...', Target='...'
INFO - [session] FINAL [multimodal|ministral-3b] Layout: left=talker, right=user
INFO - [session] FINAL [multimodal|ministral-3b] Extracted 11 bubbles (sorted top→bottom):
INFO - [session]   [1] talker(left) OK bbox=[10,100,200,140]: ...
INFO - [session]   [2] user(right) OK bbox=[250,150,440,190]: ...
...
```

### 场景 3：最小日志

只记录关键信息。

```env
DEBUG_RACE_WAIT_ALL=false
DEBUG_LOG_MERGE_STEP_EXTRACTION=false  # 不打印提取详情
DEBUG_LOG_SCREENSHOT_PARSE=false
DEBUG_LOG_RACE_STRATEGY=false
DEBUG_LOG_LLM_CALLS=false
DEBUG_LOG_VALIDATION=false
```

## 测试日志输出

使用提供的测试脚本验证日志配置：

```bash
# 启动服务器
python main.py

# 在另一个终端运行测试
python test_logging_output.py
```

或使用 load_test：

```bash
python tests/load_test.py --url http://localhost:80 --image-url https://test-r2.zhizitech.org/test35.jpg --requests 1 --concurrent 1 --disable-cache --language zh
```

## 性能影响

| 配置 | 响应时间 | Token 消耗 | 日志量 |
|------|---------|-----------|--------|
| 生产模式（默认） | 快 | 低 | 中 |
| 调试模式（wait_all=true） | 慢 | 高 | 高 |
| 最小日志 | 快 | 低 | 低 |

## 代码实现

配置在 `app/core/config.py` 中的 `DebugConfig` 类：

```python
class DebugConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEBUG_")
    
    race_wait_all: bool = False
    log_merge_step_extraction: bool = True
    log_screenshot_parse: bool = True
    log_race_strategy: bool = True
    log_llm_calls: bool = False
    log_validation: bool = False
```

使用方式：

```python
from app.core.config import settings

# In screenshot_parser.py (race process)
if settings.debug_config.log_merge_step_extraction:
    self._log_merge_step_conversation(...)

# In orchestrator.py (final result)
if settings.debug_config.log_merge_step_extraction:
    self._log_merge_step_extraction(...)

if settings.debug_config.race_wait_all:
    # Wait for all models
else:
    # Stop after first valid result
```

## Windows 终端显示问题

如果在 Windows CMD 或 PowerShell 中看到乱码或 emoji 显示不正常：

1. **使用 Windows Terminal**（推荐）：
   - 下载：https://aka.ms/terminal
   - 支持 UTF-8 和 emoji 显示

2. **配置 PowerShell**：
   ```powershell
   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   chcp 65001
   ```

3. **配置 CMD**：
   ```cmd
   chcp 65001
   ```

4. **如果 emoji 仍然显示不正常**：
   - 日志功能不受影响，只是显示问题
   - 可以通过日志文件查看完整输出
   - 或使用 `grep` 等工具过滤日志
   - 注意：日志标记已改为文本（RACE/FINAL, OK/MISMATCH），不再使用emoji

## 注意事项

1. **生产环境建议**：使用默认配置（`DEBUG_RACE_WAIT_ALL=false`）以获得最佳性能
2. **调试时**：设置 `DEBUG_RACE_WAIT_ALL=true` 来对比模型质量
3. **日志量**：启用所有日志会产生大量输出，建议只在需要时启用
4. **成本**：`DEBUG_RACE_WAIT_ALL=true` 会调用所有模型，增加 API 成本
5. **日志标记**：
   - RACE: 竞速过程中每个模型的提取结果
   - FINAL: 最终选中的模型的提取结果（来自 orchestrator）
   - OK/MISMATCH: 角色匹配状态（文本标记，不使用emoji）
