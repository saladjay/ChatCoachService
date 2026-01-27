太好了，这个需求本身就是你当前整套「聊天截图结构化 → 对话理解 → 生成策略」链路里非常核心的一步。我会按**工程可落地 + 后续可扩展 + 与你现有体系兼容**的方式，给你一份**初始版本需求文档（PRD + 技术设计混合版）**，你可以直接交给后端或自己拆任务实现。

---

## 一、背景与目标（Background & Goal）

### 1.1 背景

当前系统已经具备：

* 本地视觉算法版本的 `ChatLayoutDetector`
* 基于文本框 / center_x / 跨截图一致性 的规则与聚类识别
* 后续有内容审核、亲密度分析、策略生成等服务

但在以下场景存在明显短板：

* 不同 App、不同 UI 版本气泡结构差异极大
* 表情包、引用、系统消息难以通过纯视觉规则稳定处理
* 多截图拼接、昵称识别、对话对象识别复杂

因此需要引入：

> **多模态大模型作为“结构化解析器”**，直接从截图中输出：
>
> * 每个聊天气泡的坐标
> * 内容
> * 归属发送人
> * 沟通对象昵称

并且返回格式**严格对齐你当前下一轮接口协议**，可以无缝进入你后续的：

* 布局一致性学习
* 亲密度分析
* 策略路由
* Prompt Assembler

---

## 二、整体需求概述（High Level Requirement）

### 2.1 核心能力

新增一个 **POST 接口**，用于：

1. 接收：

   * 图片 URL（公网可访问）
   * 解析参数（可选）

2. 服务端完成：

   * 下载图片
   * 构造多模态 Prompt
   * 调用多模态大模型 API
   * 解析模型返回结果
   * 校验 / 标准化返回结构

3. 输出：

   * 严格符合**当前下一轮接口所需格式**的结构化结果

---

## 三、接口设计（API Design）

### 3.1 接口基本信息

```
POST /api/chat_screenshot/parse
```

用途：

> 对聊天截图进行结构化解析，输出气泡级结构数据

---

### 3.2 请求参数（Request）

#### 3.2.1 Body（JSON）

```json
{
  "image_url": "https://xxx.com/chat_screenshot.png",
  "session_id": "optional-session-id",
  "options": {
    "need_nickname": true,
    "need_sender": true,
    "force_two_columns": true,
    "app_type": "unknown"
  }
}
```

#### 参数说明

| 字段                        | 类型     | 必填 | 说明                                    |
| ------------------------- | ------ | -- | ------------------------------------- |
| image_url                 | string | 是  | 聊天截图公网可访问 URL                         |
| session_id                | string | 否  | 业务会话ID，用于链路追踪                         |
| options.need_nickname     | bool   | 否  | 是否强制识别沟通对象昵称                          |
| options.need_sender       | bool   | 否  | 是否必须输出发送人归属                           |
| options.force_two_columns | bool   | 否  | 是否强制假设左右两列布局                          |
| options.app_type          | string | 否  | 已知App类型（wechat/line/whatsapp/unknown） |

---

## 四、返回结构设计（Response Schema）

> ⚠️ 这一部分是**最关键**的：
> 我会设计成**高度贴合你后续「气泡归属 + 对话建模」链路可直接消费的结构**。

