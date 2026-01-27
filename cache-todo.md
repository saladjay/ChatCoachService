## Session Cache TODO（Redis + SQLite，V1 Legacy）

说明：该 V1 实现计划删除，文档暂留仅用于对照与清理（见“删除 V1 SessionCacheService”）

### 目标
- [ ] 按 `session_id` 缓存 **2 小时内活跃** 的 **JSON** 数据
- [ ] 读取/写入都会刷新活跃时间（sliding TTL）
- [ ] 读取按插入顺序返回

### 配置（.env）
- [ ] `CACHE_REDIS_URL`（默认 `redis://localhost:6379/0`）
- [ ] `CACHE_SQLITE_PATH`（默认 `./session_cache.db`）
- [ ] `CACHE_TTL_SECONDS`（默认 `7200`）
- [ ] `CACHE_MAX_ITEMS_PER_SESSION`（默认 `20`，用于 Redis `LTRIM`）
- [ ] `CACHE_CLEANUP_INTERVAL_SECONDS`（默认 `300`，用于 SQLite 定时清理间隔）
- [ ] `CACHE_REDIS_KEY_PREFIX`（默认 `cache`）

### Redis 后端（在线缓存）
- [ ] Key 设计：`{prefix}:session:{session_id}`
- [ ] 写入：`RPUSH` 追加 JSON（保持插入顺序）
- [ ] 写入：`LTRIM -N -1`（N 由 `CACHE_MAX_ITEMS_PER_SESSION` 控制，默认 20）
- [ ] 写入：`EXPIRE key TTL`（刷新 2h TTL）
- [ ] 读取：`LRANGE 0 -1` 返回 JSON 数组（按插入顺序）
- [ ] 读取：`EXPIRE key TTL`（读取也刷新 TTL）
- [ ] Redis miss 回源：从 SQLite 加载并回填到 Redis（避免 Redis 重启导致直接空）

### SQLite 持久化（应对闪退/缓存量大）
- [ ] Schema：
  - [ ] `sessions(session_id, last_active_at, created_at)`
  - [ ] `items(id autoincrement, session_id, payload TEXT, created_at)`
- [ ] 写入策略：write-through（写 Redis 的同时写 SQLite）
- [ ] 活跃时间记录：读取/写入都会更新 `sessions.last_active_at`
- [ ] SQLite 侧裁剪：每个 session 只保留最近 N 条（与 `CACHE_MAX_ITEMS_PER_SESSION` 对齐）

### 过期与清理
- [ ] Redis：依赖 TTL 自动删除整个 session 缓存
- [ ] SQLite：后台定时清理 `last_active_at < now - TTL` 的 session（items 级联删除）
- [ ] 提供手动清理：`clear(session_id)` 同步删除 Redis + SQLite

### 与 FastAPI/容器模式集成
- [ ] 通过容器模式注册为 service：`ServiceContainer` 注册 `session_cache`
- [ ] FastAPI 启动时自动启动缓存服务：`lifespan` 中 `cache_service.start()`
- [ ] FastAPI 关闭时停止后台任务：`lifespan` 中 `cache_service.stop()`
- [ ] 支持 Depends 注入：`get_session_cache_service` / `SessionCacheServiceDep`

### 测试与可观测性
- [ ] 单元测试：顺序（RPUSH/LRANGE）、LTRIM 生效、TTL 刷新（读/写）、SQLite 恢复、SQLite 清理
- [ ] 指标/日志：session 数量、每 session 条目数、回源次数、清理次数

---

## 扩展规划：缓存需要细分类别字段（session_id + resource + category）

### 目标查询模式（你现在明确的读法）
- [x] `GET(session_id + url)`：返回该“资源”(url/纯文字)下**多个 category 的汇总**（同一资源的多类结果）
- [x] `GET(session_id + category)`：跨资源汇总，且**按时间顺序排列**（该 category 的事件流/历史）
- [x] `GET(session_id + category + url)`：返回该资源下**单个 category 的最新结果**
- [x] `GET(session_id)`：返回该 session 下出现过的所有资源（url/纯文字），并尽量按时间/最近活跃排序
- [x] 不需要 `GET(url -> session_id)` 反查（不做跨 session 的 url 去重）

