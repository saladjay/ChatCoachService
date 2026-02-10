# Bug 修复和优化文档

本目录包含所有重要的 bug 修复和系统优化的文档。

## 最新优化（2026-02-10）

### [缓存和后台任务优化](./cache-and-background-task-optimization.md)
完整的缓存日志增强和后台任务管理系统优化指南。

**包含内容**：
- ✅ 缓存日志增强 - 显示模型和策略信息
- ✅ Premium 后台任务修复 - 修复 3 个关键 bug
- ✅ 后台任务管理系统 - 自动追踪和清理
- ✅ 超时保护 - 防止任务无限等待
- ✅ Premium 日志增强 - 完整的执行日志

**状态**：✅ 已完成并测试，可以立即部署

### [Premium to_results 方法修复](./premium-to-results-fix.md)
修复 Premium 后台任务调用不存在的 `to_results()` 方法的问题。

**问题**：`'MergeStepAdapter' object has no attribute 'to_results'`

**修复**：使用正确的 `to_context_result()` 和 `to_scene_analysis_result()` 方法

**状态**：✅ 已修复

### [边界框坐标缩小问题修复](./bbox-coordinate-issue.md)
修复 LLM 返回的边界框坐标尺度不一致导致标注图片中矩形框缩小的问题。

**问题**：标注图片中的矩形框比实际对话气泡小，坐标超出图片边界

**根本原因**：LLM 返回的坐标可能是归一化的（0-1000 范围），但代码将其视为像素坐标

**修复**：在 `MergeStepAdapter` 中添加自动坐标尺度检测和归一化
- 支持像素坐标、0-1 归一化、0-1000 归一化三种格式
- 两遍处理：先检测尺度，再统一归一化
- 添加验证和警告日志

**状态**：✅ 已修复并测试

### [Merge Step v3.0 Prompt 兼容性](./merge-step-v3-compatibility.md)
确保代码完全兼容新的 merge_step v3.0 prompt，同时保持向后兼容性。

**v3.0 新特性**：
- 新增 `image_metadata` 字段（包含原始图片尺寸）
- 强化坐标要求（必须是像素值，不能是归一化尺度）
- 坐标验证规则（整数，x2>x1, y2>y1）

**代码更新**：
- 验证逻辑支持 v3.0 的 image_metadata
- 利用 LLM 报告的尺寸验证坐标
- 改进警告信息（区分 v2.0 和 v3.0 行为）
- 坐标整数化

**兼容性**：
- ✅ v2.0 prompt - 完全兼容
- ✅ v3.0 prompt - 完全兼容
- ✅ 自动检测和适配

**状态**：✅ 已完成并测试

### [Premium 缓存 Resource=None 错误修复](./premium-cache-resource-none-fix.md)
修复当 `request.resource` 为 `None` 时导致的 Redis 编码错误。

**问题**：`'NoneType' object has no attribute 'encode'`

**根本原因**：
- `request.resource` 是 `Optional[str]`，默认值为 `None`
- Redis 的 `hset` 操作不接受 `None` 值
- 代码直接使用 `request.resource` 而没有处理 `None`

**修复**：
- 后台任务缓存：`resource = request.resource or ""`
- 同步缓存：修复不存在的 `_cache_payload` 方法，使用正确的 `cache_service.append_event()`

**状态**：✅ 已修复并测试

---

## 其他修复

### [坐标归一化修复](./COORDINATE_NORMALIZATION.md)
修复截图解析中的坐标归一化问题。

### [Target ID 修复](./TARGET_ID.md)
修复 Target ID 相关的问题。

### [Vision API Provider 修复](./VISION_API_PROVIDER.md)
修复 Vision API Provider 的问题。

---

## 文档组织

所有修复和优化文档都按照以下结构组织：

```
docs/
├── fixes/                          # Bug 修复和优化
│   ├── README.md                   # 本文件
│   ├── cache-and-background-task-optimization.md
│   ├── premium-to-results-fix.md
│   ├── bbox-coordinate-issue.md
│   ├── merge-step-v3-compatibility.md
│   ├── premium-cache-resource-none-fix.md  # NEW
│   └── ...
├── race-strategy/                  # 竞速策略相关
│   ├── CACHE_BEHAVIOR.md          # 缓存行为分析
│   └── ...
├── guides/                         # 使用指南
├── api/                           # API 文档
├── configuration/                 # 配置说明
└── ...
```

---

## 相关测试

所有优化都有对应的测试脚本：

- `test_cache_model_logging.py` - 缓存日志格式测试
- `test_premium_background_task.py` - 后台任务行为测试
- `test_background_task_management.py` - 任务管理系统测试
- `test_premium_logging.py` - Premium 日志测试
- `test_bbox_normalization.py` - 边界框坐标归一化测试
- `test_premium_cache_resource_none.py` - Resource=None 处理测试

---

## 快速链接

- [缓存和后台任务优化](./cache-and-background-task-optimization.md)
- [Premium to_results 修复](./premium-to-results-fix.md)
- [边界框坐标修复](./bbox-coordinate-issue.md)
- [Merge Step v3.0 兼容性](./merge-step-v3-compatibility.md)
- [Premium 缓存 Resource=None 修复](./premium-cache-resource-none-fix.md)
- [竞速策略缓存行为](../race-strategy/CACHE_BEHAVIOR.md)
- [测试脚本](../../test_cache_model_logging.py)
