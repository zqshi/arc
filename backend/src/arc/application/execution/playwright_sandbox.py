"""Playwright 沙盒验证服务 — 基于 playwright-mcp 设计。

来源: microsoft/playwright-mcp
用途:
  - UI 设计阶段: 渲染 HTML prototype → 截图验证
  - 测试阶段: 执行 E2E 验证 → 生成 pass/fail 证据
  - 部署阶段: 健康检查 → 截图 + 状态码

设计原则:
  - 沙盒隔离: 每次验证在独立子进程中启动 playwright
  - 仅交付结果: 用户不感知浏览器启动/关闭过程
  - 超时保护: 单次验证最长 30s
  - 无状态: 每次调用独立，不复用浏览器实例
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PLAYWRIGHT_TIMEOUT_S = 30


@dataclass
class VerificationResult:
    """验证结果 — 仅包含用户需要看到的信息"""

    success: bool
    evidence_type: str  # "screenshot" | "assertion" | "health_check"
    summary: str
    details: dict = field(default_factory=dict)
    screenshot_path: str | None = None
    error: str | None = None


async def render_and_screenshot(
    html_content: str,
    *,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    output_dir: str | None = None,
) -> VerificationResult:
    """渲染 HTML prototype 并截图 — 沙盒隔离执行。

    用于 UI 设计阶段验证 wireframe 可渲染性。
    """
    if not output_dir:
        output_dir = tempfile.mkdtemp(prefix="arc_playwright_")

    html_file = Path(output_dir) / "prototype.html"
    html_file.write_text(html_content, encoding="utf-8")
    screenshot_file = Path(output_dir) / "screenshot.png"

    script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={{"width": {viewport_width}, "height": {viewport_height}}})
        await page.goto("file://{html_file.resolve()}")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="{screenshot_file.resolve()}", full_page=True)
        await browser.close()
        print("OK")

asyncio.run(main())
"""

    try:
        result = await _run_in_sandbox(script, timeout=PLAYWRIGHT_TIMEOUT_S)
        if result.returncode == 0 and screenshot_file.exists():
            return VerificationResult(
                success=True,
                evidence_type="screenshot",
                summary=f"Prototype 渲染成功 ({viewport_width}x{viewport_height})",
                screenshot_path=str(screenshot_file),
            )
        return VerificationResult(
            success=False,
            evidence_type="screenshot",
            summary="Prototype 渲染失败",
            error=result.stderr[:500] if result.stderr else "Unknown error",
        )
    except asyncio.TimeoutError:
        return VerificationResult(
            success=False,
            evidence_type="screenshot",
            summary="渲染超时",
            error=f"超过 {PLAYWRIGHT_TIMEOUT_S}s 未完成",
        )
    except Exception as exc:
        return VerificationResult(
            success=False,
            evidence_type="screenshot",
            summary="渲染异常",
            error=str(exc),
        )


async def verify_url_health(
    url: str,
    *,
    expected_status: int = 200,
    expected_text: str | None = None,
) -> VerificationResult:
    """访问 URL 验证健康状态 — 沙盒隔离执行。

    用于部署阶段健康检查。
    """
    script = f"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto("{url}", wait_until="domcontentloaded", timeout=15000)
        status = response.status if response else 0
        title = await page.title()
        text_content = await page.inner_text("body")
        await browser.close()
        print(json.dumps({{"status": status, "title": title, "body_preview": text_content[:200]}}))