### 统一建模建议（把“资源(resource) 视为维度”，“category 视为类型”，“timeline 视为序列”）
- [x] 定义概念实体（不写代码，仅语义）：
  - [x] `Category`: `image_result`/`context_analysis`/`scene_analysis`/`persona_analysis`/`strategy_plan`/`reply`（向后兼容，允许扩展）
  - [x] `ResourceKey`: 对“资源字符串”(url 或纯文字)做 `hash(resource)` 得到短 key（避免 Redis key 过长；原始字符串可进 payload/meta）
  - [x] `Event`: `{ts, resource_key, category, payload_json}`（用于 `session_id+category` 的时间序列）

### Redis Key 设计（主结构选你标注的：`session+category` timeline）
- [x] `S0: session 下资源列表（为了 GET(session_id)）`
  - [x] Key：`{prefix}:s:{session_id}:resources`
  - [x] Value：采用 `ZSet`：score=最近活跃 ts，member=resource_key（去重+最近排序）
  - [x] 同步维护 `Hash`：`{prefix}:s:{session_id}:resources:map`（resource_key -> 原始 resource 字符串）
- [x] `S2: 按 session+category 的时间序列（你选择这个为主结构）`
  - [x] Key：`{prefix}:s:{session_id}:c:{category}:timeline`
  - [x] Value：采用 `List`（RPUSH Event JSON；LRANGE 读出按插入顺序）
  - [x] 裁剪：使用 `LTRIM` 控制长度（`CACHE_TIMELINE_MAX_ITEMS`，默认 500）
- [x] `S3: （采用：轻量索引）按 session+resource+category 的最新指针（为了 GET(session_id+category+url)）`
  - [x] Key：`{prefix}:s:{session_id}:r:{resource_key}:c:{category}:last`
  - [x] Value：当前实现直接存 `Event JSON`（包含 ts/resource_key/category/payload）
  - [ ] 可选优化：未来 payload 变大时再改为“指针/摘要”（event_id / payload_key / ts）
- [x] `S4: （采用：轻量索引）按 session+resource 的 category 汇总（为了 GET(session_id+url)）`
  - [x] Key：`{prefix}:s:{session_id}:r:{resource_key}:cats`
  - [x] Value：采用 `Hash`（field=category，value=Event JSON）

### 写入规则（为了保持一致性）
- [x] timeline（`S2`）是 **source of truth**（权威数据源）
- [x] `S3/S4` 是 **加速索引**（当前实现存 Event JSON；未来可优化为指针）
- [x] Redis miss 时可从 SQLite 回源并重建 `S2/S3/S4/S0`

### TTL / 活跃时间策略（建议以 session 为统一边界）
- [x] 推荐：`session_id` 级别 sliding TTL 采用这个
  - [x] 任一写入/读取会刷新该 session 相关 key 的 TTL（至少刷新 `S0` + `S2`，并刷新 `S3/S4`）
  - [x] 过期删除以 session 为单位自然发生（符合“2 小时不活跃就删除该 session 缓存”）
- [ ] 可选：`cache_key` 级别独立 TTL（更精细，但会显著增加 key 数量与清理复杂度）

### 与你当前描述/我经验的冲突点（需要明确取舍）
- [ ] **关于“只选 timeline、不做 session+resource 聚合结构”的冲突**：
  - [ ] 你希望支持 `GET(session_id+url)` 与 `GET(session_id+category+url)`，但你又倾向“不选 `session+url` 上存最新对象”。
  - [ ] 经验结论：如果完全不做任何 `session+resource` 的索引（哪怕只是指针），那：
    - [ ] `GET(session_id+category+url)` 只能扫描 `S2` timeline 找最后一个匹配 resource_key（复杂度随历史增长）
    - [ ] `GET(session_id+url)` 需要扫描多个 category timeline 或扫描全量事件再按 resource 聚合（更重）
  - [ ] 结论（你已确认允许）：采用 **轻量索引/指针**（`S3/S4`），payload 仍以 timeline 为准；业务消费历史时直接读 `S2`。

