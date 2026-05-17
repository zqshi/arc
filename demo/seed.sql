-- =============================================================
-- Arc 演示数据种子 — 一键灌入，覆盖全链路各阶段
-- 用法: docker compose exec db psql -U arc -d arc -f /seed.sql
--       或: cat demo/seed.sql | docker compose exec -T db psql -U arc -d arc
-- =============================================================

-- 清空旧数据（按外键顺序）
TRUNCATE messages, conversations, experiences, todos CASCADE;

-- ======================== UUIDs =============================
-- 6个待办，分别处于不同状态

-- Todo 1: pending（刚创建）
-- Todo 2: analyzing（分析中，有对话）
-- Todo 3: dev（开发中，有分析+开发对话）
-- Todo 4: review（验收中）
-- Todo 5: done（已完成，有经验卡片）
-- Todo 6: pending（另一个新待办）

DO $$
DECLARE
  t1 uuid := 'a0000001-0000-0000-0000-000000000001';
  t2 uuid := 'a0000002-0000-0000-0000-000000000002';
  t3 uuid := 'a0000003-0000-0000-0000-000000000003';
  t4 uuid := 'a0000004-0000-0000-0000-000000000004';
  t5 uuid := 'a0000005-0000-0000-0000-000000000005';
  t6 uuid := 'a0000006-0000-0000-0000-000000000006';
  c1 uuid := 'c0000001-0000-0000-0000-000000000001';
  c2 uuid := 'c0000002-0000-0000-0000-000000000002';
  c3 uuid := 'c0000003-0000-0000-0000-000000000003';
  c4 uuid := 'c0000004-0000-0000-0000-000000000004';
  c5 uuid := 'c0000005-0000-0000-0000-000000000005';
  e1 uuid := 'e0000001-0000-0000-0000-000000000001';
  e2 uuid := 'e0000002-0000-0000-0000-000000000002';
  now_ts timestamptz := now();
BEGIN

-- ====================== TODOS ==============================

INSERT INTO todos (id, title, description, status, tags, background, goals, boundaries, acceptance, tech_plan, created_at, updated_at)
VALUES
-- 1. 刚创建的待办
(t1, '用户登录支持OAuth2.0',
 '当前系统只有用户名密码登录，需要增加Google和GitHub的OAuth2.0登录方式',
 'pending',
 '[{"label":"认证","color":"#4A9FD8"},{"label":"后端","color":"#4A9FD8"},{"label":"安全","color":"#EF4444"}]'::jsonb,
 '', '', '', '', '',
 now_ts - interval '2 hours', now_ts - interval '2 hours'),

-- 2. 分析中
(t2, '订单导出性能优化',
 '后台导出10万条以上订单时，接口超时（>30s），需要优化到5s内完成或改为异步导出',
 'analyzing',
 '[{"label":"性能","color":"#E5A93D"},{"label":"后端","color":"#4A9FD8"},{"label":"导出","color":"#4A9FD8"}]'::jsonb,
 '运营团队每周需要导出全量订单数据做分析，当前使用同步接口，数据量超过10万时频繁超时。',
 '将导出响应时间控制在5s内，或支持异步导出+下载通知',
 '', '', '',
 now_ts - interval '5 hours', now_ts - interval '1 hour'),

-- 3. 开发中
(t3, '商品搜索接入Elasticsearch',
 '当前商品搜索使用数据库LIKE查询，20万商品时搜索延迟>2s，需要接入ES提升搜索体验',
 'dev',
 '[{"label":"性能","color":"#E5A93D"},{"label":"架构","color":"#F59E0B"},{"label":"后端","color":"#4A9FD8"}]'::jsonb,
 '电商平台商品量增长到20万+，用户搜索体验明显下降，搜索延迟经常超过2秒。',
 '接入Elasticsearch实现商品全文搜索，搜索延迟<200ms，支持拼音和模糊搜索。',
 '1. 不改变现有商品CRUD接口\n2. ES宕机时降级到数据库查询\n3. 索引同步延迟<1s',
 '1. 搜索延迟p99<200ms\n2. 支持中文分词+拼音搜索\n3. 搜索结果与数据库一致性>99.9%',
 '1. 部署ES 8.x单节点\n2. 使用Canal监听MySQL binlog同步到ES\n3. 商品Service增加SearchAdapter\n4. 搜索API走ES，写入仍走MySQL\n5. 增加降级开关和健康检查',
 now_ts - interval '1 day', now_ts - interval '30 minutes'),

