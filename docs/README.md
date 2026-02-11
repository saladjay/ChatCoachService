# ChatCoach 文档索引

## 核心功能文档

### 🏁 LLM 竞速策略 ([race-strategy/](race-strategy/))
- **[RACE_STRATEGY.md](race-strategy/RACE_STRATEGY.md)** - 竞速策略完整说明（先到先得原则）
- **[BACKGROUND_CACHING.md](race-strategy/BACKGROUND_CACHING.md)** - 后台缓存解决方案
- **[CACHE_BEHAVIOR.md](race-strategy/CACHE_BEHAVIOR.md)** - 缓存行为分析（Premium 失败场景）
- **[MIGRATION.md](race-strategy/MIGRATION.md)** - 从旧策略迁移指南
- **[VERIFICATION.md](race-strategy/VERIFICATION.md)** - 实现验证报告

### 🎨 多模态配置 ([multimodal/](multimodal/))
- **[IMAGE_FORMAT.md](multimodal/IMAGE_FORMAT.md)** - 图片传输格式配置（base64/url）
- **[LLM_REFACTOR.md](multimodal/LLM_REFACTOR.md)** - 多模态 LLM 重构说明

### 🐛 调试与日志 ([debugging/](debugging/))
- **[CONFIGURATION.md](debugging/CONFIGURATION.md)** - 调试配置完整指南
- **[MERGE_STEP_LOGGING.md](debugging/MERGE_STEP_LOGGING.md)** - Merge Step 对话日志说明
- **[TIMING_LOGS.md](debugging/TIMING_LOGS.md)** - 时间日志实现
- **[TIMING_LOGS_CN.md](debugging/TIMING_LOGS_CN.md)** - 时间日志中文说明
- **[TIMING_LOGS_IMPLEMENTATION.md](debugging/TIMING_LOGS_IMPLEMENTATION.md)** - 时间日志实现细节
- **[TIMING_LOGS_QUICK_START.md](debugging/TIMING_LOGS_QUICK_START.md)** - 时间日志快速开始

### 🔧 问题修复 ([fixes/](fixes/))
- **[README.md](fixes/README.md)** - 修复文档索引
- **[cache-and-background-task-optimization.md](fixes/cache-and-background-task-optimization.md)** - 缓存和后台任务优化（2026-02-10）✅
- **[premium-to-results-fix.md](fixes/premium-to-results-fix.md)** - Premium to_results 方法修复（2026-02-10）✅
- **[COORDINATE_NORMALIZATION.md](fixes/COORDINATE_NORMALIZATION.md)** - 坐标归一化修复
- **[TARGET_ID.md](fixes/TARGET_ID.md)** - Target ID 修复
- **[VISION_API_PROVIDER.md](fixes/VISION_API_PROVIDER.md)** - Vision API Provider 修复

### ⚙️ 系统配置 ([configuration/](configuration/))
- **[SERVER_STARTUP.md](configuration/SERVER_STARTUP.md)** - 服务器启动成功
- **[SWITCH_TO_REAL_MODE.md](configuration/SWITCH_TO_REAL_MODE.md)** - 切换到真实模式
- **[intimacy_check_rules.md](configuration/intimacy_check_rules.md)** - 亲密度检查规则

### 📝 重构与总结
- **[REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md)** - 重构总结
- **[DOCUMENTATION_ORGANIZATION.md](DOCUMENTATION_ORGANIZATION.md)** - 文档整理说明

## 按主题分类

### 🏁 性能优化
1. [race-strategy/RACE_STRATEGY.md](race-strategy/RACE_STRATEGY.md) - 竞速策略（30-40% 响应时间提升）
2. [race-strategy/BACKGROUND_CACHING.md](race-strategy/BACKGROUND_CACHING.md) - 后台缓存（不阻塞响应）
3. [multimodal/IMAGE_FORMAT.md](multimodal/IMAGE_FORMAT.md) - 图片格式优化

### 🐛 调试工具
1. [debugging/CONFIGURATION.md](debugging/CONFIGURATION.md) - 调试配置总览
2. [debugging/MERGE_STEP_LOGGING.md](debugging/MERGE_STEP_LOGGING.md) - 对话提取日志
3. [debugging/TIMING_LOGS.md](debugging/TIMING_LOGS.md) - 性能时间日志

### 🔧 配置指南
1. [multimodal/IMAGE_FORMAT.md](multimodal/IMAGE_FORMAT.md) - 图片传输格式
2. [debugging/CONFIGURATION.md](debugging/CONFIGURATION.md) - 调试开关
3. [configuration/intimacy_check_rules.md](configuration/intimacy_check_rules.md) - 亲密度规则

### 📊 测试与验证
1. [race-strategy/VERIFICATION.md](race-strategy/VERIFICATION.md) - 竞速策略验证
2. [../tests/TEST_RACE_STRATEGY_README.md](../tests/TEST_RACE_STRATEGY_README.md) - 测试套件说明

## 快速开始

