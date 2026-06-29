"""项目凭证配置 API 集成测试 (T2)。

打通真实链路: route → require_project_role 权限 → DeployService → Project.set_*_creds
→ crypto.encrypt → repository 持久化。验证 CRUD 全路径 + 权限边界 + 枚举校验。
"""
from __future__ import annotations

import uuid


class TestProjectCredentialsCRUD:
    async def test_configure_and_list_signing_creds(self, client):
        """配 Apple 签名凭证 → GET 验证 configured=True, 响应不含明文。"""
        create = await client.post("/api/projects", json={"name": "Cred CRUD"})
        pid = create.json()["id"]

        resp = await client.put(
            f"/api/projects/{pid}/credentials/signing/apple",
            json={"creds": {"apple_dev_id": "DEV123", "apple_team_id": "TEAM456"}},
        )
        assert resp.status_code == 200
        assert resp.json() == {"platform": "apple", "configured": True}

        listed = await client.get(f"/api/projects/{pid}/credentials")
        assert listed.status_code == 200
        body = listed.json()
        assert body["signing"]["apple"] is True
        assert body["signing"]["windows"] is False
        # 响应不含明文
        assert "DEV123" not in listed.text
        assert "TEAM456" not in listed.text

    async def test_configure_distribution_creds(self, client):
        """配 PlayStore 分发凭证 → GET 验证, 独立于签名字段。"""
        create = await client.post("/api/projects", json={"name": "Cred Dist"})
        pid = create.json()["id"]

        resp = await client.put(
            f"/api/projects/{pid}/credentials/distribution/play_store",
            json={"creds": {"play_key_json": "{}", "play_package_name": "com.x"}},
        )
        assert resp.status_code == 200
        assert resp.json() == {"channel": "play_store", "configured": True}

        listed = await client.get(f"/api/projects/{pid}/credentials")
        assert listed.json()["distribution"]["play_store"] is True
        assert listed.json()["distribution"]["app_store"] is False

    async def test_empty_creds_leaves_existing_unchanged(self, client):
        """空 creds 不改变现有配置 (domain set 行为: 空 dict 不存, 非清除)。

        清除能力 (显式 DELETE) 超出 T2 范围, 留作后续增强。
        """
        create = await client.post("/api/projects", json={"name": "Cred Empty"})
        pid = create.json()["id"]

        await client.put(
            f"/api/projects/{pid}/credentials/signing/windows",
            json={"creds": {"win_ev_cert_path": "/c.pfx", "win_ev_password": "p"}},
        )
        assert (await client.get(f"/api/projects/{pid}/credentials")).json()["signing"]["windows"] is True

        # 空 creds → 不改变 (仍 True)
        resp = await client.put(
            f"/api/projects/{pid}/credentials/signing/windows",
            json={"creds": {}},
        )
        assert resp.json()["configured"] is False
        assert (await client.get(f"/api/projects/{pid}/credentials")).json()["signing"]["windows"] is True

    async def test_configure_ios_signing_creds(self, client):
        """v6.19 T7: PUT /credentials/signing/ios (枚举自动放行) → GET signing['ios'] True。

        同时守卫 list_credentials 全 SignerType 迭代 (_enc_field_for 须含 IOS, 否则 KeyError)。
        """
        create = await client.post("/api/projects", json={"name": "Cred iOS"})
        pid = create.json()["id"]

        resp = await client.put(
            f"/api/projects/{pid}/credentials/signing/ios",
            json={"creds": {"ios_cert_path": "/c.p12", "ios_cert_password": "p", "ios_identity": "id"}},
        )
        assert resp.status_code == 200
        assert resp.json() == {"platform": "ios", "configured": True}

        listed = await client.get(f"/api/projects/{pid}/credentials")
        assert listed.json()["signing"]["ios"] is True

    async def test_configure_harmony_signing_creds(self, client):
        """v6.19 T10: PUT /credentials/signing/harmony → GET signing['harmony'] True。"""
        create = await client.post("/api/projects", json={"name": "Cred Harmony"})
        pid = create.json()["id"]

        resp = await client.put(
            f"/api/projects/{pid}/credentials/signing/harmony",
            json={"creds": {"harmony_keystore_path": "/c.p12", "harmony_keystore_password": "p"}},
        )
        assert resp.status_code == 200
        assert resp.json() == {"platform": "harmony", "configured": True}

        listed = await client.get(f"/api/projects/{pid}/credentials")
        assert listed.json()["signing"]["harmony"] is True


class TestProjectCredentialsPermissions:
    async def test_unauthorized_project_returns_401(self, client):
        """访问不存在的 project (非 owner 非 member) → AuthenticationError 401。"""
        random_pid = uuid.uuid4()
        resp = await client.get(f"/api/projects/{random_pid}/credentials")
        assert resp.status_code == 401

    async def test_invalid_platform_returns_422(self, client):
        """非法 platform 枚举值 → 422 (路径参数枚举校验)。"""
        create = await client.post("/api/projects", json={"name": "Cred Enum"})
        pid = create.json()["id"]

        resp = await client.put(
            f"/api/projects/{pid}/credentials/signing/not_a_platform",
            json={"creds": {"x": "y"}},
        )
        assert resp.status_code == 422