- [ ] **经验上不建议用 Hash 存大量大 JSON**：
  - [ ] Hash 很适合存“少量、固定字段”的小值；如果 category payload 很大/很多，可能导致内存碎片与网络开销增大.
  - [ ] 但你的读模式是“按 url 一次拿全量 category”，Hash 可以减少 key 数量和 round-trip，这是取舍.

- [ ] **经验上更推荐把大 JSON 放在单独的 String key**：
  - [ ] `S4` 的 Hash 中只存一个“引用 key/版本号/摘要”，实际 payload 可以存 `{prefix}:s:{session_id}:r:{resource_key}:c:{category}:payload`（String JSON）或仅存在 timeline
- [ ] **不需要 url->session 反查**（你已明确）：
  - [ ] 这会让“跨 session 的重复 url 复用/去重”无法做到；但好处是模型简单、隐私边界清晰.

### 默认取舍（为了和你当前需求一致）
- [ ] 默认采用：`session_id` 级别 sliding TTL（便于“2 小时不活跃清整 session”）采取默认
- [ ] 如果后续发现 key 数量/写放大可控，再考虑 `cache_key` 级别 TTL 作为可选优化

### SQLite 持久化模型（支持多维 key + 索引）
- [x] 持久化表结构（当前实现：`session_categorized_cache_service.py`）
  - [x] `cache_sessions(session_id, last_active_at, created_at)`
  - [x] `cache_resources(session_id, resource_key, resource, last_active_at, created_at)`
  - [x] `cache_events(id, session_id, category, resource_key, ts, payload)`
- [x] 索引（当前实现）
  - [x] `idx_cache_events_session_category_id(session_id, category, id)`
  - [x] `idx_cache_events_session_resource_category_id(session_id, resource_key, category, id)`
  - [x] `idx_cache_sessions_last_active_at(last_active_at)`
  - [x] `idx_cache_resources_last_active_at(last_active_at)`

### API 规划（不写代码，仅定义能力边界）
- [x] `append_event(session_id, category, resource, payload)`：写入到 `S2 timeline`（权威）并维护 `S0/S3/S4`
- [x] `get_timeline(session_id, category, ...)`：读取 timeline 并刷新 TTL
- [x] `get_resource_categories(session_id, resource)`：读取 `S4`
- [x] `get_resource_category_last(session_id, resource, category)`：读取 `S3`
- [x] `list_resources(session_id)`：读取 `S0`
- [x] `clear_by_session(session_id)` / `clear_resource(session_id, resource)`：清理能力分层

### 实现状态（V2 已落地）
- [x] 服务实现：`app/services/session_categorized_cache_service.py`
- [x] 配置项：`CACHE_TIMELINE_MAX_ITEMS`（`app/core/config.py`）
- [x] 容器注册：`ServiceContainer.get_session_categorized_cache_service()`
- [x] 生命周期：`app/main.py` 的 `lifespan` 启动/停止
- [x] 依赖注入：`SessionCategorizedCacheServiceDep`
- [x] 单元测试：`tests/test_session_categorized_cache_service.py`

### 兼容与迁移策略
- [x] 不考虑 V1：当前不存在 V1 的业务数据与读写链路，不做 V1 命中/回退/迁移
- [ ] 可观测性（基于当前实现的计数器）：
  - [ ] 记录 `sqlite_fallback_loads`（近似视为“回源次数”）
  - [ ] 记录各 API 调用量：`append_event_calls/get_timeline_calls/get_resource_categories_calls/get_resource_category_last_calls/list_resources_calls`
  - [ ] 可选增强：补充 hit/miss 统计（区分 redis 命中 vs sqlite 回源）