-- 4. 验收中
(t4, '支付回调幂等性改造',
 '支付网关偶发重复回调导致订单状态异常，需要实现幂等性处理机制',
 'review',
 '[{"label":"支付","color":"#A78BFA"},{"label":"后端","color":"#4A9FD8"},{"label":"安全","color":"#EF4444"}]'::jsonb,
 '线上每周约有3-5笔订单因支付回调重复导致状态错乱，影响用户体验和财务对账。',
 '1. 支付回调100%幂等\n2. 重复回调不影响订单状态\n3. 保留完整的回调日志',
 '1. 不修改支付网关侧的配置\n2. 兼容微信/支付宝/Stripe三个渠道',
 '1. 同一笔支付回调重复3次，订单状态正确\n2. 幂等检查延迟<5ms\n3. 回调日志可追溯',
 '1. 新增payment_callbacks表记录每次回调\n2. 使用唯一索引(payment_id, callback_type)实现幂等\n3. 回调处理改为先查后写模式\n4. 增加分布式锁防并发\n5. 异常回调告警到企微',
 now_ts - interval '3 days', now_ts - interval '6 hours'),

-- 5. 已完成
(t5, 'API接口限流方案实施',
 '高峰期API QPS达到5000+，部分接口响应变慢，需要实施精细化限流保护核心接口',
 'done',
 '[{"label":"性能","color":"#E5A93D"},{"label":"架构","color":"#F59E0B"},{"label":"API","color":"#34D399"}]'::jsonb,
 '大促期间API QPS峰值达到5000+，数据库连接池耗尽导致核心交易接口受影响。',
 '1. 核心交易接口保证p99<500ms\n2. 非核心接口限流不影响用户体验\n3. 限流策略可动态调整',
 '1. 使用现有Redis集群\n2. 不引入新的中间件\n3. 限流粒度到接口+用户维度',
 '1. 核心接口在10000QPS下p99<500ms\n2. 限流规则10s内生效\n3. 被限流请求返回429+Retry-After头',
 '1. 基于Redis实现令牌桶算法\n2. 接口级+用户级双层限流\n3. 规则存储在配置中心，支持热更新\n4. 限流SDK封装为中间件\n5. Grafana面板监控限流触发率',
 now_ts - interval '7 days', now_ts - interval '2 days'),

-- 6. 另一个新待办
(t6, '用户行为埋点系统设计',
 '产品侧需要用户行为数据支撑决策，目前没有统一的埋点方案，数据散落在各处日志中',
 'pending',
 '[{"label":"前端","color":"#34D399"},{"label":"架构","color":"#F59E0B"},{"label":"数据库","color":"#A78BFA"}]'::jsonb,
 '', '', '', '', '',
 now_ts - interval '1 hour', now_ts - interval '1 hour');


-- =================== CONVERSATIONS =========================

-- Todo2(analyzing) 的需求澄清对话
INSERT INTO conversations (id, todo_id, purpose, created_at, updated_at)
VALUES (c1, t2, 'clarification', now_ts - interval '4 hours', now_ts - interval '1 hour');

INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) VALUES
(gen_random_uuid(), c1, 'assistant',
 '我来帮你分析订单导出性能优化的需求。先了解几个关键信息：

1. **当前数据量**：平均每次导出多少条订单？峰值是多少？
2. **导出格式**：目前是导出为Excel还是CSV？
3. **筛选条件**：用户导出时通常使用哪些筛选条件？
4. **使用频率**：每天大约有多少次导出请求？',
 '{}'::jsonb, now_ts - interval '4 hours'),
(gen_random_uuid(), c1, 'user',
 '1. 平均5万条，峰值15万条\n2. 导出为Excel(.xlsx)\n3. 通常按时间范围+订单状态筛选\n4. 每天约50次导出请求，集中在上午10点',
 '{}'::jsonb, now_ts - interval '3 hours' - interval '50 minutes'),
(gen_random_uuid(), c1, 'assistant',
 '了解了。根据你的描述，核心瓶颈在于：
- **Excel生成耗时**：15万行Excel在内存中生成非常慢
- **同步阻塞**：当前是同步接口，请求线程被长时间占用
- **并发冲击**：上午10点集中请求加剧了问题

我建议的方案方向：

### 方案A：异步导出 + 消息通知
1. 导出请求立即返回任务ID
2. 后台Worker异步生成文件
3. 完成后推送通知（站内信/企微）
4. 用户到"我的导出"页面下载

### 方案B：流式导出CSV
1. 改用CSV格式，流式写入响应
2. 10万条CSV约3s完成
3. 但牺牲了Excel格式的便利性

你倾向哪个方案？或者两个都要支持？',
 '{}'::jsonb, now_ts - interval '3 hours' - interval '40 minutes'),
(gen_random_uuid(), c1, 'user',
 '方案A，运营团队习惯用Excel。另外需要支持导出任务排队，不能同时跑太多。',
 '{}'::jsonb, now_ts - interval '3 hours' - interval '30 minutes'),
