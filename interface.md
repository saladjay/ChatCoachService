# Conversation Generation Service - 接口文档

## 1. HTTP API 接口

### 1.1 健康检查

| 属性 | 值 |
|------|-----|
| 端点 | `/health` |
| 方法 | GET |
| 描述 | 服务健康检查 |

**响应示例:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

### 1.2 生成对话回复

| 属性 | 值 |
|------|-----|
| 端点 | `/api/v1/generate/reply` |
| 方法 | POST |
| 描述 | 生成对话回复建议 |

#### 请求体 (GenerateReplyRequest)

| 字段 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `user_id` | string | ✅ | - | 用户ID |
| `target_id` | string | ✅ | - | 目标用户ID |
| `conversation_id` | string | ✅ | - | 对话ID |
| `language` | string | ❌ | `"zh-CN"` | 语言代码 |
| `quality` | string | ❌ | `"normal"` | 质量等级: `"cheap"` \| `"normal"` \| `"premium"` |
| `force_regenerate` | boolean | ❌ | `false` | 是否强制重新生成 |

**请求示例:**
```json
{
  "user_id": "user123",
  "target_id": "target456",
  "conversation_id": "conv789",
  "language": "zh-CN",
  "quality": "normal",
  "force_regenerate": false
}
```

#### 响应体 (GenerateReplyResponse)

| 字段 | 类型 | 描述 |
|------|------|------|
| `reply_text` | string | 生成的回复文本 |
| `confidence` | float | 置信度 (0-1) |
| `intimacy_level_before` | int | 生成前亲密度等级 (1-5) |
| `intimacy_level_after` | int | 生成后亲密度等级 (1-5) |
| `model` | string | 使用的 LLM 模型 |
| `provider` | string | LLM 提供商 |
| `cost_usd` | float | 本次调用成本 (USD) |
| `fallback` | boolean | 是否使用了回退响应 |

**响应示例:**
```json
{
  "reply_text": "我觉得我们可以慢慢聊，不着急。",
  "confidence": 0.85,
  "intimacy_level_before": 2,
  "intimacy_level_after": 3,
  "model": "gpt-4",
  "provider": "openai",
  "cost_usd": 0.002,
  "fallback": false
}
```

#### 错误响应

| HTTP 状态码 | 错误类型 | 描述 |
|-------------|----------|------|
| 400 | `validation_error` | 参数验证失败 |
| 402 | `quota_exceeded` | 用户额度不足 |
| 500 | `internal_error` | 内部服务错误 |
| 503 | `service_unavailable` | 服务不可用 |
| 504 | `timeout` | 服务超时 |

**错误响应示例:**
```json
{
  "error": "validation_error",
  "message": "Invalid request parameters",
  "details": ["user_id: field required"]
}
```

---

## 2. 子模块抽象接口

所有子模块接口定义在 `app/services/base.py`，采用抽象基类模式。

### 2.1 BaseContextBuilder - 上下文构建器

```python
class BaseContextBuilder(ABC):
    @abstractmethod
    async def build_context(self, input: ContextBuilderInput) -> ContextResult:
        ...
```

**输入 (ContextBuilderInput):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `user_id` | str | 用户ID |
| `target_id` | str | 目标用户ID |
| `conversation_id` | str | 对话ID |
| `history_dialog` | list[Message] | 历史对话列表 |
| `emotion_trend` | EmotionSummary \| None | 情绪趋势 |

**输出 (ContextResult):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `conversation_summary` | str | 对话摘要 |
| `emotion_state` | str | 情绪状态 |
| `current_intimacy_level` | int | 当前亲密度 (1-5) |
| `risk_flags` | list[str] | 风险标记 |

---

### 2.2 BaseSceneAnalyzer - 场景分析器

```python
class BaseSceneAnalyzer(ABC):
    @abstractmethod
    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        ...
```

**输入 (SceneAnalysisInput):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `conversation_id` | str | 对话ID |
| `history_dialog` | list[Message] | 历史对话列表 |
| `emotion_trend` | EmotionSummary \| None | 情绪趋势 |

**输出 (SceneAnalysisResult):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `scene` | str | 场景类型: `"破冰"` \| `"推进"` \| `"冷却"` \| `"维持"` |
| `intimacy_level` | int | 亲密度等级 (1-5) |
| `risk_flags` | list[str] | 风险标记 |

---

### 2.3 BasePersonaInferencer - 用户画像推理器

```python
class BasePersonaInferencer(ABC):
    @abstractmethod
    async def infer_persona(self, input: PersonaInferenceInput) -> PersonaSnapshot:
        ...
```