### 4.1 总体结构

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "image_meta": {
      "width": 1080,
      "height": 2400
    },
    "participants": {
      "self": {
        "id": "user",
        "nickname": "我"
      },
      "other": {
        "id": "talker",
        "nickname": "小美"
      }
    },
    "bubbles": [
      {
        "bubble_id": "b1",
        "bbox": {
          "x1": 120,
          "y1": 300,
          "x2": 620,
          "y2": 420
        },
        "center_x": 370,
        "center_y": 360,
        "text": "你今天下班了吗？",
        "sender": "talker",
        "column": "left",
        "confidence": 0.93
      },
      {
        "bubble_id": "b2",
        "bbox": {
          "x1": 680,
          "y1": 460,
          "x2": 1040,
          "y2": 600
        },
        "center_x": 860,
        "center_y": 530,
        "text": "刚到家，有点累。",
        "sender": "user",
        "column": "right",
        "confidence": 0.95
      }
    ],
    "layout": {
      "type": "two_columns",
      "left_role": "talker",
      "right_role": "user"
    }
  }
}
```

---

### 4.2 关键字段设计说明（与你现有体系强相关）

#### （1）participants

```json
"participants": {
  "self": { "id": "user", "nickname": "我" },
  "other": { "id": "talker", "nickname": "小美" }
}
```

用途：

* 直接供你后续 **用户画像 / 对话建模 / 亲密度计算** 使用
* nickname 可进入你 Profile 构建模块

---

#### （2）bubbles 数组（核心）

每个元素 = 一个聊天气泡的**完整结构单元**

| 字段                  | 说明            | 你后续用途      |
| ------------------- | ------------- | ---------- |
| bubble_id           | 本截图内唯一ID      | 追踪、跨截图一致性  |
| bbox                | 气泡矩形坐标        | 你已有视觉布局体系  |
| center_x / center_y | 中心点           | 你现在的列聚类逻辑  |
| text                | 文本内容          | 后续亲密度 / 策略 |
| sender              | user / talker | 对话方向建模     |
| column              | left / right  | 布局学习、纠错    |
| confidence          | 模型自信度         | 低置信度走规则兜底  |

---

#### （3）layout 区域

```json
"layout": {
  "type": "two_columns",
  "left_role": "talker",
  "right_role": "user"
}
```

这一步是为你**现有 ChatLayoutDetector + 跨截图一致性学习**预留的锚点。

---

## 五、模型 Prompt 设计（核心技术点）

这一部分是**你产品的关键资产**，我会用你现在的技术路线风格来设计。

### 5.1 System Prompt（固定模板）

```text
你是一个专门解析聊天截图结构的视觉理解助手。

你的任务是：
1. 识别图片中每一个聊天气泡的位置坐标（左上角x1,y1 右下角x2,y2）
2. 识别每个气泡中的文字内容
3. 判断每个气泡的发送人归属（user 或 talker）
4. 识别聊天对象的昵称（如果存在于顶部或气泡附近）

要求：
- 严格按我给定的 JSON 格式返回
- 所有坐标以原图像素为准
- sender 只能是 "user" 或 "talker"
- column 只能是 "left" 或 "right"
- 不要输出多余解释性文字
```

---

### 5.2 User Prompt（动态部分）

```text
请解析这张聊天截图。

已知规则：
- 左侧气泡通常属于 talker
- 右侧气泡通常属于 user
- 如果顶部存在昵称或联系人名称，请识别为 other.nickname

请输出：
- 图片尺寸
- 聊天参与者昵称
- 每个聊天气泡的坐标、文本、发送人、左右列归属

返回格式必须为以下 JSON 结构：

{ ...严格结构模板... }
```

---

## 六、服务内部流程设计（Service Flow）

### 6.1 时序流程

```
Client
  |
  | POST image_url
  v
API Server
  |
  | 下载图片
  | 构造 multimodal request
  v
Multimodal LLM
  |
  | 返回结构化 JSON
  v
API Server
  |
  | 校验 + 纠错 + 标准化
  v
Return Response
```

---

### 6.2 关键模块拆分

#### 模块 1：ImageFetcher

职责：

* 校验 URL
* 下载图片
* 获取 width / height
* 转 base64 或 file stream

---

#### 模块 2：PromptBuilder

输入：

* options
* 是否强制两列
* 是否已知 app_type

输出：

* system prompt
* user prompt
* image

---

#### 模块 3：LLM Client（多模态）

* 支持 OpenAI / Gemini / Claude Vision 可插拔
* 统一返回 raw_json

---

#### 模块 4：ResultNormalizer（非常重要）

功能：

* 校验 JSON Schema
* 修正 sender 非法值
* 自动补充 center_x / center_y
* 排序 bubbles（按 y1 asc）
* 低置信度标记

---

## 七、错误与兜底设计（Engineering Grade）

### 7.1 错误码设计

| code | 含义       |
| ---- | -------- |
| 0    | 成功       |
| 1001 | 图片下载失败   |
| 1002 | 模型调用失败   |
| 1003 | 模型返回格式非法 |
| 1004 | 关键字段缺失   |

---

### 7.2 兜底策略（与你现有规则体系强结合）

当出现以下情况：

* sender 缺失
* column 缺失
* bbox 数量异常

则：

1. 启用你已有的：

   * center_x 列聚类
   * 跨截图列一致性
2. 重新推断 sender / column
3. 标记 confidence 降低

---

## 八、与你现有系统的衔接点（非常关键）

结合你当前在做的：

* ChatLayoutDetector
* 跨截图一致性学习
* 亲密度服务
* Prompt Router

我建议你后续链路可以直接这样接：

```
Screenshot Parse API
        |
        v
Bubble Sequence (标准结构)
        |
        v
Conversation Builder
        |
        v
Intimacy Scoring Service
        |
        v
Strategy Router
        |
        v
Prompt Assembler
```

---

