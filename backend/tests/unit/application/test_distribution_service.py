"""Tests for DistributionService — 制品分发层编排 (v6.2.0 T5)。

mock storage (build_manifest 的 get_public_url + publish 的 storage) + distributor,
真实上传需制品仓 + 商店凭证。覆盖 build/distribute/generate_*/publish/finalize。
"""

import pytest

from arc.domain.deployment.distribution import (
    ArtifactEntry,
    DistributionManifest,
    DistributionOutcome,
)
from arc.domain.deployment.distributor import (
    DistributionCredentials,
    DistributeResult,
    DistributorType,
)
from arc.domain.deployment.signer import SignResult, SignerType
from arc.application.deployment.distribution import DistributionService


# -- 测试用 fixture ----------------------------------------------------


class _FakeDist:
    """假分发器: 记录 upload 调用, 返回预设 DistributeResult。"""

    def __init__(self, result=None):
        self._result = result or DistributeResult(uploaded=True, store_url="https://up/x")
        self.calls = []

    async def upload(self, artifact_path, signed, credentials):
        self.calls.append((artifact_path, signed, credentials))
        return self._result


class _FakeStorage:
    """假制品仓: 记录 async_upload, 返回 URL。"""

    def __init__(self):
        self.uploads = []

    async def async_upload(self, key, content, content_type):
        self.uploads.append((key, content, content_type))
        return f"https://cdn/{key}"


def _sign_results(*pairs):
    """[(SignerType, SignResult)] → [(SignerType, path, SignResult)]。"""
    return [(st, f"/tmp/x.{st.value}", r) for st, r in pairs]


def _make_manifest(artifacts=None, distributions=None, unsigned=False):
    a = artifacts or (
        ArtifactEntry(
            platform="darwin-aarch64",
            filename="App.dmg",
            download_url="https://cdn/App.dmg",
            signed=not unsigned,
            signer_type="apple" if not unsigned else "",
            signature_id="sig1" if not unsigned else "",
            size=100,
        ),
    )
    return DistributionManifest(
        version_name="1.2.0",
        version_id="v-uuid",
        changelog="release notes",
        pub_date="2026-06-25T00:00:00Z",
        artifacts=a,
        distributions=distributions or (),
    )


# -- build_manifest ----------------------------------------------------


class TestBuildManifest:
    def test_scans_artifacts_and_matches_sign_state(self, monkeypatch, tmp_path):
        (tmp_path / "App.dmg").write_bytes(b"mac")
        (tmp_path / "App.exe").write_bytes(b"win")
        (tmp_path / "App.deb").write_bytes(b"linux")  # 无签名平台 → unsigned
        monkeypatch.setattr(
            "arc.infrastructure.storage.get_public_url",
            lambda key: f"https://cdn/{key}",
        )

        from arc.domain.deployment.entity import Deployment
        from arc.domain.project.entity import Version

        deployment = Deployment(project_id=__import__("uuid").uuid4(), version_id=__import__("uuid").uuid4())
        version = Version(project_id=deployment.project_id, name="1.2.0")
        version.changelog = "release notes"
        sign_results = _sign_results(
            (SignerType.APPLE, SignResult(signed=True, signature_id="tkt")),
            (SignerType.WINDOWS, SignResult(signed=True)),
        )

        svc = DistributionService()
        manifest = svc.build_manifest(
            deployment, version, sign_results, "artifacts/p/d", str(tmp_path)
        )

        names = {a.filename for a in manifest.artifacts}
        assert names == {"App.dmg", "App.exe", "App.deb"}
        by_name = {a.filename: a for a in manifest.artifacts}
        assert by_name["App.dmg"].signed is True
        assert by_name["App.dmg"].signer_type == "apple"
        assert by_name["App.dmg"].signature_id == "tkt"
        assert by_name["App.exe"].signed is True
        assert by_name["App.deb"].signed is False  # linux 无签名
        assert by_name["App.dmg"].download_url == "https://cdn/artifacts/p/d/App.dmg"
        assert manifest.version_name == "1.2.0"
        assert manifest.changelog == "release notes"

    def test_unsigned_when_sign_skipped(self, monkeypatch, tmp_path):
        (tmp_path / "App.dmg").write_bytes(b"mac")
        monkeypatch.setattr(
            "arc.infrastructure.storage.get_public_url", lambda key: f"https://cdn/{key}"
        )
        from arc.domain.deployment.entity import Deployment
        from arc.domain.project.entity import Version

        deployment = Deployment(project_id=__import__("uuid").uuid4(), version_id=__import__("uuid").uuid4())
        version = Version(project_id=deployment.project_id, name="1.0.0")
        # APPLE 签名 skipped (凭证未配) → 产物 unsigned
        sign_results = _sign_results((SignerType.APPLE, SignResult.skip("no creds")))

        svc = DistributionService()
        manifest = svc.build_manifest(deployment, version, sign_results, "p/d", str(tmp_path))
        assert manifest.artifacts[0].signed is False
        assert manifest.has_unsigned() is True


# -- distribute --------------------------------------------------------


