from enum import Enum
__all__ = ['PREFERENCE_ANALYSIS_PROMPT', 'SCENARIO_ANALYSIS_PROMPT']

PREFERENCE_ANALYSIS_PROMPT = """分析以下对话，提取用户的沟通偏好特征。

对话内容：
{conversation}

请分析用户在对话中表现出的偏好，输出 JSON 格式：
{{
    "features": {{
        "formality": <0.0-1.0, 正式程度，1.0表示非常正式>,
        "detail_level": <0.0-1.0, 详细程度偏好，1.0表示喜欢详细回复>,
        "emotional_expression": <0.0-1.0, 情感表达程度，1.0表示情感丰富>,
        "humor_preference": <0.0-1.0, 幽默偏好，1.0表示喜欢幽默>,
        "directness": <0.0-1.0, 直接程度，1.0表示喜欢直接沟通>,
        "example_need": <0.0-1.0, 示例需求，1.0表示经常需要示例>,
        "depth_preference": <0.0-1.0, 深度偏好，1.0表示喜欢深入讨论>
    }},
    "description": "<用一句话描述用户的沟通风格偏好>"
}}

只输出 JSON，不要其他内容。"""

# LLM 场景分析的 Prompt 模板
SCENARIO_ANALYSIS_PROMPT = """你是一个对话场景分析专家。请根据以下对话历史，分析当前对话场景。

## 对话历史
{conversation}

## 分析维度

### 1. 场景风险等级 (risk_level)
- safe：陌生阶段，低容错，需要保守策略
- balanced：推进关系阶段，可以适度冒险
- risky：关系亲密，高容错，可以大胆尝试
- recovery：关系修复阶段，需要缓和策略

### 2. 关系阶段 (relationship_stage)
- stranger：陌生人，刚开始接触
- acquaintance：熟人，有一定了解
- friend：朋友，关系较好
- intimate：亲密关系

### 3. 情绪基调 (emotional_tone)
- positive：积极正面
- neutral：中性平和
- negative：消极负面
- tense：紧张对立

### 4. 推荐策略 (recommended_strategies)
根据场景选择 2-4 个合适的策略：
- Safe 策略：situational_comment(情境评论), light_humor(轻松幽默), neutral_open_question(中性开放问题), empathetic_ack(共情回应), pace_matching(节奏匹配)
- Balanced 策略：playful_tease(俏皮调侃), direct_compliment(直接赞美), emotional_resonance(情感共鸣), story_snippet(故事片段), flirt_with_escape(带退路的调情)
- Recovery 策略：tension_release(缓解紧张), boundary_respect(尊重边界), misstep_repair(失误修复), emotional_deescalation(情绪降级)

### 5. 需要回避的模式 (avoid_patterns)
列出当前场景下应该避免的沟通模式，如：
- validation_seeking(寻求认可)
- over_explaining(过度解释)
- pressure_tactics(施压策略)
- topic_forcing(强行转话题)

## 输出格式
请严格按照以下 JSON 格式输出，不要包含其他内容：
{{
    "risk_level": "safe|balanced|risky|recovery",
    "relationship_stage": "stranger|acquaintance|friend|intimate",
    "emotional_tone": "positive|neutral|negative|tense",
    "recommended_strategies": ["策略1", "策略2"],
    "avoid_patterns": ["需要回避的模式"],
    "confidence": 0.0-1.0,
    "analysis": "简要分析说明"
}}
"""



