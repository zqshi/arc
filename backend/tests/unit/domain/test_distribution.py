"""Tests for domain/deployment/distribution — 分发清单值对象 (v6.2.0 T5)。

artifact 显式建模: 分发产物 + 渠道结果用值对象承载。frozen 不可变。
"""

import pytest

from arc.domain.deployment.distribution import (
    ArtifactEntry,
    DistributionManifest,
    DistributionOutcome,
)
from arc.domain.deployment.distributor import DistributorType


class TestArtifactEntry:
    def test_signed_artifact(self):
        a = ArtifactEntry(
            platform="darwin-aarch64",
            filename="App.dmg",
            download_url="https://cdn/App.dmg",
            signed=True,
            signer_type="apple",
            signature_id="ticket-123",
            size=1024,
        )
        assert a.is_unsigned is False
        assert a.signed is True

    def test_unsigned_artifact(self):
        a = ArtifactEntry(
            platform="windows-x86_64",
            filename="App.exe",
            download_url="https://cdn/App.exe",
        )
        assert a.is_unsigned is True
        assert a.signed is False
        assert a.signer_type == ""


class TestDistributionOutcome:
    def test_uploaded(self):
        o = DistributionOutcome(
            channel=DistributorType.PLAY_STORE, uploaded=True, store_url="https://play/..."
        )
        assert o.uploaded is True
        assert o.skipped is False

    def test_skipped(self):
        o = DistributionOutcome(
            channel=DistributorType.APP_STORE, skipped=True, error="凭证未配"
        )
        assert o.uploaded is False
        assert o.skipped is True

    def test_failed(self):
        o = DistributionOutcome(
            channel=DistributorType.TAURI_UPDATER, error="HTTP 500"
        )
        assert o.uploaded is False
        assert o.skipped is False


class TestDistributionManifest:
    def _manifest(self, *, unsigned=False):
        a = ArtifactEntry(
            platform="darwin-aarch64",
            filename="App.dmg",
            download_url="https://cdn/App.dmg",
            signed=not unsigned,
            signer_type="apple" if not unsigned else "",
        )
        return DistributionManifest(
            version_name="1.0.0",
            version_id="v-uuid",
            changelog="fix",
            pub_date="2026-06-25T00:00:00Z",
            artifacts=(a,),
            distributions=(
                DistributionOutcome(
                    channel=DistributorType.TAURI_UPDATER, uploaded=True, store_url="https://up"
                ),
            ),
        )

    def test_has_unsigned_false_when_all_signed(self):
        m = self._manifest(unsigned=False)
        assert m.has_unsigned() is False

    def test_has_unsigned_true_when_any_unsigned(self):
        m = self._manifest(unsigned=True)
        assert m.has_unsigned() is True

    def test_channel_outcome_found(self):
        m = self._manifest()
        o = m.channel_outcome(DistributorType.TAURI_UPDATER)
        assert o is not None
        assert o.uploaded is True

    def test_channel_outcome_not_found(self):
        m = self._manifest()
        assert m.channel_outcome(DistributorType.PLAY_STORE) is None

    def test_frozen(self):
        m = self._manifest()
        with pytest.raises(Exception):
            m.version_name = "2.0.0"  # type: ignore[misc]
