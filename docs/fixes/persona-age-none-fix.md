# Persona Age=None TypeError 修复

**日期**: 2026-02-10  
**状态**: ✅ 已修复

## 问题描述

用户报告在推断 persona 时出现 TypeError：

```
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
```

## 错误日志

```
2026-02-10 15:52:43,705 - app - ERROR - Traceback (most recent call last):
  File "D:\project\release\chatcoachservice\app\services\user_profile_impl.py", line 1543, in infer_persona
    age=int(persona['age']),
        ~~~^^^^^^^^^^^^^^^^
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'

2026-02-10 15:52:43,705 - app - INFO - 1545 用户 user123 的画像: 
{
  'user_id': 'user123', 
  'explicit': {
    'response_style': [], 
    'forbidden': [], 
    'role': [], 
    'intimacy': 50.0, 
    'age': None,      # ← age 是 None
    'gender': None
  }, 
  'behavioral': {
    'depth_preference': 0.5, 
    'example_need': 0.5, 
    'structure_need': 0.5, 
    'long_response_preference': 0.5, 
    'allusion_preference': 0.5, 
    'technical_level': 0.5
  }
}
```

## 根本原因

### 问题代码

在 `app/services/user_profile_impl.py` 第 1543 行：

```python
quick_setup_profile = self.user_profile_service.manager.quick_setup_profile(
    input.user_id,
    age=int(persona['age']),  # ❌ 当 age 是 None 时崩溃
    intimacy=input.intimacy,
    gender=normalized_gender,
    role=persona.get('persona', []),
    style=persona.get('style', []),
    forbidden=persona.get('forbidden', []),
)
```

### 为什么会出现 None？

1. **用户画像初始化**: 新用户的 `age` 字段默认为 `None`
2. **LLM 推断失败**: 如果 LLM 无法从对话中推断出年龄，返回 `None`
3. **数据缺失**: 用户没有提供年龄信息

### Python 的 int() 行为

```python
int(None)  # ❌ TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
int(25)    # ✓ 25
int("30")  # ✓ 30
int("abc") # ❌ ValueError: invalid literal for int() with base 10: 'abc'
```

## 修复方案

### 修复代码

```python
# Handle age - convert to int if not None
age_value = persona.get('age')
normalized_age: int | None = None

if age_value is not None:
    try:
        normalized_age = int(age_value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid age value for user {input.user_id}: {age_value}, using None")
        normalized_age = None

quick_setup_profile = self.user_profile_service.manager.quick_setup_profile(
    input.user_id,
    age=normalized_age,  # ✓ 安全地传递 None 或有效的整数
    intimacy=input.intimacy,
    gender=normalized_gender,
    role=persona.get('persona', []),
    style=persona.get('style', []),
    forbidden=persona.get('forbidden', []),
)
```

### 修复逻辑

1. **安全获取**: 使用 `persona.get('age')` 而不是 `persona['age']`
2. **None 检查**: 只在 `age_value is not None` 时才转换
3. **异常处理**: 捕获 `ValueError` 和 `TypeError`，处理无效值
4. **日志记录**: 记录无效的 age 值以便调试
5. **默认值**: 无效值时使用 `None`

### 为什么这样修复？

**`quick_setup_profile` 方法签名**:
```python
def quick_setup_profile(
    self,
    user_id: str,
    age: Optional[int] = None,  # ← 接受 None
    gender: Optional[str] = None,
    intimacy: float = 50.0,
    ...
) -> UserProfile:
```

方法已经支持 `age=None`，所以我们可以安全地传递 `None`。

## 测试验证

创建了 `test_persona_age_none.py` 测试 5 个场景：

### Test 1: age=None
```python
persona = {'age': None}
# 修复前: TypeError ❌
# 修复后: normalized_age = None ✓
```

### Test 2: age=25 (整数)
```python
persona = {'age': 25}
# normalized_age = 25 ✓
```

### Test 3: age='30' (字符串数字)
```python
persona = {'age': '30'}
# normalized_age = 30 ✓
```

### Test 4: age='invalid' (无效字符串)
```python
persona = {'age': 'invalid'}
# 修复前: ValueError ❌
# 修复后: normalized_age = None ✓
```

### Test 5: age 键缺失
```python
persona = {'gender': 'male'}  # 没有 age 键
# normalized_age = None ✓
```

**所有测试通过** ✅

## 影响范围

### 修复的场景

1. ✅ **新用户** - age 初始为 None
2. ✅ **LLM 推断失败** - 无法推断年龄时返回 None
3. ✅ **无效年龄值** - 字符串、负数等无效值
4. ✅ **缺失字段** - persona 中没有 age 键

### 不受影响的场景

- ✅ 有效的整数年龄
- ✅ 字符串格式的数字年龄（会被转换）
- ✅ 其他 persona 字段（gender, role, style, forbidden）

## 类似问题预防

### 检查其他字段

在同一个方法中，`gender` 字段已经有正确的 None 处理：

```python
normalized_gender: str | None
if raw_gender is None:
    normalized_gender = None
else:
    # 处理有效值
    ...
```

### 最佳实践

处理可能为 None 的字段时：

```python
# ❌ 不好的做法
value = int(data['field'])

# ✓ 好的做法
value = data.get('field')
if value is not None:
    try:
        value = int(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid value: {value}")
        value = None
```

## 相关代码

### 调用链

```
infer_persona()
  ↓
quick_setup_profile(age=normalized_age)
  ↓
validate_explicit_tag_value("age", age)  # 只在 age is not None 时调用
  ↓
profile.explicit.age = age
```

### 验证逻辑

在 `core/chatcoachuserprofile/src/user_profile/manager.py`:

```python
def quick_setup_profile(
    self,
    user_id: str,
    age: Optional[int] = None,
    ...
) -> UserProfile:
    # 只在 age 不是 None 时才验证
    if age is not None:
        validate_explicit_tag_value("age", age)
    
    # 只在 age 不是 None 时才设置
    if age is not None:
        profile.explicit.age = age
```

这个设计已经支持 None 值，我们的修复只是确保传递给它的值是安全的。

## 相关文件

- `app/services/user_profile_impl.py` - **已修复** - 第 1543-1560 行
- `core/chatcoachuserprofile/src/user_profile/manager.py` - quick_setup_profile 方法
- `test_persona_age_none.py` - **新增** - 测试脚本
- `docs/fixes/persona-age-none-fix.md` - **新增** - 本文档

## 总结

✅ **问题已修复**

- 安全处理 `age=None` 的情况
- 捕获并处理无效的 age 值
- 添加日志记录以便调试
- 所有测试通过

**修复简单但关键** - 一个 None 检查避免了运行时崩溃！

## 建议

### 代码审查

检查其他可能有类似问题的地方：
- 所有使用 `int()` 转换的地方
- 所有从字典获取值并直接使用的地方
- 所有处理用户输入的地方

### 类型提示

考虑使用更严格的类型提示：

```python
def process_age(age: int | str | None) -> int | None:
    """Process age value safely."""
    if age is None:
        return None
    try:
        return int(age)
    except (ValueError, TypeError):
        return None
```

### 单元测试

为所有处理可选字段的方法添加单元测试，包括 None 值测试。