(gen_random_uuid(), c1, 'assistant',
 '明白，那我来梳理完整的需求：

### 背景
运营团队日常需要导出大量订单数据，当前同步导出在数据量>10万时超时。

### 目标
实现异步导出机制，支持大数据量Excel导出，完成后自动通知。

### 边界条件
1. 最大支持20万条订单导出
2. 同时运行的导出任务不超过3个，多余的排队
3. 导出文件保留7天后自动清理
4. Excel格式不变，兼容现有的列结构

### 验收标准
1. 15万条订单导出<60s完成
2. 用户提交导出后3s内收到"已加入队列"反馈
3. 完成后1分钟内收到企微通知
4. "我的导出"页面显示任务状态和下载链接

需要确认这些要求是否准确？',
 '{}'::jsonb, now_ts - interval '3 hours' - interval '20 minutes');


-- Todo3(dev) 的需求澄清对话（已完成）
INSERT INTO conversations (id, todo_id, purpose, created_at, updated_at)
VALUES (c2, t3, 'clarification', now_ts - interval '23 hours', now_ts - interval '20 hours');

INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) VALUES
(gen_random_uuid(), c2, 'assistant',
 '商品搜索接入ES是个好方向。让我确认几个关键点：

1. 当前商品表有多少字段？搜索需要覆盖哪些字段？
2. 是否需要支持筛选（价格区间、分类、品牌）？
3. 对搜索结果排序有什么要求？',
 '{}'::jsonb, now_ts - interval '23 hours'),
(gen_random_uuid(), c2, 'user',
 '1. 搜索覆盖：商品名称、描述、SKU编号、品牌名\n2. 需要支持分类和价格筛选\n3. 默认按相关度排序，支持按价格和销量排序',
 '{}'::jsonb, now_ts - interval '22 hours' - interval '30 minutes'),
(gen_random_uuid(), c2, 'assistant',
 '好的，需求清晰了。技术方案我建议如下：

1. **ES索引设计**：使用ik_max_word分词器 + pinyin分析器
2. **数据同步**：Canal监听binlog，准实时同步到ES
3. **API设计**：新增/api/products/search端点
4. **降级方案**：ES不可用时自动切回MySQL LIKE查询

确认没问题我就整理成卡片字段。',
 '{}'::jsonb, now_ts - interval '22 hours');

-- Todo3(dev) 的开发执行对话
INSERT INTO conversations (id, todo_id, purpose, created_at, updated_at)
VALUES (c3, t3, 'development', now_ts - interval '18 hours', now_ts - interval '30 minutes');

INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) VALUES
(gen_random_uuid(), c3, 'system',
 '[OpenHands] 已创建开发会话，任务ID: oh-session-3a7b',
 '{}'::jsonb, now_ts - interval '18 hours'),
(gen_random_uuid(), c3, 'system',
 '[OpenHands] 正在分析项目结构...\n识别到Spring Boot项目，MySQL数据源配置在application.yml',
 '{}'::jsonb, now_ts - interval '17 hours' - interval '55 minutes'),
(gen_random_uuid(), c3, 'system',
 '[OpenHands] 开始实施步骤1: 添加ES依赖和配置\n- 添加 spring-boot-starter-data-elasticsearch\n- 配置ES连接: localhost:9200',
 '{}'::jsonb, now_ts - interval '17 hours' - interval '45 minutes'),
(gen_random_uuid(), c3, 'system',
 '[OpenHands] 步骤2: 创建ES索引映射\n- 创建 ProductSearchDocument 实体\n- 配置ik分词器和pinyin分析器\n- 字段映射: name(text), description(text), sku(keyword), brand(keyword), price(double), category_id(long)',
 '{}'::jsonb, now_ts - interval '17 hours' - interval '30 minutes'),
(gen_random_uuid(), c3, 'system',
 '[OpenHands] 步骤3: 实现SearchAdapter\n- 创建 ProductSearchService\n- 实现 search(keyword, filters, sort, page) 方法\n- 实现降级逻辑: @CircuitBreaker fallback到MySQL',
 '{}'::jsonb, now_ts - interval '17 hours'),
(gen_random_uuid(), c3, 'system',
 '[OpenHands] 步骤4: 数据同步模块开发中...',
 '{}'::jsonb, now_ts - interval '30 minutes');


-- Todo4(review) 的需求澄清对话
INSERT INTO conversations (id, todo_id, purpose, created_at, updated_at)
VALUES (c4, t4, 'clarification', now_ts - interval '2 days' - interval '20 hours', now_ts - interval '2 days' - interval '19 hours');

INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) VALUES
(gen_random_uuid(), c4, 'assistant',
 '支付回调幂等性是个关键问题。当前你们遇到的重复回调，是同一个支付单号的多次回调，还是不同支付单号但同一订单的回调？',
 '{}'::jsonb, now_ts - interval '2 days' - interval '20 hours'),