---

## 删除 V1 SessionCacheService（旧实现清理）

### 代码清理
- [x] 全局 grep 确认无业务代码仍引用 `SessionCacheService` / `SessionCacheServiceDep`
- [x] 移除容器注册与 getter：`ServiceContainer` 中的 `session_cache` 相关逻辑
- [x] 移除依赖注入：`app/core/dependencies.py` 中 `get_session_cache_service` / `SessionCacheServiceDep`
- [x] 移除生命周期启停：`app/main.py` 的 `lifespan` 不再 `start()/stop()` V1
- [x] 删除旧服务实现：`app/services/session_cache_service.py`

### 配置清理
- [x] 评估并移除仅 V1 使用的配置项
  - [x] `CACHE_MAX_ITEMS_PER_SESSION`（V1 的 LTRIM）
  - [x] 其余配置项若 V2 仍使用则保留（例如 redis/sqlite/ttl/cleanup/prefix）

### 测试清理
- [x] 删除 V1 单元测试：`tests/test_session_cache_service.py`
- [ ] 跑全量测试确保通过

### 数据库文件与表
- [x] 旧表 `sessions/items` 直接删除：V1 从未上线、无数据、不做迁移

---

## 业务代码

### predict流程 api/v1/ChatAnalysis/predict
- [x] 输入解析与一致性约束
  - [x] 从请求中提取 `session_id` 与 `content[]`
  - [x] 定义 `resource`（业务约束）：
    - [x] 文本类：直接使用原文本
    - [x] 图片类：统一使用 `image_url`（无论是否下载到本地）
  - [x] 说明：服务内部对 `resource` 做短 hash 得到 `resource_key`（仅用于缩短 Redis key，不改变业务语义）
  - [x] 说明：不对图片内容做 hash 的影响 业务本身约束，同一个图片在session结束前，url不变
    - [x] 相同图片但 URL 不同无法复用缓存（URL 变更会导致 cache miss）
    - [x] 无法跨不同 URL 做去重（但实现更简单，也避免下载/读文件计算 hash 的成本）
  - [x] 校验：同一个 `session_id` 的 `scene` 必须一致（发现不一致则拒绝或告警）
    - [x] 规则：`scene` 为 1 或 3 视为同一类（建议先做归一化后再校验）
    - [x] 已实现：归一化后读取/写入 `scene_type` 并校验一致性
- [x] screenshot/image 结果缓存（优先命中缓存）
  - [x] category 统一：`image_result`
  - [x] 读：`get_resource_category_last(session_id, category="image_result", resource)`
  - [x] 命中：直接使用缓存的 `ImageResult`（不走后续分析）
  - [x] miss：执行 screenshot analysis / 第三方多模态
    - [x] 若拿到的是 `ParsedScreenshotData`，需转换为 `ImageResult` 再缓存
    - [x] 写：`append_event(session_id, category="image_result", resource, payload=ImageResult)`
  - [ ] 第三方多模态结果未测试：先落 TODO（单测/回归后再开启强依赖）
- [x] Orchestrator 阶段性缓存（在 `app/services/orchestrator.py`）
  - [x] category 统一：
    - [x] `context_analysis`
    - [x] `scene_analysis`
    - [x] `persona_analysis`
    - [x] `strategy_plan`
    - [x] `reply`
  - [x] 写入点：每个阶段产出后 `append_event(session_id, category, resource, payload=阶段输出)`
  - [x] 读取策略（先保守）：仅在需要“复用同一 session+resource 的已产出结果”时读取
    - [x] 读：`get_resource_category_last(session_id, category, resource)`
    - [x] 命中：跳过该阶段计算或作为 warm-start（由业务决策）
    - [x] miss：正常计算并写入