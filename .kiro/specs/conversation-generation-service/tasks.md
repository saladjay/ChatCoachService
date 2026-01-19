# Implementation Plan: Conversation Generation Service

## Overview

基于 FastAPI 构建对话生成服务框架，采用模块化设计，通过 Orchestrator 编排各子模块调用。LLM Adapter 和 UserProfile 已实现，其他子模块提供抽象接口和 Mock 实现。

## Tasks

- [x] 1. 项目结构和基础配置
  - [x] 1.1 创建项目目录结构
    - 创建 `app/` 目录及子目录：`api/`, `services/`, `models/`, `core/`, `db/`
    - _Requirements: 7.1_
  - [x] 1.2 配置 Pydantic Settings 和环境变量
    - 创建 `app/core/config.py` 配置类
    - 支持从环境变量和 `.env` 文件加载配置
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  - [x] 1.3 创建 FastAPI 应用入口
    - 创建 `app/main.py` 初始化 FastAPI 应用
    - 配置 CORS、异常处理器
    - _Requirements: 1.1_

- [x] 2. 数据模型定义
  - [x] 2.1 创建核心业务模型
    - 创建 `app/models/schemas.py` 定义 Pydantic 模型
    - 包含 Message, EmotionSummary, PersonaSnapshot 等
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [x] 2.2 创建 API 请求响应模型
    - 创建 `app/models/api.py` 定义 GenerateReplyRequest, GenerateReplyResponse
    - _Requirements: 1.2, 1.4_
  - [x] 2.3 创建数据库 ORM 模型
    - 创建 `app/db/models.py` 定义 SQLAlchemy 模型
    - 包含 scene_analysis_log, persona_snapshot, llm_call_log, intimacy_check_log, generation_result
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 3. 子模块抽象接口定义
  - [x] 3.1 创建子模块抽象基类
    - 创建 `app/services/base.py` 定义所有子模块的抽象接口
    - BaseContextBuilder, BaseSceneAnalyzer, BasePersonaInferencer, BaseReplyGenerator, BaseIntimacyChecker
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [x] 3.2 创建 Mock 实现
    - 创建 `app/services/mocks.py` 为每个子模块提供 Mock 实现
    - Mock 实现返回合理的默认值
    - _Requirements: 7.4_

- [x] 4. 核心服务实现
  - [x] 4.1 实现 BillingService
    - 创建 `app/services/billing.py`
    - 实现 record_call, get_total_cost, check_quota 方法
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [ ]* 4.2 编写 BillingService 属性测试
    - **Property 8: Billing Record Completeness**
    - **Validates: Requirements 5.1, 5.2**
  - [x] 4.3 实现 Orchestrator
    - 创建 `app/services/orchestrator.py`
    - 实现 generate_reply 方法，编排各子模块调用
    - 实现重试逻辑和失败回退
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 4.5_
  - [x] 4.4 编写 Orchestrator 属性测试

    - **Property 3: Service Invocation Order**
    - **Property 4: Retry Limit Enforcement**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [x] 5. 依赖注入容器
  - [x] 5.1 实现 ServiceContainer
    - 创建 `app/core/container.py`
    - 实现服务注册和获取
    - 支持配置切换 Mock/真实实现
    - _Requirements: 7.1, 7.2, 7.3_
  - [x] 5.2 配置 FastAPI 依赖注入
    - 创建 `app/core/dependencies.py`
    - 使用 FastAPI Depends 注入服务
    - _Requirements: 7.1_

- [x] 6. API 路由实现
  - [x] 6.1 实现生成回复端点
    - 创建 `app/api/generate.py`
    - 实现 POST /api/v1/generate/reply 端点
    - 参数验证和错误处理
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x] 6.2 编写 API 验证属性测试

    - **Property 1: Request Validation Consistency**
    - **Property 2: Response Schema Completeness**
    - **Validates: Requirements 1.2, 1.3, 1.4**

- [x] 7. 数据库集成
  - [x] 7.1 配置数据库连接
    - 创建 `app/db/session.py` 配置 SQLAlchemy 异步会话
    - _Requirements: 6.1_
  - [x] 7.2 实现数据持久化服务
    - 创建 `app/services/persistence.py`
    - 实现各类日志的存储方法
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - [ ]* 7.3 编写数据持久化属性测试
    - **Property 10: Data Persistence Integrity**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [ ] 8. Checkpoint - 核心功能验证
  - 确保所有测试通过，如有问题请询问用户

- [x] 9. 错误处理和回退策略
  - [x] 9.1 实现全局异常处理器
    - 创建 `app/core/exceptions.py` 定义自定义异常
    - 在 main.py 注册异常处理器
    - _Requirements: 4.5_
  - [x] 9.2 实现回退策略
    - 创建 `app/services/fallback.py`
    - 实现保守回复模板
    - _Requirements: 4.2, 4.4_
  - [ ]* 9.3 编写异常处理属性测试
    - **Property 7: Exception Handling Consistency**
    - **Validates: Requirements 4.4, 4.5**

- [x] 10. 集成已有模块
  - [x] 10.1 集成 LLM Adapter
    - 在 ServiceContainer 中注册已有的 LLM Adapter
    - 确保 Orchestrator 正确调用
    - _Requirements: 3.3_
  - [x] 10.2 集成 UserProfile Service
    - 在 ServiceContainer 中注册已有的 UserProfile Service
    - _Requirements: 3.2_

- [x] 11. Final Checkpoint - 完整流程验证
  - 确保所有测试通过，如有问题请询问用户
  - 验证完整的生成流程可以运行

## Notes

- 标记 `*` 的任务为可选测试任务，可跳过以加快 MVP 开发
- LLM Adapter 和 UserProfile 已实现，任务 10 负责集成
- 其他子模块（Scene Analysis, Persona Inference 等）使用 Mock 实现，后续独立开发
- 每个属性测试对应设计文档中的 Correctness Property