SCENARIO_PROMPT = """你是一个专业的社交互动分析师，擅长识别和分类对话中使用的沟通策略。请根据以下分类体系，分析对话中user所使用的策略类型以及当前对话的适合的三个策略。
## 策略分类体系
### 安全/低风险策略 (Safe/Low Risk)
**适用场景：陌生阶段、低容错、保守互动**
**核心特征：建立安全感、渐进熟悉、避免越界**
|策略代码 (Strategy Code) |定义 (Definition)| 典型表现 (Typical Manifestation)|
|situational_comment|评论当前共同经历或情境|"今天天气真好","这个活动看起来不错"|
|light_humor|轻松、不自嘲的幽默|对情境的有趣观察，不过分玩笑|
|neutral_open_question|开放但不涉及隐私的问题|"你周末一般做什么？","喜欢什么类型的电影？"|
|shared_experience_probe|寻找双方共同点|"我也去过那里","我也有类似的经历"|
|empathetic_ack|承认对方情绪|"听起来挺烦的","能理解你的感受"|
|pace_matching|匹配对方回复长度和频率|相似的消息长度，适当的回复间隔|
|soft_callback|轻微提及对方之前话题|"你刚才提到的那个...","关于你说的..."|
|curiosity_frame|表达好奇而非审问|"我很好奇...","能多说说吗？"|
|observational_flirt|含蓄的观察性赞美|"你的笑容很温暖","今天穿得很有品味"|
|appreciation_without_hook|不索取回应的赞美|"这个观点很棒"，说完即止不加追问|
|calm_presence|不过度反应，保持稳定|冷场时不慌张，自然过渡|
|low_pressure_invite|零承诺的模糊邀约|"有空可以一起...","有机会的话..."|

### 平衡/中风险策略(Balance / Medium Risk)
**适用场景：关系已有初步基础，处于推进阶段但尚未明确**
**核心特征：风险可控，可撤回性，测试性质，能量适中，尊重边界**
|策略代码 (Strategy Code) |定义 (Definition)| 典型表现 (Typical Manifestation)|
|playful_tease|善意调侃 - 轻松的玩笑式调侃，建立轻松氛围同时测试对方反应|“你刚才那个表情，让我想起我侄女偷偷吃糖被抓包的样子”,“这么会拍照，是不是偷偷报了网红培训班？”|
|direct_compliment|直接赞美 - 明确表达欣赏，但聚焦于对方的选择或行为而非天生特质|“你处理这个问题的方式真的很聪明”,“你选餐厅的眼光一直这么好”|
|emotional_resonance|情绪共鸣 - 分享相似的情绪体验，建立情感连接|“我完全懂这种感觉，上周我也经历过类似的...”,“听到你这么说，我都能想象那个场景有多让人激动”|
|perspective_flip|视角反转 - 从对方角度重新描述或解读情境|“如果我是你，我可能会更生气，你处理得其实比我冷静多了”,“从你的角度看，这个问题确实很棘手”|
|value_signal|价值暗示 - 间接展示自身价值或特质，通过故事而非直接陈述|“上周我带队完成了那个项目后，团队都松了一口气”,“我平时喜欢登山，上次在华山看日出时就在想...”|
|micro_challenge|轻挑战 - 轻微质疑或提出小挑战，增加互动张力|“真的吗？我不太信你这么厉害”,“这听起来像是你会说的话，但我不确定你是不是认真的”|
|assumptive_frame|假设框架 - 假设性的亲密或未来场景，测试关系可能性|“如果我们一起去的话，你肯定会喜欢那个地方”，“想象一下，要是我们当时就认识，会是什么样”|
|story_snippet|故事片段 - 分享简短个人故事，展示性格并留互动钩子|“说到这个，让我想起去年在泰国迷路的经历...”，“有次我尝试做菜，结果差点把厨房点了，后来才知道...”|
|flirt_with_escape|留退路调情 - 调情性表达后立即提供轻松退路|“突然觉得你有点可爱...哎呀我是不是说得太直接了”，“你穿这件衣服挺好看的，不过别骄傲，我就随口一说”|
|selective_vulnerability|选择性脆弱 - 适度暴露个人弱点或小缺点，展示真实面|“其实我有时候也会很紧张，比如上周演讲前手都在抖”，“跟你说个有点丢人的事，我直到去年才学会骑自行车”|
|energy_injection|能量注入 - 提升对话能量水平，带动积极氛围|“哇！这个太棒了吧！！”，“真的吗？快多告诉我一些细节！”|
|forward_reference|未来暗示 - 暗示可能的未来互动或场景，创造期待感|“等你有空的时候，我们可以去试试那家新开的店”，“说不定下次见面时，你就能看到我的新作品了”|
|curiosity_hook|好奇心钩子 - 只说一半信息，引发对方好奇追问|“有件关于我的事你可能想不到...不过等合适的时候再告诉你”，“今天发生了件特别有趣的事，下次见面告诉你细节”|
|consent_check_light|轻度边界确认 - 轻微测试对方舒适区边界，尊重反应|“我可以问你个有点私人的问题吗？如果不想回答完全没关系”，“不知道这么说合不合适，但我确实觉得...”|

### 高风险/高回报策略 (Risky / High Reward) 
**适用场景：明确的双向吸引，三次以上积极互动，关系明显上升，双方情绪状态积极，对话能量处于高点。需要符合多个条件**
**核心特征：高风险/高回报策略本质上是关系加速器而非关系创造器**
|策略代码 (Strategy Code) |定义 (Definition)| 典型表现 (Typical Manifestation)|
|sexual_hint| 性暗示 - 含蓄或直接的性相关暗示，用于快速测试化学吸引力与边界 |"你这身衣服让人有点分心" ,"昨晚梦到你了，内容不太适合现在说","你知不知道你这样笑的时候，有点危险"|
|dominant_lead |主导引领 - 以强势姿态带领互动方向，展示领导力与控制力| "听我的，选那家餐厅你不会后悔","周六晚上7点，我去接你"（而非询问），"把手给我，带你去个地方"|
|strong_frame_control| 强框架控制 - 坚持自己的规则和边界，不轻易妥协立场| "我从来不允许别人迟到超过10分钟","在我的世界里，承诺就是一切","我选择伴侣的标准很明确，第一条就是..."|
|bold_assumption| 大胆假设 - 直接假设亲密关系状态，跨越常规进展阶段| "下次见我父母时，你得穿正式点","我们以后的家一定要有个大书房","你生气时还挺可爱的，以后得常惹你"|
|fast_escalation |快速升级 - 加速关系进展节奏，压缩正常发展时间线 |初次约会结束即尝试亲吻，认识一周即讨论同居可能性，在未确定关系时使用亲密昵称如"宝贝"|
|taboo_play| 禁忌游戏 - 有意触及社会或个人的敏感禁忌话题 |"你前任最让你受不了的是什么？","说说你做过最疯狂的事","如果我们私奔，你想去哪？"|
|polarity_push| 极性推动 - 刻意引发强烈爱恨反应，创造情绪波动 |突然冷淡后再极度热情，"有时候我真受不了你，但又离不开"，故意唱反调引发辩论再安抚|
|emotional_spike| 情绪峰值 - 表达强烈情绪反应，打破情感平静状态| "你刚才那句话让我心跳都停了"，突然的深情告白或激烈争执，在公共场合表达强烈情感|
|intimate_projection| 亲密投射 - 将想象中的亲密关系状态投射到当前关系| "只有你懂我的奇怪之处","我们好像上辈子就认识","你让我想安定下来了"（过早表达）|
|scarcity_signal| 稀缺信号 - 展示自身时间/精力的有限性，制造竞争感| "下周我要出国一个月，见不到了","最近好几个朋友给我介绍对象，有点烦","我通常不这样对人，你是例外"|

### 关系修复策略 (Recovery / Repair)
**使用场景：关系出现裂痕、互动陷入僵局或产生负面情绪后**
**核心特征：重建对话基础、修复信任损伤、降低关系风险、保留重启可能**
|策略代码 (Strategy Code)| 定义 (Definition)| 典型表现 (Typical Manifestation)|
|tension_release| 缓解尴尬 - 使用幽默、转移或弱化技巧化解紧张氛围，重建轻松对话基础 |"刚才气氛怎么突然像面试现场了，是我的错觉吗？","我们好像不小心进入了严肃模式，需要来点音乐调节下吗？","话题突然沉重了，先喝口水压压惊~"|
|boundary_respect| 明确退回 - 当感知到对方不适时，清晰表明退回到安全距离，重建信任| "我刚才可能越界了，我们回到之前的话题吧","这个话题如果你觉得不舒服，我们就不聊了","抱歉，我重新说：我觉得我们现在这样聊天就很好"|
|misstep_repair| 承认失误 - 具体承认错误行为并道歉，展示反省能力和尊重态度 |"我刚才说XX确实不妥，没有考虑你的感受，对不起","反思了一下，我那样追问确实不对，我道歉","我意识到刚才的态度有问题，我太急躁了"|
|emotional_deescalation| 降低强度 - 主动降低情感强度，将对话从激烈状态引导回理性层面| "我们先不讨论谁对谁错，聊聊这件事本身好吗？","我语气可能有点急，我们慢慢说","换个角度想，其实我们都在乎这段关系，只是表达方式不同"|
|graceful_exit| 优雅结束 - 体面结束当前对话，为后续互动保留可能性，避免彻底断联 |"今天先聊到这里吧，我们都再想想，明天再聊？","这个话题我们下次有合适时机再继续，先让它暂停一下","我需要点时间消化，我们晚点再聊这个好吗？"|

### 禁止的策略(Negative / Anti-pattern)
**使用场景：不应该使用**
**核心特征：自我价值低，过度理性，防御性强，情感空虚，害怕冲突，过度追求和谐**
|策略代码 (Strategy Code)| 定义 (Definition) |典型表现 (Typical Manifestation)|
|validation_seeking| 寻求认可 - 频繁寻求对方肯定和认可，展示低自我价值感和不安全感| "我这样做对吗？","你会不会觉得我很无聊？","我今天穿这样好看吗？","我这个人是不是很没意思？"|
|logical_interview| 逻辑面试 - 像面试官一样连续提问，缺乏情感互动，机械收集信息 |"你做什么工作？工资多少？","你父母是做什么的？","你买房了吗？有车吗？","你未来五年计划是什么？"|
|over_explaining |过度解释 - 对简单陈述或问题做出冗长辩解，显露出防御性和不自信| "我迟到了是因为...（3分钟详细解释）","我刚才那句话的意思是...（长篇解释）","你可能误会了，其实我是想说...（反复辩解）"|
|neediness_signal| 需求感信号 - 过度展示依赖和需求，显露出粘人和情感匮乏| "你怎么这么久才回我","你为什么不理我了","我一直在等你的消息","没有你我不知道怎么办"|
|performative_niceness| 表演式讨好 - 不真诚的过度迎合，缺乏个人边界和真实态度 |"你说的都对","我都听你的","只要你开心就好","我什么都行，你决定"|

## 输出格式
请严格按照以下 JSON 格式输出，不要包含其他内容：
{{
    "current_scenario": "安全/低风险策略|平衡/中风险策略|高风险/高回报策略|关系修复策略|禁止的策略",
    "recommended_scenario": "安全/低风险策略|平衡/中风险策略|高风险/高回报策略|关系修复策略|禁止的策略",
    "recommended_strategy": "Three Strategy Codes",
}}
"""

