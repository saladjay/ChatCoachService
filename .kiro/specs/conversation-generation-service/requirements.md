# Requirements Document

## Introduction

基于 FastAPI 构建对话生成子系统的整体流程服务框架。该框架负责编排各个子模块（场景分析、用户画像推理、回复生成、亲密度检查等），提供统一的 API 入口，并支持失败回退、Token 计费等功能。

LLM Adapter 和 UserProfile 模块已实现，其他子模块将作为接口预留，后续独立开发。

## Glossary

- **Orchestrator**: 流程编排服务，负责协调各子模块的调用顺序和数据流转
- **LLM_Adapter**: 统一的大语言模型调用适配器（已实现）
- **UserProfile_Service**: 用户画像服务（已实现）
- **Scene_Analysis_Service**: 场景分析服务，分析当前对话场景和亲密度等级
- **Persona_Inference_Service**: 用户画像推理服务，推断用户风格偏好
- **Reply_Generation_Service**: 回复生成服务，生成建议回复
- **Intimacy_Check_Service**: 亲密度检查服务，验证回复是否符合当前关系阶段
- **Billing_Service**: 计费服务，记录 Token 消耗和成本
- **Context_Builder**: 上下文构建器，整合历史对话、情绪趋势等信息

## Requirements

### Requirement 1: API 入口

**User Story:** As a 上层系统开发者, I want 通过统一的 API 入口请求生成对话建议, so that 可以简化集成流程。

#### Acceptance Criteria

1. THE API_Gateway SHALL 提供 POST /api/v1/generate/reply 端点接收生成请求
2. WHEN 请求到达时, THE API_Gateway SHALL 验证请求参数的完整性和格式
3. WHEN 参数验证失败时, THE API_Gateway SHALL 返回 400 错误码和详细错误信息
4. THE API_Gateway SHALL 返回包含 reply_text、confidence、intimacy_level_before、intimacy_level_after、model、provider、cost_usd 的响应

### Requirement 2: 流程编排

**User Story:** As a 系统架构师, I want 有一个中央编排器协调各子模块调用, so that 流程可控且易于维护。

#### Acceptance Criteria

1. THE Orchestrator SHALL 按顺序调用 Context_Builder → Scene_Analysis → Persona_Inference → Reply_Generation → Intimacy_Check
2. WHEN 任一子模块返回结果时, THE Orchestrator SHALL 将结果传递给下一个子模块
3. WHEN Intimacy_Check 失败时, THE Orchestrator SHALL 触发重新生成流程（最多 3 次）
4. WHEN 重试次数耗尽时, THE Orchestrator SHALL 返回保守建议或错误响应
5. THE Orchestrator SHALL 记录每个步骤的执行时间和状态

### Requirement 3: 子模块接口定义

**User Story:** As a 子模块开发者, I want 有清晰的接口定义, so that 可以独立开发各个子模块。

#### Acceptance Criteria

1. THE Scene_Analysis_Service SHALL 定义 analyze_scene(input: SceneAnalysisInput) -> SceneAnalysisResult 接口
2. THE Persona_Inference_Service SHALL 定义 infer_persona(input: PersonaInferenceInput) -> PersonaSnapshot 接口
3. THE Reply_Generation_Service SHALL 定义 generate_reply(input: ReplyGenerationInput) -> LLMResult 接口
4. THE Intimacy_Check_Service SHALL 定义 check(input: IntimacyCheckInput) -> IntimacyCheckResult 接口
5. THE Context_Builder SHALL 定义 build_context(input: ContextBuilderInput) -> ContextResult 接口

### Requirement 4: 失败回退策略

**User Story:** As a 运维人员, I want 系统具备完善的失败回退机制, so that 服务可以保持高可用性。

#### Acceptance Criteria

1. WHEN LLM 调用超时时, THE Orchestrator SHALL 切换到低级模型重试
2. WHEN Intimacy_Check 连续失败时, THE Orchestrator SHALL 降级输出保守建议
3. WHEN 成本超过配置上限时, THE Orchestrator SHALL 强制使用 cheap 模型
4. WHEN Context_Builder 构造失败时, THE Orchestrator SHALL 返回人工模板回复
5. IF 任何子模块抛出异常, THEN THE Orchestrator SHALL 记录错误日志并返回友好错误信息

### Requirement 5: Token 监控与计费

**User Story:** As a 产品经理, I want 追踪每次调用的 Token 消耗和成本, so that 可以进行成本分析和用户额度控制。

#### Acceptance Criteria

1. THE Billing_Service SHALL 记录每次 LLM 调用的 provider、model、input_tokens、output_tokens、cost_usd
2. WHEN 生成流程完成时, THE Billing_Service SHALL 汇总本次请求的总成本
3. THE Billing_Service SHALL 支持按 user_id 查询累计消耗
4. WHEN 用户额度不足时, THE Billing_Service SHALL 阻止请求并返回额度不足错误

### Requirement 6: 数据持久化

**User Story:** As a 数据分析师, I want 所有关键数据被持久化存储, so that 可以进行后续分析和审计。

#### Acceptance Criteria

1. THE Persistence_Layer SHALL 存储场景分析结果到 scene_analysis_log 表
2. THE Persistence_Layer SHALL 存储用户画像快照到 persona_snapshot 表
3. THE Persistence_Layer SHALL 存储 LLM 调用日志到 llm_call_log 表
4. THE Persistence_Layer SHALL 存储亲密度检查结果到 intimacy_check_log 表
5. THE Persistence_Layer SHALL 存储最终生成结果到 generation_result 表

### Requirement 7: 依赖注入与模块化

**User Story:** As a 开发者, I want 子模块通过依赖注入方式集成, so that 可以方便地替换实现或进行单元测试。

#### Acceptance Criteria

1. THE Framework SHALL 使用依赖注入容器管理所有服务实例
2. THE Framework SHALL 支持通过配置切换子模块的实现（真实实现 / Mock 实现）
3. THE Framework SHALL 为每个子模块提供抽象基类或协议定义
4. WHEN 子模块未实现时, THE Framework SHALL 使用 Mock 实现返回默认值

### Requirement 8: 配置管理

**User Story:** As a 运维人员, I want 通过配置文件管理系统参数, so that 可以在不修改代码的情况下调整系统行为。

#### Acceptance Criteria

1. THE Config_Manager SHALL 支持从环境变量和配置文件加载配置
2. THE Config_Manager SHALL 支持配置 LLM 模型选择策略
3. THE Config_Manager SHALL 支持配置重试次数和超时时间
4. THE Config_Manager SHALL 支持配置成本上限阈值
