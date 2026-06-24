"""Apple 签名器 — codesign + xcrun notarytool (v6.1.0 T2)。

签名链路:
1. 凭证未配 → SignResult.skip (graceful, 不阻断构建)
2. codesign --sign {identity} --force {artifact}  (Developer ID Application 签名)
3. xcrun notarytool submit {artifact} --apple-id {team_id} --team-id {team_id}
   --password {app_password} --wait  (公证, --wait 同步等待结果避免轮询)
4. 任一失败 → SignResult.fail (signed=False, 不抛异常)

注意: 真实签名需 macOS + 钥匙串导入 Developer ID 证书。notarytool --wait
可能数分钟 (Apple 服务器排队), 真实验证标 slow 手动跑。
此处 mock subprocess 验证命令构造 + graceful skip 逻辑。
"""
from __future__ import annotations

import asyncio
import logging
import subprocess

from arc.domain.deployment.signer import SignResult, SigningCredentials, Signer, SignerType

logger = logging.getLogger(__name__)


class AppleSigner(Signer):
    """Apple Developer ID 签名 + 公证。"""

    signer_type = SignerType.APPLE

    async def sign(self, artifact_path: str, credentials: SigningCredentials) -> SignResult:
        if not credentials.has_apple():
            return SignResult.skip("Apple 凭证未配全 (需 apple_dev_id + apple_team_id + apple_app_password)")

        # 1. codesign 签名
        codesign_argv = [
            "codesign", "--sign", credentials.apple_dev_id,
            "--force", "--deep", "--timestamp", artifact_path,
        ]
        cs_result = await asyncio.to_thread(self._run, codesign_argv)
        if not cs_result.ok:
            return SignResult.fail(f"codesign failed: {cs_result.stderr}")

        # 2. notarytool 提交公证 (--wait 同步等待)
        notary_argv = [
            "xcrun", "notarytool", "submit", artifact_path,
            "--apple-id", credentials.apple_team_id,  # Apple ID (Team ID 兼用)
            "--team-id", credentials.apple_team_id,
            "--password", credentials.apple_app_password,
            "--wait",
        ]
        nt_result = await asyncio.to_thread(self._run, notary_argv)
        if not nt_result.ok:
            # 签名已成功但公证失败 — 记 fail 但产物已签名
            logger.warning("notarytool failed (artifact signed but not notarized): %s", nt_result.stderr)
            return SignResult.fail(f"notarytool failed: {nt_result.stderr}")

        return SignResult(
            signed=True,
            signature_id=nt_result.stdout.strip().splitlines()[0] if nt_result.stdout else "",
            signed_path=artifact_path,
        )

    @staticmethod
    def _run(argv: list[str]) -> _CmdResult:
        """同步执行命令, 返回结果 (复用 runtime.py subprocess.run 风格)。"""
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=600)
            return _CmdResult(
                ok=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr.strip(),
            )
        except FileNotFoundError:
            return _CmdResult(ok=False, stdout="", stderr="codesign/notarytool 未安装 (非 macOS?)")
        except subprocess.TimeoutExpired:
            return _CmdResult(ok=False, stdout="", stderr="notarytool --wait 超时 (Apple 服务器排队)")


class _CmdResult:
    """命令执行结果 (内部, 避免 dataclass 开销)。"""

    __slots__ = ("ok", "stdout", "stderr")

    def __init__(self, ok: bool, stdout: str, stderr: str):
        self.ok = ok
        self.stdout = stdout
        self.stderr = stderr