(gen_random_uuid(), c4, 'user',
 '主要是同一支付单号的重复回调，支付网关有时会重试发送。',
 '{}'::jsonb, now_ts - interval '2 days' - interval '19 hours' - interval '50 minutes'),
(gen_random_uuid(), c4, 'assistant',
 '清楚了。技术方案建议：用唯一索引+先查后写，配合分布式锁兜底并发场景。验收标准我整理好了，已写入卡片。',
 '{}'::jsonb, now_ts - interval '2 days' - interval '19 hours');

-- Todo5(done) 的需求澄清对话
INSERT INTO conversations (id, todo_id, purpose, created_at, updated_at)
VALUES (c5, t5, 'clarification', now_ts - interval '6 days', now_ts - interval '5 days' - interval '20 hours');

INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) VALUES
(gen_random_uuid(), c5, 'assistant',
 'API限流方案，我们先明确几个关键参数：\n1. 核心接口有哪些？各自的限流阈值是多少？\n2. 限流粒度：按IP、按用户、还是按接口？\n3. 限流后的降级策略是什么？',
 '{}'::jsonb, now_ts - interval '6 days'),
(gen_random_uuid(), c5, 'user',
 '1. 下单、支付、查询订单为核心接口，分别限流1000、500、2000 QPS\n2. 接口+用户双维度\n3. 返回429，前端展示"请求太频繁，请稍后重试"',
 '{}'::jsonb, now_ts - interval '5 days' - interval '23 hours'),
(gen_random_uuid(), c5, 'assistant',
 '好的，方案很清晰。我已梳理完整需求并写入卡片，可以进入开发阶段。',
 '{}'::jsonb, now_ts - interval '5 days' - interval '20 hours');


-- =================== EXPERIENCES ============================

-- 与Todo5(已完成)关联的经验
INSERT INTO experiences (id, todo_id, title, problem, solution, decisions, pitfalls, applicable_scenarios, tags, confidence, reuse_count, metadata, created_at, updated_at)
VALUES
(e1, t5,
 'Redis令牌桶限流实战',
 '大促期间API QPS达5000+，数据库连接池耗尽，核心交易接口响应劣化到>2s。',
 '基于Redis实现令牌桶算法，分接口+用户双层限流。使用Lua脚本保证原子性，配合配置中心实现规则热更新。限流SDK封装为Spring拦截器，一行注解即可接入。',
 '["选择令牌桶而非漏桶算法，因为需要允许短时突发流量","限流规则存配置中心而非代码里，支持不停机调整","双层限流：全局接口级+单用户级，防止单个用户占用过多配额"]',
 '["Redis Cluster模式下Lua脚本要用hashtag保证key在同一个slot","令牌桶的refill计算在高并发下有精度问题，最终改用Redis TIME命令获取服务端时间","配置中心推送有2-3s延迟，限流规则生效不是实时的，文档要说明"]',
 '高并发场景下的API保护，适用于电商大促、秒杀活动等流量突增场景。需要Redis基础设施支持。',
 '[{"label":"性能","color":"#E5A93D"},{"label":"架构","color":"#F59E0B"},{"label":"API","color":"#34D399"},{"label":"缓存","color":"#E5A93D"}]'::jsonb,
 0.85, 3,
 '{}'::jsonb,
 now_ts - interval '2 days', now_ts - interval '2 days'),

-- 独立的经验卡片（模拟历史积累）
(e2, NULL,
 'MySQL到ES数据同步踩坑记录',
 '使用Canal监听MySQL binlog同步数据到Elasticsearch，同步延迟不稳定，偶发数据不一致。',
 '1. Canal部署为HA模式，配合ZK做failover\n2. 消费端增加对账任务，每小时全量比对一次\n3. 同步失败的消息入死信队列，人工处理\n4. ES写入使用bulk API批量操作，吞吐量提升5x',
 '["用Canal而非双写，避免分布式事务问题","对账任务选在凌晨低峰期运行，减少对线上影响","死信队列选用RocketMQ而非Redis，确保消息不丢"]',
 '["Canal的position管理要持久化到ZK，否则重启后会重复消费","ES的mapping一旦创建不能修改字段类型，要提前规划好","binlog格式必须是ROW模式，STATEMENT模式Canal解析会出错"]',
 '需要准实时数据同步的场景，如搜索引擎索引构建、数据仓库ETL、读写分离架构。',
 '[{"label":"数据库","color":"#A78BFA"},{"label":"架构","color":"#F59E0B"},{"label":"第三方","color":"#F59E0B"}]'::jsonb,
 0.78, 1,
 '{}'::jsonb,
 now_ts - interval '14 days', now_ts - interval '14 days');

END $$;