**输入 (PersonaInferenceInput):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `user_id` | str | 用户ID |
| `conversation_id` | str | 对话ID |
| `scene` | str | 当前场景 |
| `history_dialog` | list[Message] | 历史对话列表 |

**输出 (PersonaSnapshot):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `style` | str | 风格: `"理性"` \| `"感性"` \| `"幽默"` \| `"克制"` |
| `pacing` | str | 节奏: `"slow"` \| `"normal"` \| `"fast"` |
| `risk_tolerance` | str | 风险容忍度: `"low"` \| `"medium"` \| `"high"` |
| `confidence` | float | 置信度 (0-1) |

---

### 2.4 BaseReplyGenerator - 回复生成器

```python
class BaseReplyGenerator(ABC):
    @abstractmethod
    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult:
        ...
```

**输入 (ReplyGenerationInput):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `prompt` | str | 生成提示词 |
| `quality` | str | 质量等级: `"cheap"` \| `"normal"` \| `"premium"` |
| `context` | ContextResult | 上下文结果 |
| `scene` | SceneAnalysisResult | 场景分析结果 |
| `persona` | PersonaSnapshot | 用户画像 |

**输出 (LLMResult):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `text` | str | 生成的文本 |
| `provider` | str | LLM 提供商 |
| `model` | str | 模型名称 |
| `input_tokens` | int | 输入 token 数 |
| `output_tokens` | int | 输出 token 数 |
| `cost_usd` | float | 调用成本 (USD) |

---

### 2.5 BaseIntimacyChecker - 亲密度检查器

```python
class BaseIntimacyChecker(ABC):
    @abstractmethod
    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult:
        ...
```

**输入 (IntimacyCheckInput):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `reply_text` | str | 待检查的回复文本 |
| `intimacy_level` | int | 当前亲密度等级 (1-5) |
| `persona` | PersonaSnapshot | 用户画像 |

**输出 (IntimacyCheckResult):**
| 字段 | 类型 | 描述 |
|------|------|------|
| `passed` | bool | 是否通过检查 |
| `score` | float | 评分 (0-1) |
| `reason` | str \| None | 未通过原因 |

---

## 3. 数据模型

### 3.1 Message - 消息

```python
class Message(BaseModel):
    id: str
    speaker: Literal["user", "target"]
    content: str
    timestamp: datetime
```

### 3.2 EmotionSummary - 情绪摘要

```python
class EmotionSummary(BaseModel):
    trend: Literal["positive", "negative", "neutral"]
    intensity: float  # 0-1
    recent_emotions: list[str]
```

### 3.3 LLMCallRecord - LLM 调用记录

```python
class LLMCallRecord(BaseModel):
    user_id: str
    task_type: Literal["scene", "persona", "generation", "qc"]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    created_at: datetime
```

---

## 4. 使用示例

### 4.1 启动服务

```bash
# 激活虚拟环境
.venv\Scripts\activate.ps1

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 cURL 调用

```bash
# 健康检查
curl http://localhost:8000/health

# 生成回复
curl -X POST http://localhost:8000/api/v1/generate/reply \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "target_id": "target456",
    "conversation_id": "conv789",
    "quality": "normal"
  }'
```

### 4.3 Python 调用

```python
import httpx

async def generate_reply():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/generate/reply",
            json={
                "user_id": "user123",
                "target_id": "target456",
                "conversation_id": "conv789",
                "quality": "normal",
            }
        )
        return response.json()
```

### 4.4 实现自定义子模块

```python
from app.services.base import BaseSceneAnalyzer
from app.models.schemas import SceneAnalysisInput, SceneAnalysisResult

class MySceneAnalyzer(BaseSceneAnalyzer):
    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        # 实现场景分析逻辑
        return SceneAnalysisResult(
            scene="推进",
            intimacy_level=3,
            risk_flags=[]
        )
```

---

## 5. 配置说明

主要配置项通过环境变量或 `.env` 文件设置：

| 环境变量 | 默认值 | 描述 |
|----------|--------|------|
| `DEBUG` | `false` | 调试模式 |
| `LLM_DEFAULT_MODEL` | `gpt-4` | 默认 LLM 模型 |
| `LLM_FALLBACK_MODEL` | `gpt-3.5-turbo` | 回退模型 |
| `ORCHESTRATOR_MAX_RETRIES` | `3` | 最大重试次数 |
| `ORCHESTRATOR_TIMEOUT_SECONDS` | `30.0` | 超时时间 |
| `BILLING_COST_LIMIT_USD` | `0.1` | 单次请求成本上限 |
| `BILLING_DEFAULT_USER_QUOTA_USD` | `10.0` | 用户默认额度 |
| `DB_URL` | `sqlite+aiosqlite:///./conversation.db` | 数据库连接 |
