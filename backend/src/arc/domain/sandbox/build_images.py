"""构建镜像推导注册表 — (project_type, build_target) → 镜像名。

镜像选择是二维决策, 与 sandbox 运行时配置解耦:
- project_type 决定"构建什么形态" (静态站点/原生客户端)
- build_target 决定"容器内构建到哪个目标" (tauri_linux/web/apk)

本模块是纯映射 + 覆盖, 不依赖 config 模块 (覆盖值作 dict 参数传入),
符合 domain 层零外部依赖约束。application 层调用 resolve_build_image()
后将结果填入 SandboxPolicy.docker_image — SandboxPolicy 保持"已解析最终配置"
职责, 不耦合 project_type。

波次2/3 激活新 target 时只需在 DEFAULT_BUILD_IMAGES 加条目, 零架构改动。
"""
from __future__ import annotations

from arc.domain.project.value_objects import ProjectType
from arc.domain.sandbox.value_objects import BuildTarget

# (ProjectType, BuildTarget) → 默认镜像名。
# v6.0 波次1: 仅 BINARY_APP/TAURI_LINUX 主线。
# 波次2: 加 (BINARY_APP, WEB) / (STATIC_SITE, WEB)
# 波次3: 加 (BINARY_APP, CAPACITOR_APK)
DEFAULT_BUILD_IMAGES: dict[tuple[ProjectType, BuildTarget], str] = {
    (ProjectType.BINARY_APP, BuildTarget.TAURI_LINUX): "arc/tauri-builder:linux",
}


def _override_key(project_type: ProjectType, build_target: BuildTarget) -> str:
    """组合覆盖键: "{project_type}:{build_target}"。"""
    return f"{project_type.value}:{build_target.value}"


def resolve_build_image(
    project_type: ProjectType,
    build_target: BuildTarget,
    *,
    overrides: dict[str, str] | None = None,
) -> str:
    """按 (project_type, build_target) 推导构建镜像名。

    优先级: overrides 覆盖 > DEFAULT_BUILD_IMAGES 查表 > 空串(调用方 fallback)。

    Returns:
        镜像名 (如 "arc/tauri-builder:linux"); 未注册组合返回空串,
        由调用方 fallback 到 SandboxPolicy.docker_image 原值。
    """
    if overrides:
        key = _override_key(project_type, build_target)
        if key in overrides:
            return overrides[key]
    return DEFAULT_BUILD_IMAGES.get((project_type, build_target), "")


def default_sandbox_config(project_type: ProjectType) -> dict | None:
    """未显式配置 sandbox 时, 按项目类型返回默认 sandbox 配置。

    BINARY_APP 默认启用容器化构建 (mode=docker, target=tauri_linux) —
    原生客户端构建链依赖工具链镜像, 宿主直跑必失败, 故自动启用沙箱。
    其他类型默认 None (维持宿主直跑现状)。

    返回 dict 形式供 application 层与用户显式配置统一走 SandboxPolicy.from_dict。
    用户显式配置 conversation_config["sandbox"] 时, 本函数不介入 (由调用方判断)。
    """
    if project_type == ProjectType.BINARY_APP:
        return {"mode": "docker", "target": BuildTarget.TAURI_LINUX.value}
    return None
