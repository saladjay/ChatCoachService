# LLM 竞速策略文档

## 概述

本目录包含 LLM 竞速策略的完整文档，包括策略说明、后台缓存、迁移指南和验证报告。

## 核心原则

**先到先得（First Valid Wins）**
- 同时调用 multimodal 和 premium 两个模型
- 哪个先返回有效结果就用哪个
- 不等待较慢的模型
- Premium 结果在后台缓存供下次使用

## 文档列表

### [RACE_STRATEGY.md](RACE_STRATEGY.md)
**竞速策略完整说明**

详细介绍竞速策略的工作原理、场景分析、性能对比和监控指标。

**关键内容**：
- 核心原则和详细逻辑
- 5个典型场景分析
- 与旧方案的对比
- 性能提升数据（30-40%）
- 后台缓存机制
- 代码位置和监控指标

**适合**：开发者、架构师

---

### [BACKGROUND_CACHING.md](BACKGROUND_CACHING.md)
**后台缓存解决方案**

解决 Premium 结果在响应返回后如何缓存的问题。

**关键内容**：
- 问题描述（request 对象失效）
- 3种解决方案对比
- 当前实现详解
- 异常处理策略
- 测试场景
- 性能影响分析

**适合**：开发者、运维人员

---

### [MIGRATION.md](MIGRATION.md)
**从旧策略迁移指南**

记录从"总是等待 Premium"策略到"先到先得"策略的变更。

**关键内容**：
- 新旧策略对比
- 代码变更说明
- 4个使用场景
- 日志输出格式
- 性能和成本影响
- 回滚方案

**适合**：维护人员、项目经理

---

### [VERIFICATION.md](VERIFICATION.md)
**实现验证报告**

完整的测试验证报告，证明实现正确性。

**关键内容**：
- 实现总结
- 核心组件代码
- 7个测试场景（全部通过）
- Test 6 详细验证（关键测试）
- 性能对比数据
- 配置说明

**适合**：QA、技术评审

---

## 快速开始

### 1. 理解策略
阅读 [RACE_STRATEGY.md](RACE_STRATEGY.md) 了解核心原理

### 2. 查看实现
阅读 [BACKGROUND_CACHING.md](BACKGROUND_CACHING.md) 了解技术细节

### 3. 验证测试
查看 [VERIFICATION.md](VERIFICATION.md) 确认实现正确

### 4. 迁移参考
如需从旧版本迁移，参考 [MIGRATION.md](MIGRATION.md)

## 性能数据

| 场景 | 旧策略 | 新策略 | 提升 |
|------|--------|--------|------|
| Premium 先完成 (3s) | 3s | 3s | 0% |
| Multimodal 先完成 (2s) | 4s | 2s | **50%** |
| Premium 失败 (2s) | 4s | 2s | **50%** |

**平均提升**: 约 **30-40%** 响应时间减少

## 配置

```bash
# 竞速策略行为（已废弃，总是使用"先到先得"）
# DEBUG_RACE_WAIT_ALL=false

# 日志控制
DEBUG_LOG_RACE_STRATEGY=true           # 记录竞速详情
DEBUG_LOG_MERGE_STEP_EXTRACTION=true   # 记录对话提取
```

## 相关资源

- **测试代码**: [../../tests/test_race_strategy.py](../../tests/test_race_strategy.py)
- **测试文档**: [../../tests/TEST_RACE_STRATEGY_README.md](../../tests/TEST_RACE_STRATEGY_README.md)
- **实现代码**: 
  - `app/services/screenshot_parser.py` - 竞速逻辑
  - `app/services/orchestrator.py` - 后台缓存

## 问题排查

### 响应时间没有提升
1. 检查日志确认竞速策略是否生效
2. 查看两个模型的完成时间
3. 确认 multimodal 模型配置正确

### 后台缓存失败
1. 检查日志中的 "Background: Failed to cache" 警告
2. 确认 cache service 可用
3. 查看 [BACKGROUND_CACHING.md](BACKGROUND_CACHING.md) 的异常处理部分

## 贡献

如需更新文档：
1. 保持文档同步更新
2. 更新性能数据时提供测试证据
3. 添加新场景时更新所有相关文档
