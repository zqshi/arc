# Backlog — 后续版本规划

> 这是粗粒度的版本规划, 不是承诺。每个版本启动时再细化为 current.md。
> 最后更新: 2026-05-25

---

## ~~v0.4.0~~ → 已完成, 见 [v0.4.0-snapshot.md](v0.4.0-snapshot.md)

## ~~v0.5.0~~ → 已完成, 见 [v0.5.0-snapshot.md](v0.5.0-snapshot.md)

---

## ~~v1.0.0~~ → 已完成, 见 [v1.0.0-snapshot.md](v1.0.0-snapshot.md)

---

## ~~v1.1.0~~ → 已完成, 见 [v1.1.0-snapshot.md](v1.1.0-snapshot.md)

---

## ~~v1.2.0~~ → 已完成, 见 [v1.2.0-snapshot.md](v1.2.0-snapshot.md)

---

## ~~v2.0.0~~ → 已完成, 见 [v2.0.0-snapshot.md](v2.0.0-snapshot.md)

---

## 技术债务 — 架构改善 (可穿插在任何版本中)

| 工作项 | 优先级 | 来源 | 状态 |
|--------|--------|------|------|
| ~~路由层 → Application Service 收口 (14+ 路由文件直接操作 Repository)~~ | P1 | 2026-05 审计 | 核心收口已完成, 剩余渐进 |
| ~~核心模块测试覆盖 (storage/publish/document/WS/pipeline routes)~~ | P1 | 2026-05 审计 | 36 cases 已覆盖 |
| ~~内存分页改 SQL 分页 (project.py:762,876,947,611)~~ | P2 | 2026-05 审计 | done |
| ~~Artifact content discriminated union 类型化 (前后端)~~ | P2 | 2026-05 审计 | done |
| ~~ChatMessages 虚拟列表 (200+ 消息滚动性能)~~ | P2 | 2026-05 审计 | done |
| ~~DeliverableDrawer 类型断言消除 (定义 RoadmapData 接口)~~ | P3 | 2026-05 审计 | done |
| ~~ErrorBoundary key-based remount~~ | P3 | 2026-05 审计 | done |
| ~~Toast ARIA live region~~ | P3 | 2026-05 审计 | done |

---

## 跨版本约束

这些约束跨越多个版本, 任何版本的开发都必须遵守:

1. **架构约束**: DDD分层不可破坏 — domain层不依赖infrastructure
2. **数据兼容**: 数据库schema变更必须有migration, 不允许破坏性变更
3. **API兼容**: 已发布的API端点不改签名, 新增字段用optional
4. **经验数据**: 经验表结构的变更必须考虑存量数据迁移
5. **二代预留**: 功能设计需考虑"第二代: AI驱动, 人审批"的演化方向(见arc_system_essence.md)
