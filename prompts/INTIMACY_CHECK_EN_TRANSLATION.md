# Intimacy Check Prompt 英文翻译

## 更新说明

将 `intimacy_check_v2.0-compact.txt` 从中文翻译为英文，以提高 LLM 的兼容性和理解准确度。

## 翻译对比

### 中文版本 (原版)

```
[PROMPT:intimacy_check_compact_v2]
对话审核：评估回复是否超出当前关系阶段的亲密度。

阶段定义：1=陌生 2=熟人 3=朋友 4=亲密 5=羁绊

输出JSON：{"score": <0~1>}
score: 0=合适 1=越界

persona: {persona}
stage: {intimacy_stage}
text: {text}
```

### 英文版本 (新版)

```
[PROMPT:intimacy_check_compact_v2]
Review: Assess if reply exceeds current relationship stage intimacy.

Stages: 1=stranger 2=acquaintance 3=friend 4=intimate 5=bonded

Output JSON: {"score": <0~1>}
score: 0=appropriate 1=boundary-crossing

persona: {persona}
stage: {intimacy_stage}
text: {text}
```

## 翻译对照表

| 中文 | 英文 | 说明 |
|------|------|------|
| 对话审核 | Review | 简洁的动词形式 |
| 评估回复是否超出当前关系阶段的亲密度 | Assess if reply exceeds current relationship stage intimacy | 保持语义完整 |
| 阶段定义 | Stages | 简化为名词 |
| 陌生 | stranger | 陌生人阶段 |
| 熟人 | acquaintance | 熟人阶段 |
| 朋友 | friend | 朋友阶段 |
| 亲密 | intimate | 亲密阶段 |
| 羁绊 | bonded | 深度羁绊阶段 |
| 输出JSON | Output JSON | 直译 |
| 合适 | appropriate | 恰当的、合适的 |
| 越界 | boundary-crossing | 跨越边界 |

## 翻译原则

1. **保持简洁**: 英文版本同样保持 compact 风格
2. **语义准确**: 确保 LLM 能正确理解任务
3. **术语一致**: 使用标准的关系阶段术语
4. **格式统一**: 保持与其他英文 prompt 的格式一致

## Token 对比

| 版本 | 语言 | Token 估算 | 说明 |
|------|------|-----------|------|
| V1.0 | 中文 | ~150 | 原始详细版本 |
| V2.0 (旧) | 中文 | ~60 | 压缩版本 |
| V2.0 (新) | 英文 | ~60 | 英文压缩版本 |

**注**: 英文版本的 token 数量与中文版本相近，因为：
- 英文单词通常比中文字符占用更多 token
- 但英文更简洁，减少了一些冗余表达
- 最终 token 数量基本持平

## 为什么使用英文？

### 优势

1. **更好的 LLM 兼容性**
   - 大多数 LLM 在英文上训练更充分
   - 英文指令理解更准确
   - 减少歧义和误解

2. **与其他 prompt 一致**
   - 系统中其他 prompt (context_summary, scenario_analysis, reply_generation) 都是英文
   - 统一的语言风格更易维护

3. **国际化支持**
   - 如果未来需要支持其他语言的用户，英文 prompt 更通用
   - 便于团队协作（国际团队）

4. **调试和日志**
   - 英文日志更易于搜索和分析
   - 与代码注释和文档保持一致

### 可能的劣势

1. **中文语境理解**
   - 如果检测的是中文对话，可能需要 LLM 在中英文之间切换
   - 但现代 LLM 通常能很好地处理这种情况

2. **Token 效率**
   - 英文单词可能比中文字符占用更多 token
   - 但通过简洁的表达可以抵消这个差异

## 测试建议

### 1. 准确度测试

使用相同的测试用例，对比中英文版本的检测结果：

