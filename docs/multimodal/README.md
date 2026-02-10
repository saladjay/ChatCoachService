# 多模态配置文档

## 概述

本目录包含多模态 LLM 配置相关文档，主要涉及图片传输格式和 LLM 重构说明。

## 文档列表

### [IMAGE_FORMAT.md](IMAGE_FORMAT.md)
**图片传输格式配置**

详细说明如何配置图片传输格式（base64 vs url）。

**关键内容**：
- base64 和 url 两种格式对比
- 各 LLM 提供商兼容性
- 配置示例和使用场景
- 故障排查指南

**配置变量**：
```bash
LLM_MULTIMODAL_IMAGE_FORMAT=base64  # 推荐
LLM_MULTIMODAL_IMAGE_COMPRESS=true  # base64时压缩
```

**适合**：运维人员、开发者

---

### [LLM_REFACTOR.md](LLM_REFACTOR.md)
**多模态 LLM 重构说明**

记录多模态 LLM 功能的重构过程和架构变更。

**关键内容**：
- 重构背景和目标
- 架构变更说明
- 新旧实现对比
- 迁移指南

**适合**：架构师、维护人员

---

## 快速配置

### 推荐配置（生产环境）

```bash
# .env 文件
LLM_MULTIMODAL_IMAGE_FORMAT=base64
LLM_MULTIMODAL_IMAGE_COMPRESS=true
```

**优点**：
- ✅ 兼容所有提供商
- ✅ 图片压缩减少 token 消耗
- ✅ 不依赖外部 URL 访问

### URL 格式（特殊场景）

```bash
# .env 文件
LLM_MULTIMODAL_IMAGE_FORMAT=url
```

**使用条件**：
- 图片 URL 必须公网可访问
- 使用 OpenRouter 或 OpenAI
- 需要 LLM 处理原始高分辨率图片

**注意**：DashScope 无法访问内网 URL（192.168.x.x, 10.x.x.x）

## 提供商兼容性

| 提供商 | base64 | url | 备注 |
|--------|--------|-----|------|
| OpenRouter | ✅ | ✅ | 完全支持 |
| OpenAI | ✅ | ✅ | 完全支持 |
| Gemini | ✅ | ✅ | 完全支持 |
| DashScope | ✅ | ⚠️ | URL 必须公网可访问 |

## 常见问题

### Q: 为什么推荐 base64 格式？
A: base64 格式兼容性最好，支持图片压缩，减少 token 消耗和成本。

### Q: 什么时候使用 url 格式？
A: 当需要 LLM 处理原始高分辨率图片，且图片 URL 公网可访问时。

### Q: DashScope 报错 "URL does not appear to be valid"
A: DashScope 无法访问内网 URL，请改用 base64 格式：
```bash
LLM_MULTIMODAL_IMAGE_FORMAT=base64
```

### Q: 图片压缩会影响识别准确度吗？
A: 压缩到 800px 对大多数场景影响很小，且能显著减少成本。如需更高精度，可设置：
```bash
LLM_MULTIMODAL_IMAGE_COMPRESS=false
```

## 性能对比

### base64 格式
- **优点**：兼容性好、可压缩、不依赖外部访问
- **缺点**：需要下载和编码时间（约 100-300ms）
- **Token 消耗**：低（压缩后）
- **成本**：低

### url 格式
- **优点**：无需下载编码、响应快
- **缺点**：需要公网访问、不可压缩
- **Token 消耗**：高（原始分辨率）
- **成本**：高

## 相关资源

- **配置文件**: [../../.env.example](../../.env.example)
- **实现代码**: 
  - `app/services/screenshot_parser.py`
  - `app/services/orchestrator.py`
  - `app/services/image_fetcher.py`
- **配置类**: `app/core/config.py` - `LLMConfig`

## 测试

```bash
# 测试 base64 格式
LLM_MULTIMODAL_IMAGE_FORMAT=base64 python tests/load_test.py --url http://localhost:80 --image-url https://test-r2.zhizitech.org/test35.jpg --requests 1

# 测试 url 格式（需要公网 URL）
LLM_MULTIMODAL_IMAGE_FORMAT=url python tests/load_test.py --url http://localhost:80 --image-url https://test-r2.zhizitech.org/test35.jpg --requests 1
```

## 贡献

更新文档时：
1. 添加新提供商时更新兼容性表格
2. 记录新的配置选项
3. 更新性能对比数据
4. 添加实际使用案例