class TestDistribute:
    @pytest.mark.asyncio
    async def test_distribute_calls_distributor_per_channel(self, monkeypatch, tmp_path):
        (tmp_path / "App.dmg").write_bytes(b"mac")
        (tmp_path / "App.apk").write_bytes(b"android")

        fake_tauri = _FakeDist()
        fake_play = _FakeDist()

        def _get_distributor(channel):
            return {DistributorType.TAURI_UPDATER: fake_tauri, DistributorType.PLAY_STORE: fake_play}.get(channel)

        monkeypatch.setattr("arc.infrastructure.distributor.get_distributor", _get_distributor)
        monkeypatch.setattr(
            "arc.infrastructure.distributor.load_distribution_creds_for_project",
            lambda project, channel: DistributionCredentials(),
        )

        svc = DistributionService()
        outcomes = await svc.distribute(
            str(tmp_path), project=object(), sign_results=[]
        )

        channels = {o.channel for o in outcomes}
        assert DistributorType.TAURI_UPDATER in channels
        assert DistributorType.PLAY_STORE in channels
        assert all(o.uploaded for o in outcomes)
        # .dmg → tauri, .apk → play
        assert any("App.dmg" in c[0] for c in fake_tauri.calls)
        assert any("App.apk" in c[0] for c in fake_play.calls)

    @pytest.mark.asyncio
    async def test_distribute_graceful_on_exception(self, monkeypatch, tmp_path):
        (tmp_path / "App.dmg").write_bytes(b"mac")

        class _BoomDist:
            async def upload(self, *a, **k):
                raise RuntimeError("network down")

        monkeypatch.setattr(
            "arc.infrastructure.distributor.get_distributor",
            lambda ch: _BoomDist(),
        )
        monkeypatch.setattr(
            "arc.infrastructure.distributor.load_distribution_creds_for_project",
            lambda project, channel: DistributionCredentials(),
        )

        svc = DistributionService()
        outcomes = await svc.distribute(str(tmp_path), project=object(), sign_results=[])

        assert len(outcomes) == 1
        assert outcomes[0].uploaded is False
        assert outcomes[0].skipped is False
        assert "异常" in outcomes[0].error


# -- generate_* --------------------------------------------------------


class TestGenerate:
    def test_download_page_lists_artifacts_and_unsigned_warning(self):
        manifest = _make_manifest(unsigned=True)
        html = DistributionService().generate_download_page(manifest)
        assert "App.dmg" in html
        assert "unsigned" in html
        assert "含未签名产物" in html  # warning
        assert "https://cdn/App.dmg" in html

    def test_download_page_no_warning_when_all_signed(self):
        manifest = _make_manifest(unsigned=False)
        html = DistributionService().generate_download_page(manifest)
        assert "含未签名产物" not in html
        assert "signed" in html

    def test_manifest_json_roundtrip_structure(self):
        manifest = _make_manifest()
        import json

        data = json.loads(DistributionService().generate_manifest_json(manifest))
        assert data["version_name"] == "1.2.0"
        assert data["changelog"] == "release notes"
        assert data["artifacts"][0]["filename"] == "App.dmg"

    def test_latest_json_tauri_format(self):
        manifest = _make_manifest()
        import json

        data = json.loads(DistributionService().generate_latest_json(manifest))
        assert data["version"] == "1.2.0"
        assert data["notes"] == "release notes"
        assert "darwin-aarch64" in data["platforms"]
        assert data["platforms"]["darwin-aarch64"]["url"] == "https://cdn/App.dmg"

    def test_appcast_xml_has_darwin_item_only(self):
        manifest = _make_manifest(
            artifacts=(
                ArtifactEntry(platform="darwin-aarch64", filename="App.dmg", download_url="https://cdn/App.dmg", signed=True, signature_id="ed1", size=100),
                ArtifactEntry(platform="linux-x86_64", filename="App.AppImage", download_url="https://cdn/App.AppImage", signed=False, size=200),
            )
        )
        xml = DistributionService().generate_appcast(manifest)
        assert "<rss" in xml
        assert "App.dmg" in xml
        assert "ed1" in xml  # edSignature
        assert "App.AppImage" not in xml  # linux 不进 appcast


# -- publish / finalize ------------------------------------------------


class TestPublishFinalize:
    @pytest.mark.asyncio
    async def test_publish_uploads_four_files(self, tmp_path):
        manifest = _make_manifest()
        storage = _FakeStorage()
        svc = DistributionService(storage=storage)
        urls = await svc.publish(manifest, "artifacts/p/d")
        assert set(urls) == {"download.html", "manifest.json", "latest.json", "appcast.xml"}
        keys = {k for k, _, _ in storage.uploads}
        assert keys == {
            "artifacts/p/d/download.html",
            "artifacts/p/d/manifest.json",
            "artifacts/p/d/latest.json",
            "artifacts/p/d/appcast.xml",
        }
        assert all(u.startswith("https://cdn/") for u in urls.values())

    @pytest.mark.asyncio
    async def test_finalize_orchestrates_full_flow(self, monkeypatch, tmp_path):
        (tmp_path / "App.dmg").write_bytes(b"mac")
        monkeypatch.setattr(
            "arc.infrastructure.storage.get_public_url", lambda key: f"https://cdn/{key}"
        )
        fake_dist = _FakeDist()
        monkeypatch.setattr(
            "arc.infrastructure.distributor.get_distributor", lambda ch: fake_dist
        )
        monkeypatch.setattr(
            "arc.infrastructure.distributor.load_distribution_creds_for_project",
            lambda project, channel: DistributionCredentials(),
        )
        from arc.domain.deployment.entity import Deployment
        from arc.domain.project.entity import Version

        deployment = Deployment(project_id=__import__("uuid").uuid4(), version_id=__import__("uuid").uuid4())
        version = Version(project_id=deployment.project_id, name="1.2.0")
        version.changelog = "notes"
        sign_results = _sign_results((SignerType.APPLE, SignResult(signed=True, signature_id="t")))

        svc = DistributionService(storage=_FakeStorage())
        manifest = await svc.finalize(
            deployment, version, project=object(), local_dir=str(tmp_path),
            sign_results=sign_results, storage_prefix="artifacts/p/d",
        )

        assert manifest.artifacts[0].signed is True
        assert len(manifest.distributions) == 1  # .dmg → tauri
        assert manifest.distributions[0].uploaded is True
        assert manifest.download_page_url.startswith("https://cdn/")
