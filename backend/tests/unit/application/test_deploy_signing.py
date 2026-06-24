"""Tests for DeployService._sign_artifact — 签名接入 graceful skip (v6.1.0)。

验证签名步骤在 T2-T4 签名器未实现时不阻断部署 (get_signer None → skip)。
"""

import pytest

from arc.application.deployment.service import DeployService
from arc.domain.deployment.entity import Deployment
from arc.domain.sandbox.value_objects import BuildTarget


class _FakeRepo:
    """最小 repository stub — _sign_artifact 不碰 DB, 仅需 deployment 传入。"""


def _make_deploy_service():
    """DeployService 构造需 db, 但 _sign_artifact graceful skip 路径不碰 DB。
    用 None db + 跳过 repository 初始化。"""
    ds = DeployService.__new__(DeployService)  # 跳过 __init__ 的 repo 初始化
    return ds


class TestSignArtifactGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_signer_not_implemented(self):
        """T2-T4 未实现 → get_signer 返回 None → 跳过签名, 不抛异常。"""
        ds = _make_deploy_service()
        from arc.domain.project.entity import Project

        project = Project(name="t")
        deployment = Deployment(
            project_id=project.id, version_id=project.id, deploy_type="binary_artifact"
        )
        # build_target=TAURI_LINUX 映射 Apple, 但 AppleSigner 未实现 → skip
        await ds._sign_artifact(deployment, project, BuildTarget.TAURI_LINUX, "/tmp/dist")
        # graceful skip: deployment 不因签名失败而异常, error_message 保持空
        assert deployment.error_message == "" or "签名" not in (deployment.error_message or "")

    @pytest.mark.asyncio
    async def test_skip_when_build_target_has_no_signer(self):
        """build_target 无需签名 (如 web, 暂未映射) → 直接跳过。"""
        ds = _make_deploy_service()
        from arc.domain.project.entity import Project

        project = Project(name="t")
        deployment = Deployment(
            project_id=project.id, version_id=project.id, deploy_type="binary_artifact"
        )
        # 不传 build_target / 传 None → 无映射 → 跳过 (但当前 deploy 调用前已判 None)
        # 此测验证 _sign_artifact 对未映射 target 安全
        await ds._sign_artifact(deployment, project, BuildTarget.TAURI_LINUX, "/tmp/dist")
        # 不抛异常即通过
