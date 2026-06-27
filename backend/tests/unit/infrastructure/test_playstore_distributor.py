"""Tests for PlayStoreDistributor — Google Play Console 上传 (v6.2.0 T3)。

Play Developer API v3 (httpx + jose RS256 JWT)。mock httpx.AsyncClient + jose.jwt.encode,
真实上传需 service account JSON + 网络。与 T4 (Tauri, httpx) 同构的 mock 模式。
"""

import json

import pytest
from cryptography.fernet import Fernet

from arc.domain.deployment.distributor import DistributorType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.distributor import load_distribution_creds_for_project
from arc.infrastructure.distributor.playstore import PlayStoreDistributor

_TEST_KEY = Fernet.generate_key().decode()

_FAKE_SA = json.dumps(
    {
        "type": "service_account",
        "client_email": "sa@proj.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
        "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n",
        "private_key_id": "keyid123",
    }
)


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _project_with_play_creds(monkeypatch):
    monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
    p = Project(name="t")
    p.set_distribution_creds(
        DistributorType.PLAY_STORE,
        {"play_key_json": _FAKE_SA, "play_package_name": "com.example.app"},
        encrypt,
    )
    return p


class _FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self.text = body if isinstance(body, str) else json.dumps(body)
        self._body = body

    def json(self):
        if isinstance(self._body, (dict, list)):
            return self._body
        return json.loads(self._body)


class _FakeClient:
    """记录所有 post 请求, 按入队顺序返回预设响应。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.posts = []

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.responses.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestPlayStoreGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_play_creds(self):
        """项目未配 Play 凭证 → skip。"""
        d = PlayStoreDistributor()
        project = Project(name="t")
        creds = load_distribution_creds_for_project(project, DistributorType.PLAY_STORE)
        result = await d.upload("/tmp/app.aab", signed=True, credentials=creds)
        assert result.uploaded is False
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_skip_when_missing_package_name(self, monkeypatch):
        """缺 play_package_name → 不算配全 → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(
            DistributorType.PLAY_STORE,
            {"play_key_json": _FAKE_SA},  # 缺 play_package_name
            encrypt,
        )
        creds = load_distribution_creds_for_project(p, DistributorType.PLAY_STORE)
        d = PlayStoreDistributor()
        result = await d.upload("/tmp/app.aab", signed=True, credentials=creds)
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_fail_when_key_json_invalid(self, monkeypatch, tmp_path):
        """play_key_json 非合法 JSON → fail (非 skip)。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(
            DistributorType.PLAY_STORE,
            {"play_key_json": "not-json{", "play_package_name": "com.example.app"},
            encrypt,
        )
        creds = load_distribution_creds_for_project(p, DistributorType.PLAY_STORE)
        artifact = tmp_path / "app.aab"
        artifact.write_bytes(b"fake-aab")
        d = PlayStoreDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)
        assert result.uploaded is False
        assert result.skipped is False
        assert "service account" in result.error or "JSON" in result.error

    @pytest.mark.asyncio
    async def test_fail_when_sa_missing_fields(self, monkeypatch, tmp_path):
        """service account JSON 缺 private_key → fail。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(
            DistributorType.PLAY_STORE,
            {
                "play_key_json": json.dumps({"client_email": "x", "token_uri": "y"}),
                "play_package_name": "com.example.app",
            },
            encrypt,
        )
        creds = load_distribution_creds_for_project(p, DistributorType.PLAY_STORE)
        artifact = tmp_path / "app.aab"
        artifact.write_bytes(b"fake-aab")
        d = PlayStoreDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)
        assert result.uploaded is False
        assert result.skipped is False