### 新用户必读
1. [configuration/SERVER_STARTUP.md](configuration/SERVER_STARTUP.md) - 启动服务器
2. [multimodal/IMAGE_FORMAT.md](multimodal/IMAGE_FORMAT.md) - 配置图片格式
3. [debugging/CONFIGURATION.md](debugging/CONFIGURATION.md) - 配置调试选项

### 性能调优
1. [race-strategy/RACE_STRATEGY.md](race-strategy/RACE_STRATEGY.md) - 理解竞速策略
2. [race-strategy/BACKGROUND_CACHING.md](race-strategy/BACKGROUND_CACHING.md) - 理解后台缓存
3. [debugging/TIMING_LOGS.md](debugging/TIMING_LOGS.md) - 监控性能指标

### 问题排查
1. [debugging/CONFIGURATION.md](debugging/CONFIGURATION.md) - 启用详细日志
2. [debugging/MERGE_STEP_LOGGING.md](debugging/MERGE_STEP_LOGGING.md) - 查看对话提取
3. [multimodal/IMAGE_FORMAT.md](multimodal/IMAGE_FORMAT.md) - 解决图片问题

## 环境变量速查

### 竞速策略
```bash
DEBUG_RACE_WAIT_ALL=false              # 先到先得（推荐）
DEBUG_LOG_RACE_STRATEGY=true           # 记录竞速详情
```

### 日志控制
```bash
DEBUG_LOG_MERGE_STEP_EXTRACTION=true   # 记录对话提取
DEBUG_LOG_SCREENSHOT_PARSE=true        # 记录截图解析
DEBUG_LOG_VALIDATION=false             # 记录验证详情
```

### 图片格式
```bash
LLM_MULTIMODAL_IMAGE_FORMAT=base64     # base64（推荐）或 url
LLM_MULTIMODAL_IMAGE_COMPRESS=true     # 压缩图片（base64时）
```

## 目录结构

```
docs/
├── README.md                          # 📚 文档索引（本文件）
│
├── 🏁 race-strategy/                  # 竞速策略系列
│   ├── RACE_STRATEGY.md               # 竞速策略完整说明
│   ├── BACKGROUND_CACHING.md          # 后台缓存解决方案
│   ├── MIGRATION.md                   # 策略迁移指南
│   └── VERIFICATION.md                # 实现验证报告
│
├── 🎨 multimodal/                     # 多模态配置
│   ├── IMAGE_FORMAT.md                # 图片传输格式
│   └── LLM_REFACTOR.md                # 多模态重构
│
├── 🐛 debugging/                      # 调试与日志
│   ├── CONFIGURATION.md               # 调试配置
│   ├── MERGE_STEP_LOGGING.md          # 对话日志
│   ├── TIMING_LOGS.md                 # 时间日志
│   ├── TIMING_LOGS_CN.md              # 时间日志（中文）
│   ├── TIMING_LOGS_IMPLEMENTATION.md  # 时间日志实现
│   └── TIMING_LOGS_QUICK_START.md     # 时间日志快速开始
│
├── 🔧 fixes/                          # 问题修复
│   ├── COORDINATE_NORMALIZATION.md    # 坐标归一化修复
│   ├── TARGET_ID.md                   # Target ID 修复
│   └── VISION_API_PROVIDER.md         # Vision API Provider 修复
│
├── ⚙️ configuration/                  # 系统配置
│   ├── SERVER_STARTUP.md              # 服务器启动
│   ├── SWITCH_TO_REAL_MODE.md         # 切换到真实模式
│   └── intimacy_check_rules.md        # 亲密度规则
│
├── 📁 其他目录
│   ├── api/                           # API 文档
│   ├── guides/                        # 使用指南
│   │   └── git-submodule-examples.md  # Git submodule 指南
│   ├── updates/                       # 更新记录
│   │   └── CHANGES_SUMMARY_2026-02-09.md  # 变更总结
│   ├── screenshot/                    # 截图相关
│   ├── screenshot-parser/             # 解析器文档
│   ├── setup/                         # 设置指南
│   ├── tasks/                         # 任务文档
│   └── ...                            # 其他目录
│
├── REFACTOR_SUMMARY.md                # 重构总结
└── DOCUMENTATION_ORGANIZATION.md      # 文档整理说明
```

## 贡献指南

添加新文档时：
1. 在相应目录创建 Markdown 文件
2. 更新本 README.md 的索引
3. 在文档中添加清晰的标题和示例
4. 包含配置示例和使用场景

## 版本历史

- **2026-02-10**: 添加缓存和后台任务优化文档，合并重复文档
- **2026-02-10**: 重组文档结构，按功能分类到子目录
- **2026-02-10**: 添加竞速策略文档系列
- **2026-02-09**: 更新调试配置和日志文档
- **2026-02-08**: 添加多模态图片格式文档

## 相关资源

- **测试文档**: [../tests/TEST_RACE_STRATEGY_README.md](../tests/TEST_RACE_STRATEGY_README.md)
- **示例代码**: [../examples/](../examples/)
- **配置文件**: [../.env.example](../.env.example)
- **主配置**: [../config.yaml](../config.yaml)
