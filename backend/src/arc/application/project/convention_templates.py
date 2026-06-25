"""CONVENTION_TEMPLATES 注册表 — 按 ProjectType 裁剪的意图驱动治理规范 (v6.3.0 T2)。

复用 v5.9.0 注册点模式 (与 PROTOTYPE_BUILD_GUIDES / get_deployer / get_distributor 同构):
- dict[ProjectType, str] 注册表 + ConventionTemplateRegistry 工厂
- 新增 ProjectType 时在此注册特化段落, 不在 service/prompt 加 if 分支

与 PROTOTYPE_BUILD_GUIDES 的职责区分:
- PROTOTYPE_BUILD_GUIDES = 怎么构建 (脚手架/构建命令, 规则式 OK, 构建是机械的)
- CONVENTION_TEMPLATES = 怎么治理项目 (迭代/质量/规范维护, 必须意图驱动, 等价 CLAUDE.md)

设计: 特化模板 = 通用治理骨架 (T1 DefaultConventionTemplateProvider) + 类型特化增量段落。
通用意图 (上下文加载/版本迭代/代码规范/质量守护/规范维护) 所有类型共享, 避免重复;
特化段落只写类型相关意图 (static_site=SEO/PWA/性能, binary_app=签名/分发/跨平台)。
"""
from __future__ import annotations

from arc.domain.project.charter import (
    ConventionTemplateProvider,
    DefaultConventionTemplateProvider,
)
from arc.domain.project.value_objects import ProjectType

# static_site 特化治理意图 — 官网/SPA 类项目 (v6.3.0 T2)
_STATIC_SITE_SPECIALIZATION = """\

## 静态站点特化治理意图 (project_type=static_site)

### 可发现性意图 (SEO)
- 目标: 站点内容能被搜索引擎和社交平台发现、索引、正确预览。
- 输出契约: 每个可分享页面有准确的标题、描述与社交卡片; 关键内容在首屏可抓取。
- 上下文: 静态托管无服务端渲染时, 自主判断是否需要预渲染/SSG 以保证可发现性,
  而非套固定方案。元数据与页面内容一致, 不为优化堆砌无关关键词。

### 离线降级意图 (PWA)
- 目标: 网络不稳或离线时, 用户仍能完成核心操作, 不白屏、不丢失输入。
- 输出契约: 关键资源可缓存, 离线访问有明确反馈而非静默失败。
- 上下文: 自主判断哪些资源该缓存、哪些数据需要同步策略, 而非全量缓存。
  离线体验对齐在线的核心路径, 不降级到空白页。

### 加载体验意图 (性能)
- 目标: 用户感知流畅——首屏快、交互响应及时、无意外布局偏移。
- 输出契约: 变更后, 受影响页面的加载与交互仍达可感知流畅。
- 上下文: 自主判断资源体积、加载时机、渲染策略是否合理, 而非套固定性能阈值。
  大资源延迟加载, 关键路径优先。
"""


# binary_app 特化治理意图 — 原生客户端 (Tauri/Capacitor) 类项目 (v6.3.0 T2)
# 复用 v6.0 构建 / v6.1 签名 / v6.2 分发 成果, 但以治理意图表述 (非构建命令)
_BINARY_APP_SPECIALIZATION = """\

## 原生客户端特化治理意图 (project_type=binary_app)

### 可信分发意图 (签名)
- 目标: 发布的客户端产物来源可信、未被篡改、平台可验证。
- 输出契约: 发布前完成签名; 签名凭证按平台隔离管理, 不泄露到代码或日志。
- 上下文: 自主判断各平台签名要求是否满足 (复用 v6.1 签名能力),
  凭证未配时不强行发布而是显式标记缺失。签名与构建分离, 不混入构建流程。

### 渠道上架意图 (分发)
- 目标: 签名后产物能上架到目标分发渠道, 用户可获取。
- 输出契约: 产物到达目标渠道 (商店/更新服务); 上传失败时产物不丢失。
- 上下文: 自主判断分发渠道凭证是否配齐 (复用 v6.2 分发能力),
  未配渠道 graceful skip, 产物落制品仓可手动获取。分发与签名独立, 不耦合。

### 跨平台一致性意图
- 目标: 同一工程产出的多平台客户端, 行为与体验一致。
- 输出契约: 平台差异显式标注, 共享逻辑不因平台分叉。
- 上下文: web 资源与原生壳复用, 自主判断哪些需平台特化、哪些应共享,
  而非为每平台重复实现。构建目标按平台隔离, 产物可识别。
"""


# 类型特化段落注册表 — 新增 ProjectType 时在此注册特化段落
# key = ProjectType, value = 追加在通用治理骨架后的特化意图段落
CONVENTION_TEMPLATES: dict[ProjectType, str] = {
    ProjectType.STATIC_SITE: _STATIC_SITE_SPECIALIZATION,
    ProjectType.BINARY_APP: _BINARY_APP_SPECIALIZATION,
}


class ConventionTemplateRegistry(ConventionTemplateProvider):
    """按 ProjectType 返回治理规范模板的注册表实现 (v6.3.0 T2)。

    与 v5.9.0 get_prototype_guide / get_distributor 同构: dict 注册表 + 工厂方法。
    - 已注册类型: 通用治理骨架 (T1 DefaultConventionTemplateProvider) + 类型特化段落
    - 未注册类型: 仅通用治理骨架 (graceful fallback, 不抛异常)

    替换 T1 的 DefaultConventionTemplateProvider 成为 workspace_service 默认 provider。
    新增 ProjectType 时在 CONVENTION_TEMPLATES 注册特化段落即可, 不改本类逻辑。
    """

    def __init__(self, default: ConventionTemplateProvider | None = None):
        self._default = default or DefaultConventionTemplateProvider()

    def get_template(self, project_type: ProjectType) -> str:
        base = self._default.get_template(project_type)
        specialization = CONVENTION_TEMPLATES.get(project_type)
        if not specialization:
            return base
        return f"{base}\n{specialization}"
