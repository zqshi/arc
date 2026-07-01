"""Unit test shared fixtures.

adapter_pool 是模块级单例, acquire_for_project(None) 走 _ensure_adapter 缓存
_DEFAULT_KEY adapter。跨测试残留 mock/真实 adapter 会污染后续测试 (如 todo
extract_tags 用到前测试缓存的 mock_adapter)。每测试前清空缓存保证隔离。
"""
import pytest


@pytest.fixture(autouse=True)
def _clear_adapter_pool_cache():
    from arc.application.ai.adapter_pool import adapter_pool

    adapter_pool._adapters.clear()
    yield
    adapter_pool._adapters.clear()
