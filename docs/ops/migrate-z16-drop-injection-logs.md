# 生产环境迁移与清理清单 — z16 drop experience_injection_logs

> **版本**: v6.6.0 T1
> **变更性质**: 数据库 schema 变更(drop table), 不可逆(历史数据销毁)
> **前置确认**: 用户已授权全量清理历史数据
> **最后更新**: 2026-06-26

## 背景

`experience_injection_logs` 表由 z7 migration 创建, 用于记录经验注入上下文做 ROI 追踪。
v6.6 删除了唯一的写入方 `experience/analytics.py`(218 行零引用死代码), 表成孤儿:
- model `ExperienceInjectionLog` 零业务引用(grep 确认)
- migration `z8_context_policy` 仅作 alembic 版本链前驱引用, 非表结构依赖
- 表无业务写入路径

z16 migration drop 该表 + 删 model 类。本地全新库从 z6→z16 全链建链已验证(见 [v6.6.0-snapshot.md](../versions/v6.6.0-snapshot.md))。

---

## 执行前检查(必做)

```bash
# 1. 确认当前生产 DB alembic 版本(应为 z15_project_charter)
cd backend
alembic current
# 期望输出: z15_project_charter (head)

# 2. 确认无活跃业务引用该表(应仅 alembic 版本链引用)
psql $DATABASE_URL -c "\dt experience_injection_logs"
psql $DATABASE_URL -c "SELECT count(*) FROM experience_injection_logs;"
# 记录行数, 评估历史数据销毁规模

# 3. 确认代码库已是含 z16 的版本(z16_drop_injection_logs.py 存在)
ls alembic/versions/z16_drop_injection_logs.py
grep -c "ExperienceInjectionLog" src/arc/infrastructure/models/experience.py
# 期望: 文件存在; model 类 grep 命中 0(已删)
```

---

## 执行步骤

### 步骤 1: 备份(强烈建议, 即使授权清理)

```bash
# 备份该表数据(若行数 > 0 且想留底)
pg_dump $DATABASE_URL -t experience_injection_logs > experience_injection_logs_backup_$(date +%Y%m%d).sql

# 或整库快照(生产 DB 完整备份, 推荐)
pg_dump $DATABASE_URL > arc_full_backup_$(date +%Y%m%d).sql
```

### 步骤 2: 应用 z16 migration

```bash
cd backend
alembic upgrade head
# 期望日志:
#   Running upgrade z15_project_charter -> z16_drop_injection_logs,
#   drop experience_injection_logs table (orphaned after analytics removal)
```

### 步骤 3: 验证

```bash
# 1. alembic 版本应为 z16
alembic current
# 期望: z16_drop_injection_logs (head)

# 2. 表已不存在
psql $DATABASE_URL -c "SELECT to_regclass('experience_injection_logs');"
# 期望: 空(NULL)

# 3. alembic 单 head(无版本链断裂)
alembic heads
# 期望: 仅一行 z16_drop_injection_logs (head)

# 4. backend /health 正常
curl -s http://localhost:8000/health | jq .
# 期望: {"status":"ok", ...}

# 5. 后端单元测试通过(可选, 确认 model 删除无回归)
pytest tests/unit -x --tb=short -q
# 期望: 1800 passed
```

---

## 回滚(若需恢复表结构)

> ⚠️ 回滚仅恢复空表结构, **历史数据不可恢复**(已 drop)。需用步骤 1 的备份恢复数据。

```bash
cd backend
alembic downgrade -1
# 回滚到 z15_project_charter, 重建空表 experience_injection_logs

# 恢复数据(若步骤 1 有备份)
psql $DATABASE_URL < experience_injection_logs_backup_YYYYMMDD.sql
```

z16 的 `downgrade()` 已实现完整建表(含外键/索引/server_default), 本地 up→down→up 双向幂等验证通过。

---

## 风险评估

| 项 | 评估 |
|----|------|
| 业务影响 | 无。表无写入路径(analytics.py 已删), 无读取方 |
| 数据丢失 | experience_injection_logs 行数据销毁(用户已授权全量清理) |
| 兼容性 | model 类已从代码删, 旧代码进程重启后无引用 |
| 可逆性 | 表结构可回滚(downgrade 建表), 数据不可逆 |
| 版本链 | z16 接 z15_project_charter 链尾, 单 head, 无断裂风险 |

---

## 相关

- 决策记录: [v6.6.0-snapshot.md](../versions/v6.6.0-snapshot.md) T1
- migration 文件: `backend/alembic/versions/z16_drop_injection_logs.py`
- 本地全新库建链验证: docker-compose.prod.yml `-p arcprod` 隔离环境, z6→z16 全链成功