class TestPlayStoreUpload:
    @pytest.mark.asyncio
    async def test_upload_invokes_full_chain_when_creds_present(self, monkeypatch, tmp_path):
        """配了凭证 → token→edit→aab→commit 全链路调用, JWT payload 正确。"""
        artifact = tmp_path / "app.aab"
        artifact.write_bytes(b"fake-aab")

        fake = _FakeClient(
            [
                _FakeResp(200, {"access_token": "tok-xyz"}),  # token
                _FakeResp(200, {"id": "edit-1"}),  # create edit
                _FakeResp(200, {"versionCode": 42}),  # upload aab
                _FakeResp(200, {"edit": {}}),  # commit
            ]
        )
        monkeypatch.setattr(
            "arc.infrastructure.distributor.playstore.httpx.AsyncClient",
            lambda **kw: fake,
        )

        captured = {}

        def _fake_encode(payload, key, algorithm=None, headers=None):
            captured["payload"] = payload
            captured["headers"] = headers
            return "JWT-ASSERTION"

        monkeypatch.setattr(
            "arc.infrastructure.distributor.playstore.jwt.encode", _fake_encode
        )

        project = _project_with_play_creds(monkeypatch)
        creds = load_distribution_creds_for_project(project, DistributorType.PLAY_STORE)
        d = PlayStoreDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)

        assert result.uploaded is True
        assert len(fake.posts) == 4

        # 1. token 请求: assertion + jwt-bearer grant
        token_url, token_kw = fake.posts[0]
        assert token_url == "https://oauth2.googleapis.com/token"
        assert token_kw["data"]["assertion"] == "JWT-ASSERTION"
        assert token_kw["data"]["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"

        # JWT payload: iss=client_email, scope=androidpublisher, aud=token_uri
        payload = captured["payload"]
        assert payload["iss"] == "sa@proj.iam.gserviceaccount.com"
        assert "androidpublisher" in payload["scope"]
        assert payload["aud"] == "https://oauth2.googleapis.com/token"

        # 2. create edit: Bearer token + package in url
        edit_url, edit_kw = fake.posts[1]
        assert "com.example.app" in edit_url
        assert "/edits" in edit_url
        assert edit_kw["headers"]["Authorization"] == "Bearer tok-xyz"

        # 3. upload aab: uploadType=media + 产物 content
        aab_url, aab_kw = fake.posts[2]
        assert "/aab" in aab_url
        assert "uploadType=media" in aab_url
        assert aab_kw.get("content") is not None

        # 4. commit: :commit 后缀
        commit_url, _ = fake.posts[3]
        assert ":commit" in commit_url

    @pytest.mark.asyncio
    async def test_upload_http_error_returns_fail(self, monkeypatch, tmp_path):
        """token 成功但 create edit 返回 403 → fail。"""
        artifact = tmp_path / "app.aab"
        artifact.write_bytes(b"fake-aab")

        fake = _FakeClient(
            [
                _FakeResp(200, {"access_token": "tok"}),  # token ok
                _FakeResp(403, "forbidden"),  # create edit fails
            ]
        )
        monkeypatch.setattr(
            "arc.infrastructure.distributor.playstore.httpx.AsyncClient",
            lambda **kw: fake,
        )
        monkeypatch.setattr(
            "arc.infrastructure.distributor.playstore.jwt.encode",
            lambda *a, **k: "JWT",
        )

        project = _project_with_play_creds(monkeypatch)
        creds = load_distribution_creds_for_project(project, DistributorType.PLAY_STORE)
        d = PlayStoreDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)

        assert result.uploaded is False
        assert result.skipped is False
        assert "403" in result.error or "上传" in result.error

    @pytest.mark.asyncio
    async def test_upload_token_error_returns_fail(self, monkeypatch, tmp_path):
        """token 接口 401 → fail (鉴权失败)。"""
        artifact = tmp_path / "app.aab"
        artifact.write_bytes(b"fake-aab")

        fake = _FakeClient([_FakeResp(401, "unauthorized")])
        monkeypatch.setattr(
            "arc.infrastructure.distributor.playstore.httpx.AsyncClient",
            lambda **kw: fake,
        )
        monkeypatch.setattr(
            "arc.infrastructure.distributor.playstore.jwt.encode",
            lambda *a, **k: "JWT",
        )

        project = _project_with_play_creds(monkeypatch)
        creds = load_distribution_creds_for_project(project, DistributorType.PLAY_STORE)
        d = PlayStoreDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)

        assert result.uploaded is False
        assert result.skipped is False
        assert "token" in result.error or "401" in result.error


class TestPlayStoreType:
    def test_distributor_type(self):
        assert PlayStoreDistributor().distributor_type == DistributorType.PLAY_STORE