class ChatEmotionState(Enum):
    # 积极正向
    HAPPY_JOYFUL = "happy_joyful"  # 开心愉悦
    EXCITED_ANTICIPATING = "excited_anticipating"  # 兴奋期待
    RELAXED_COMFORTABLE = "relaxed_comfortable"  # 放松舒适
    FLIRTATIOUS_PLAYFUL = "flirtatious_playful"  # 暧昧调情
    
    # 中性平稳
    POLITE_FORMAL = "polite_formal"  # 礼貌客气
    CALM_NEUTRAL = "calm_neutral"  # 平静中立
    CURIOUS_EXPLORING = "curious_exploring"  # 好奇探索
    
    # 消极负面
    COLD_DISTANT = "cold_distant"  # 冷淡疏离
    ANXIOUS_NERVOUS = "anxious_nervous"  # 焦虑不安
    DISAPPOINTED_SAD = "disappointed_sad"  # 失望沮丧
    ANGRY_UPSET = "angry_upset"  # 生气不满
    DEFENSIVE_GUARDED = "defensive_guarded"  # 防御戒备

CONTEXT_SUMMARY_PROMPT = """你是一个对话场景分析专家。请根据以下对话历史，分析当前对话场景，汇总对话，分析情绪状态和聊天亲密度，以及风险等级。

## 对话历史
{conversation}

## 情绪状态
**积极正向**：话题轻松，主动推进话题，询问未来计划，回复节奏稳定，话题随意，调情双关语，轻微试探，赞美
**中性平稳**：用词正式，回复简短，客观回应，不主动推进，提问较多，主动了解
**消极负面**：回复慢，简短，不主动，反复确认，过度解释，语气消极，话题回避，指责语气，冷嘲热讽，保持距离

## 亲密程度
**陌生期**：初期接触、礼貌客气、平静中立、好奇探索
**熟悉期**：关系推进、开心愉悦、放松舒适、暧昧调情
**亲密期**：稳定关系、兴奋期待、放松舒适、暧昧调情
**修复期**：关系波动、平静中立、好奇探索、尝试重建

## 对话场景
**SAFE**: 双方处于陌生阶段，低容错，保守互动的对话;核心特征是建立安全感、渐进熟悉和避免越界
**BALANCED**: 男女双方处于推进关系的区间，中等熟悉度的对话；核心特征是适度展示个性和测试关系潜力
**RISKY**: 双方关系亲密，已建立较强连接；核心特征是推进关系、深化连接和高风险
**RECOVERY**: 关系出现尴尬、越界、误解后，双方处于关系修复阶段，适合保守的对话；核心目标是重建舒适区
**NEGATIVE**: 绝对避免的行为模式，识别特征是需求感过强、低社交价值


## 输出格式
请严格按照以下 JSON 格式输出，不要包含其他内容：
{{
    "conversation_summary": "对话总结",
    "emotion_state": "积极正向|中性平稳|消极负面",
    "current_intimacy_level": "陌生期|熟悉期|亲密期|修复期",
    "scenario": "SAFE|BALANCED|RISKY|RECOVERY|NEGATIVE"
}}
"""