```python
test_cases = [
    {
        "text": "你好，很高兴认识你",
        "stage": 1,  # stranger
        "expected_score": 0.0  # appropriate
    },
    {
        "text": "宝贝，我好想你",
        "stage": 1,  # stranger
        "expected_score": 0.9  # boundary-crossing
    },
    # ... more test cases
]
```

### 2. 性能测试

对比两个版本的：
- 响应时间
- Token 使用量
- 成本

### 3. A/B 测试

在生产环境中：
- 50% 流量使用中文版本
- 50% 流量使用英文版本
- 对比准确率和用户反馈

## 更新的文件

### 1. Prompt 文件

- ✅ `prompts/versions/intimacy_check_v2.0-compact.txt` - 更新为英文
- ✅ `prompts/active/intimacy_check.txt` - 更新为英文

### 2. 代码文件

- ✅ `app/services/intimacy_checker_impl.py` - 更新 fallback prompt 为英文

### 3. 元数据文件

- ✅ `prompts/metadata/intimacy_check_v2.0-compact.json` - 更新语言标记为 `en`

### 4. 文档文件

- ✅ `prompts/INTIMACY_CHECK_EN_TRANSLATION.md` - 本文件

## 回滚方案

如果英文版本效果不佳，可以快速回滚到中文版本：

### 方法 1: 手动回滚

```bash
# 恢复中文版本
cat > prompts/versions/intimacy_check_v2.0-compact.txt << 'EOF'
[PROMPT:intimacy_check_compact_v2]
对话审核：评估回复是否超出当前关系阶段的亲密度。

阶段定义：1=陌生 2=熟人 3=朋友 4=亲密 5=羁绊

输出JSON：{"score": <0~1>}
score: 0=合适 1=越界

persona: {persona}
stage: {intimacy_stage}
text: {text}
EOF

# 同步到 active
cp prompts/versions/intimacy_check_v2.0-compact.txt prompts/active/intimacy_check.txt
```

### 方法 2: Git 回滚

```bash
# 查看历史
git log --oneline prompts/versions/intimacy_check_v2.0-compact.txt

# 回滚到特定提交
git checkout <commit-hash> -- prompts/versions/intimacy_check_v2.0-compact.txt
git checkout <commit-hash> -- prompts/active/intimacy_check.txt
```

### 方法 3: 创建中文版本

如果需要同时保留两个版本：

```bash
# 创建 v2.1-compact-zh 版本（中文）
# 创建 v2.2-compact-en 版本（英文）
# 根据需要切换
```

## 验证

运行验证脚本确认更新成功：

```bash
python scripts/verify_intimacy_prompt.py
```

预期输出：
- ✅ 所有文件存在
- ✅ Token 估算正确 (~60)
- ✅ 语言标记为 `en`
- ✅ 代码集成正常

## 后续工作

### 短期 (1 周内)

1. ✅ 完成翻译
2. ✅ 更新文档
3. ⏳ 进行准确度测试
4. ⏳ 收集初步反馈

### 中期 (1 个月内)

5. ⏳ A/B 测试对比
6. ⏳ 性能和成本分析
7. ⏳ 根据结果决定是否保留英文版本

### 长期 (3 个月内)

8. ⏳ 考虑多语言支持
9. ⏳ 优化 prompt 以进一步提高准确度
10. ⏳ 探索更高效的检测方法

## 相关文档

- [INTIMACY_CHECK_PROMPT_MANAGEMENT.md](INTIMACY_CHECK_PROMPT_MANAGEMENT.md) - 管理文档
- [INTIMACY_PROMPT_OPTIMIZATION_SUMMARY.md](../INTIMACY_PROMPT_OPTIMIZATION_SUMMARY.md) - 优化总结
- [INTIMACY_LLM_CHECK_USAGE_ANALYSIS.md](../INTIMACY_LLM_CHECK_USAGE_ANALYSIS.md) - 使用分析

---

*翻译完成时间: 2026-01-22*
*状态: ✅ 已完成*
*语言: 中文 → 英文*
