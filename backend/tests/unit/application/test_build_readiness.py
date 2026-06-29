"""Tests for application/build/readiness — 构建目标就绪检测 (v6.19 T11 方案3)。

mock settings (SimpleNamespace) 覆盖就绪判定四态:
docker ready / CI hosted 凭证齐 ready / CI self-hosted 凭证齐仍 blocked /
CI 凭证缺 blocked + 本地 storage blocked。application 层纯逻辑, mock 外部 settings。
"""
from types import SimpleNamespace

from arc.application.build.readiness import (
    BuildTargetReadinessService,
    TargetReadiness,
    assess_target_readiness,
)
from arc.domain.sandbox.value_objects import BuildTarget


def _settings(**kw) -> SimpleNamespace:
    """造 fake settings (仅 readiness 用到的字段, 默认全空 = 凭证缺失)。"""
    base = dict(
        gha_token="",
        storage_endpoint="",
        storage_access_key="",
        storage_secret_key="",
        storage_bucket="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


_CLOUD = dict(
    gha_token="ghp_xxx",
    storage_endpoint="https://s3.example.com",
    storage_access_key="ak",
    storage_secret_key="sk",
    storage_bucket="bkt",
)


class TestAssessTargetReadiness:
    def test_docker_target_always_ready(self):
        """DOCKER target 无外部依赖, 恒就绪 (即使凭证全空)。"""
        r = assess_target_readiness(BuildTarget.TAURI_LINUX, _settings())
        assert r.ready is True
        assert r.reason == ""

    def test_web_and_apk_docker_ready(self):
        for t in (BuildTarget.WEB, BuildTarget.CAPACITOR_APK):
            assert assess_target_readiness(t, _settings()).ready is True

    def test_ci_hosted_ready_when_creds_complete(self):
        """CI hosted target (windows/ios) 凭证齐即就绪。"""
        s = _settings(**_CLOUD)
        assert assess_target_readiness(BuildTarget.TAURI_WINDOWS, s).ready is True
        assert assess_target_readiness(BuildTarget.CAPACITOR_IOS, s).ready is True

    def test_ci_self_hosted_blocked_even_with_creds(self):
        """CI self-hosted target (鸿蒙) 凭证齐仍 blocked (需自建 DevEco 工具链)。"""
        r = assess_target_readiness(BuildTarget.HARMONY_HAP, _settings(**_CLOUD))
        assert r.ready is False
        assert "DevEco" in r.reason

    def test_ci_blocked_when_gha_token_missing(self):
        """CI target 缺 GHA token → blocked。"""
        s = _settings(
            storage_endpoint="https://s3.example.com",
            storage_access_key="ak", storage_secret_key="sk", storage_bucket="bkt",
        )
        r = assess_target_readiness(BuildTarget.TAURI_WINDOWS, s)
        assert r.ready is False
        assert "ARC_GHA_TOKEN" in r.reason

    def test_ci_blocked_when_storage_fields_missing(self):
        """CI target storage 字段缺失 → blocked。"""
        s = _settings(gha_token="ghp_xxx", storage_endpoint="https://s3.example.com")
        r = assess_target_readiness(BuildTarget.CAPACITOR_IOS, s)
        assert r.ready is False
        assert "ARC_STORAGE" in r.reason

    def test_ci_blocked_when_storage_endpoint_local(self):
        """CI target storage endpoint 本地 → blocked (CI runner 不可达, T3-g 设计5)。"""
        for endpoint in ("http://localhost:9000", "http://127.0.0.1:9000", "http://minio:9000"):
            s = _settings(
                gha_token="ghp_xxx", storage_endpoint=endpoint,
                storage_access_key="ak", storage_secret_key="sk", storage_bucket="bkt",
            )
            r = assess_target_readiness(BuildTarget.TAURI_WINDOWS, s)
            assert r.ready is False, endpoint
            assert "本地地址" in r.reason


class TestBuildTargetReadinessService:
    def test_list_readiness_covers_all_targets(self):
        svc = BuildTargetReadinessService(_settings())
        result = svc.list_readiness()
        assert len(result) == len(list(BuildTarget))
        assert all(isinstance(r, TargetReadiness) for r in result)
        targets = {r.target for r in result}
        assert BuildTarget.TAURI_LINUX in targets
        assert BuildTarget.HARMONY_HAP in targets

    def test_list_readiness_creds_empty_docker_ready_ci_blocked(self):
        """凭证全空: docker target ready, CI target 全 blocked。"""
        result = BuildTargetReadinessService(_settings()).list_readiness()
        by_target = {r.target: r for r in result}
        assert by_target[BuildTarget.TAURI_LINUX].ready is True
        assert by_target[BuildTarget.TAURI_WINDOWS].ready is False
        assert by_target[BuildTarget.CAPACITOR_IOS].ready is False
        assert by_target[BuildTarget.HARMONY_HAP].ready is False

    def test_list_readiness_creds_complete_hosted_ready(self):
        """凭证齐: docker + hosted CI ready, 鸿蒙仍 blocked (self-hosted)。"""
        result = BuildTargetReadinessService(_settings(**_CLOUD)).list_readiness()
        by_target = {r.target: r for r in result}
        assert by_target[BuildTarget.TAURI_LINUX].ready is True
        assert by_target[BuildTarget.TAURI_WINDOWS].ready is True
        assert by_target[BuildTarget.CAPACITOR_IOS].ready is True
        assert by_target[BuildTarget.HARMONY_HAP].ready is False