asyncio.run(main())
"""

    try:
        result = await _run_in_sandbox(script, timeout=PLAYWRIGHT_TIMEOUT_S)
        if result.returncode != 0:
            return VerificationResult(
                success=False,
                evidence_type="health_check",
                summary=f"健康检查失败: {url}",
                error=result.stderr[:500] if result.stderr else "Process failed",
            )

        data = json.loads(result.stdout.strip())
        status_ok = data.get("status") == expected_status
        text_ok = expected_text in data.get("body_preview", "") if expected_text else True

        return VerificationResult(
            success=status_ok and text_ok,
            evidence_type="health_check",
            summary=f"HTTP {data.get('status')} | Title: {data.get('title', '?')}",
            details=data,
        )
    except asyncio.TimeoutError:
        return VerificationResult(
            success=False,
            evidence_type="health_check",
            summary=f"健康检查超时: {url}",
            error=f"超过 {PLAYWRIGHT_TIMEOUT_S}s",
        )
    except Exception as exc:
        return VerificationResult(
            success=False,
            evidence_type="health_check",
            summary=f"健康检查异常: {url}",
            error=str(exc),
        )


async def run_assertions(
    url: str,
    assertions: list[dict],
) -> VerificationResult:
    """执行 E2E 断言 — 沙盒隔离执行。

    assertions 格式:
    [
        {"type": "text_visible", "text": "登录"},
        {"type": "element_visible", "role": "button", "name": "提交"},
        {"type": "title_contains", "text": "Dashboard"},
    ]
    """
    assertion_code = ""
    for i, a in enumerate(assertions):
        atype = a.get("type", "")
        if atype == "text_visible":
            text = a.get("text", "").replace('"', '\\"')
            assertion_code += f'    results.append({{"idx": {i}, "type": "text_visible", "text": "{text}", "pass": await page.locator("text={text}").count() > 0}})\n'
        elif atype == "element_visible":
            role = a.get("role", "")
            name = a.get("name", "").replace('"', '\\"')
            assertion_code += f'    results.append({{"idx": {i}, "type": "element_visible", "role": "{role}", "name": "{name}", "pass": await page.get_by_role("{role}", name="{name}").count() > 0}})\n'
        elif atype == "title_contains":
            text = a.get("text", "").replace('"', '\\"')
            assertion_code += f'    title = await page.title()\n    results.append({{"idx": {i}, "type": "title_contains", "text": "{text}", "pass": "{text}" in title}})\n'

    script = f"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("{url}", wait_until="domcontentloaded", timeout=15000)
        results = []
{assertion_code}
        await browser.close()
        print(json.dumps(results))

asyncio.run(main())
"""

    try:
        result = await _run_in_sandbox(script, timeout=PLAYWRIGHT_TIMEOUT_S)
        if result.returncode != 0:
            return VerificationResult(
                success=False,
                evidence_type="assertion",
                summary="E2E 断言执行失败",
                error=result.stderr[:500] if result.stderr else "Process failed",
            )

        assertion_results = json.loads(result.stdout.strip())
        all_passed = all(r.get("pass", False) for r in assertion_results)
        passed_count = sum(1 for r in assertion_results if r.get("pass"))
        total = len(assertion_results)

        return VerificationResult(
            success=all_passed,
            evidence_type="assertion",
            summary=f"E2E 断言: {passed_count}/{total} passed",
            details={"assertions": assertion_results},
        )
    except asyncio.TimeoutError:
        return VerificationResult(
            success=False,
            evidence_type="assertion",
            summary="E2E 断言超时",
            error=f"超过 {PLAYWRIGHT_TIMEOUT_S}s",
        )
    except Exception as exc:
        return VerificationResult(
            success=False,
            evidence_type="assertion",
            summary="E2E 断言异常",
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# 沙盒执行
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str


async def _run_in_sandbox(script: str, *, timeout: int = 30) -> SandboxResult:
    """在独立子进程中执行 Python 脚本 — 沙盒隔离。

    - 独立进程，不共享主进程的内存/状态
    - 超时自动 kill
    - 仅返回 stdout/stderr 文本结果
    """
    proc = await asyncio.create_subprocess_exec(
        "python3", "-c", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise

    return SandboxResult(
        returncode=proc.returncode or 0,
        stdout=stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else "",
        stderr=stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "",
    )


# ---------------------------------------------------------------------------
# 可用性检测
# ---------------------------------------------------------------------------


async def is_playwright_available() -> bool:
    """检测当前环境是否安装了 playwright。"""
    try:
        result = await _run_in_sandbox(
            "from playwright.sync_api import sync_playwright; print('ok')",
            timeout=10,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False