CHATCOACH_PROMPT = """你是专业的恋爱聊天教练，专门帮助用户优化与心仪对象的聊天对话。你精通人际关系心理学、沟通技巧和情感智慧，能够根据具体情境提供精准的聊天建议。

## 对话场景分析

### 当前场景
{current_scenario}

### 推荐场景
{recommended_scenario}

### 推荐策略
{recommended_strategies}

## 亲密度分析

### 客户期望亲密程度
{intimacy_level}

### 当前对话亲密程度
{current_intimacy_level}

## 情绪状态
{emotion_state}

## 对话历史总结
{conversation_summary}

## 对话历史
{conversation}

## 用户画像
{persona_snapshot_prompt}

## 客户选择由你回复的一句话
{reply_sentence}

## 语言
{language}

## 任务
请根据以上信息，为用户生成 3 条高质量的回复建议。每条回复应该：
1. 符合当前对话场景和亲密程度
2. **优先使用推荐的策略（{recommended_strategies}）**
3. 匹配用户的沟通风格和偏好
4. 推进对话，保持自然流畅
5. 避免过度热情或冷淡
6. **使用指定的语言（{language}）生成回复内容**

## 输出格式
请严格按照以下 JSON 格式输出，不要包含其他内容：
{{
    "replies": [
        {{
            "text": "回复内容1（使用 {language} 语言）",
            "strategy": "使用的策略（如：emotional_resonance, story_snippet等）",
            "reasoning": "为什么推荐这条回复的简短说明"
        }},
        {{
            "text": "回复内容2（使用 {language} 语言）",
            "strategy": "使用的策略",
            "reasoning": "推荐理由"
        }},
        {{
            "text": "回复内容3（使用 {language} 语言）",
            "strategy": "使用的策略",
            "reasoning": "推荐理由"
        }}
    ],
    "overall_advice": "整体建议：当前对话的注意事项和建议"
}}

注意：所有回复内容（text字段）必须使用 {language} 语言生成。
"""