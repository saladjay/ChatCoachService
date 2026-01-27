# 更新日志：移除 app_type 参数

## 更新日期
2025-01-25

## 更新内容

根据反馈，从所有示例代码和文档中移除了 `app_type` 参数。

## 修改的文件

### 1. 示例代码

#### `examples/screenshot_analysis_client.py`
- ✅ 移除 `analyze_screenshot()` 方法的 `app_type` 参数
- ✅ 移除命令行参数 `--app-type`
- ✅ 移除请求构造中的 `app_type` 字段
- ✅ 移除打印输出中的应用类型信息

#### `examples/simple_screenshot_client.py`
- ✅ 移除所有请求中的 `app_type` 字段
- ✅ 更新为使用完整的 options 配置

#### `examples/demo_screenshot_flow.py`
- ✅ 移除 `analyze_screenshot()` 方法的 `app_type` 参数
- ✅ 移除所有调用中的 `app_type` 参数
- ✅ 简化场景3的应用测试（移除app_type元组元素）

### 2. 文档

#### `examples/SCREENSHOT_CLIENT_USAGE.md`
- ✅ 移除参数列表中的 `--app-type`
- ✅ 移除高级选项示例中的 `--app-type` 用法
- ✅ 更新API请求示例，移除 `app_type` 字段
- ✅ 更新配置选项表格

#### `examples/README_SCREENSHOT_CLIENT.md`
- ✅ 更新代码示例，移除 `app_type` 字段
- ✅ 更新cURL示例
- ✅ 更新配置选项表格

## 更新后的API请求格式

### 之前（包含 app_type）
```json
{
  "image_url": "https://example.com/screenshot.png",
  "session_id": "demo-001",
  "options": {
    "app_type": "wechat"
  }
}
```

### 现在（不包含 app_type）
```json
{
  "image_url": "https://example.com/screenshot.png",
  "session_id": "demo-001",
  "options": {
    "need_nickname": true,
    "need_sender": true,
    "force_two_columns": true
  }
}
```

## 命令行使用变化

### 之前
```bash
python examples/screenshot_analysis_client.py \
    --image screenshot.png \
    --mode analyze \
    --app-type wechat
```

### 现在
```bash
python examples/screenshot_analysis_client.py \
    --image screenshot.png \
    --mode analyze
```

## 可用的配置选项

现在只支持以下选项：

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `need_nickname` | bool | true | 是否提取昵称 |
| `need_sender` | bool | true | 是否判断发送者 |
| `force_two_columns` | bool | true | 是否强制两列布局 |

## 测试验证

所有示例脚本已测试通过：

```bash
# ✅ 演示脚本运行成功
python examples/demo_screenshot_flow.py

# ✅ 简单示例可以正常使用
python examples/simple_screenshot_client.py

# ✅ 完整客户端可以正常使用
python examples/screenshot_analysis_client.py --image test.png --mode analyze
```

## 注意事项

1. **API模型未修改**：`app/models/screenshot.py` 中的 `ParseOptions` 模型仍然包含 `app_type` 字段，但示例代码不再使用它。

2. **向后兼容**：如果API仍然接受 `app_type` 参数，旧的客户端代码仍然可以工作，但新的示例代码不再使用它。

3. **文档一致性**：所有示例和文档已更新为一致的格式，不再提及 `app_type` 参数。

## 影响范围

- ✅ 所有示例代码已更新
- ✅ 所有文档已更新
- ✅ 所有测试已验证通过
- ⚠️ API模型定义未修改（如需修改，需要更新 `app/models/screenshot.py`）

## 后续建议

如果确认 `app_type` 参数完全不需要，建议：

1. 从 `app/models/screenshot.py` 的 `ParseOptions` 模型中移除 `app_type` 字段
2. 更新相关的需求文档和设计文档
3. 更新所有测试用例
4. 更新API文档

## 相关文件

- `examples/screenshot_analysis_client.py`
- `examples/simple_screenshot_client.py`
- `examples/demo_screenshot_flow.py`
- `examples/SCREENSHOT_CLIENT_USAGE.md`
- `examples/README_SCREENSHOT_CLIENT.md`
