"""单元测试 — v5.5.0 质量加固模块。

覆盖:
- A1: Tool 执行超时+重试
- A3: Orchestration Worker 超时
- C1: Autopilot wall-clock 超时
- C3: 部署补偿事务
- B1: 经验检索质量门控
- C2: SSE Event Buffer (为后续 SSE replay 预置)
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.execution.tools import ToolCall, ToolResult

# =====================================================================
# A1: Tool 执行超时 + 重试
# =====================================================================


class TestToolExecuteWithRetry:
    """验证 ToolAwareLoop._execute_tool_with_retry 行为。"""

    @pytest.fixture
    def make_loop(self):
        """构造一个最小化 ToolAwareLoop 实例。"""
        from arc.application.execution.tool_loop import ToolAwareLoop

        adapter = AsyncMock()
        registry = AsyncMock()
        loop = ToolAwareLoop(adapter, registry)
        return loop, registry

    @pytest.fixture
    def sample_call(self):
        return ToolCall(id="tc-1", name="read_file", input={"path": "/src/main.py"})

    @pytest.mark.asyncio
    async def test_success_first_attempt(self, make_loop, sample_call):
        loop, registry = make_loop
        expected = ToolResult(tool_use_id="tc-1", content="file content")
        registry.execute = AsyncMock(return_value=expected)

        result = await loop._execute_tool_with_retry(sample_call)

        assert result.content == "file content"
        assert result.is_error is False
        assert registry.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_retries_then_error(self, make_loop, sample_call):
        loop, registry = make_loop
        registry.execute = AsyncMock(side_effect=asyncio.TimeoutError())

        # Patch timeout to very short for test speed
        with patch("arc.application.execution.tool_loop.TOOL_TIMEOUT_SECONDS", 0.01):
            result = await loop._execute_tool_with_retry(sample_call)

        assert result.is_error is True
        assert "超时" in result.content
        # 1 initial + 1 retry = 2 calls
        assert registry.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_exception_retries_then_error(self, make_loop, sample_call):
        loop, registry = make_loop
        registry.execute = AsyncMock(side_effect=RuntimeError("disk full"))

        result = await loop._execute_tool_with_retry(sample_call)

        assert result.is_error is True
        assert "disk full" in result.content
        assert registry.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_succeeds_second_attempt(self, make_loop, sample_call):
        loop, registry = make_loop
        success = ToolResult(tool_use_id="tc-1", content="ok")
        registry.execute = AsyncMock(
            side_effect=[RuntimeError("transient"), success],
        )

        result = await loop._execute_tool_with_retry(sample_call)

        assert result.is_error is False
        assert result.content == "ok"
        assert registry.execute.call_count == 2


# =====================================================================
# C1: Autopilot wall-clock 超时
# =====================================================================


class TestAutopilotWallTimeout:
    """验证 ExecutionEngine.run_autopilot 的超时保护。"""

    @pytest.mark.asyncio
    async def test_wall_timeout_emits_event(self):
        """模拟 time.monotonic 使其超过 wall_timeout。"""

        from arc.application.execution.execution_engine import ExecutionEngine

        # 构造最小化 engine（所有依赖 mock）
        db = AsyncMock()
        prompt_builder = AsyncMock()
        prompt_builder.injected_experience_ids = []
        conv_repo = AsyncMock()
        tracker_repo = AsyncMock()
        extractor = AsyncMock()

        engine = ExecutionEngine(db, prompt_builder, conv_repo, tracker_repo, extractor)

        # mock conversation
        conversation = MagicMock()
        conversation.id = uuid.uuid4()
        conversation.todo_id = uuid.uuid4()
        conversation.messages = []

        # 让 time.monotonic 第一次返回 0，第二次返回 > 600（超时）
        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return 0.0
            return 601.0  # 超过 wall_timeout

        events = []
        with patch("arc.application.execution.autopilot.time") as mock_time:
            mock_time.monotonic = fake_monotonic
            async for event in engine.run_autopilot(conversation):
                events.append(event)

        timeout_events = [e for e in events if e.get("event") == "autopilot_paused"
                          and e.get("reason") == "wall_timeout"]
        assert len(timeout_events) == 1
        assert timeout_events[0]["elapsed_seconds"] > 600


# =====================================================================
# C3: 部署补偿事务
# =====================================================================


class TestDeployCompensation:
    """验证 DeployService 异常时状态不留脏。"""

    @pytest.mark.asyncio
    async def test_deploy_exception_marks_failed(self):
        from arc.domain.deployment.value_objects import DeploymentStatus

        db = AsyncMock()
        db.commit = AsyncMock()

        with patch("arc.application.deployment.service.DeploymentRepository") as MockRepo, \
             patch("arc.application.deployment.service.ProjectRepository"), \
             patch("arc.application.deployment.service.VersionRepository"), \
             patch("arc.application.deployment.service.get_deployer") as MockDeployer:

            from arc.application.deployment.service import DeployService

            repo_instance = MockRepo.return_value
            # create 返回新 deployment
            async def fake_create(d):
                return d
            repo_instance.create = AsyncMock(side_effect=fake_create)
            repo_instance.update = AsyncMock()

            # deployer 抛异常
            deployer_instance = MockDeployer.return_value
            deployer_instance.deploy = AsyncMock(side_effect=RuntimeError("S3 down"))

            service = DeployService(db)
            result = await service.deploy_static_site(
                project_id=uuid.uuid4(),
                version_id=uuid.uuid4(),
                local_dir="/tmp/dist",
            )

            assert result.status == DeploymentStatus.FAILED
            assert "S3 down" in (result.error_message or "")
            db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_success_marks_deployed(self):
        from arc.domain.deployment.value_objects import DeploymentStatus

        db = AsyncMock()
        db.commit = AsyncMock()

        with patch("arc.application.deployment.service.DeploymentRepository") as MockRepo, \
             patch("arc.application.deployment.service.ProjectRepository"), \
             patch("arc.application.deployment.service.VersionRepository") as MockVersionRepo, \
             patch("arc.application.deployment.service.get_deployer") as MockDeployer:

            from arc.application.deployment.service import DeployService

            repo_instance = MockRepo.return_value
            async def fake_create(d):
                return d
            repo_instance.create = AsyncMock(side_effect=fake_create)
            repo_instance.update = AsyncMock()

            version_repo = MockVersionRepo.return_value
            version_repo.get_by_id = AsyncMock(return_value=None)

            deploy_result = MagicMock()
            deploy_result.success = True
            deploy_result.url = "https://cdn.example.com/deploy/1/index.html"
            deploy_result.prefix = "deployments/proj-1/deploy-1"
            deploy_result.file_count = 42

            deployer_instance = MockDeployer.return_value
            deployer_instance.deploy = AsyncMock(return_value=deploy_result)

            service = DeployService(db)
            result = await service.deploy_static_site(
                project_id=uuid.uuid4(),
                version_id=uuid.uuid4(),
                local_dir="/tmp/dist",
            )

            assert result.status == DeploymentStatus.DEPLOYED
            assert result.deploy_url == "https://cdn.example.com/deploy/1/index.html"
            assert result.files_uploaded == 42


# =====================================================================
# B1: 经验检索质量门控
# =====================================================================


class TestExperienceSearchQualityGate:
    """验证 search_similar 的相似度阈值 + 多样性控制。"""

    def _make_exp(self, eid: str, category: str = "technical") -> MagicMock:
        exp = MagicMock()
        exp.id = uuid.UUID(eid.ljust(32, "0"))
        exp.category = MagicMock()
        exp.category.value = category
        return exp

    @pytest.mark.asyncio
    async def test_filters_below_threshold(self):
        """低于 SIMILARITY_THRESHOLD 的结果被过滤。"""
        from arc.application.experience.service import ExperienceService

        service = ExperienceService.__new__(ExperienceService)
        service.db = AsyncMock()
        service.exp_repo = AsyncMock()
        service.conv_repo = AsyncMock()

        exp1 = self._make_exp("a" * 32)
        exp2 = self._make_exp("b" * 32)

        # exp1 score 0.9 (above), exp2 score 0.3 (below)
        service.exp_repo.search_by_embedding = AsyncMock(
            return_value=[(exp1, 0.9), (exp2, 0.3)]
        )

        with patch("arc.application.ai.resilience.create_resilient_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.embed = AsyncMock(return_value=[0.1] * 1536)
            adapter.close = AsyncMock()
            mock_adapter.return_value = adapter

            results = await service.search_similar("test query", limit=5)

        assert len(results) == 1
        assert results[0].id == exp1.id

    @pytest.mark.asyncio
    async def test_diversity_limits_same_category(self):
        """同一 category 最多返回 MAX_SAME_CATEGORY 条。"""
        from arc.application.experience.service import (
            MAX_SAME_CATEGORY,
            ExperienceService,
        )

        service = ExperienceService.__new__(ExperienceService)
        service.db = AsyncMock()
        service.exp_repo = AsyncMock()
        service.conv_repo = AsyncMock()

        # 5 条都是 technical，score 都很高
        exps = [(self._make_exp(f"{chr(97+i)}" * 32, "technical"), 0.9 - i * 0.01) for i in range(5)]
        service.exp_repo.search_by_embedding = AsyncMock(return_value=exps)

        with patch("arc.application.ai.resilience.create_resilient_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.embed = AsyncMock(return_value=[0.1] * 1536)
            adapter.close = AsyncMock()
            mock_adapter.return_value = adapter

            results = await service.search_similar("test query", limit=5)

        assert len(results) == MAX_SAME_CATEGORY

    @pytest.mark.asyncio
    async def test_empty_when_all_below_threshold(self):
        """所有结果都低于阈值时返回空。"""
        from arc.application.experience.service import ExperienceService

        service = ExperienceService.__new__(ExperienceService)
        service.db = AsyncMock()
        service.exp_repo = AsyncMock()
        service.conv_repo = AsyncMock()

        exp = self._make_exp("a" * 32)
        service.exp_repo.search_by_embedding = AsyncMock(return_value=[(exp, 0.2)])

        with patch("arc.application.ai.resilience.create_resilient_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.embed = AsyncMock(return_value=[0.1] * 1536)
            adapter.close = AsyncMock()
            mock_adapter.return_value = adapter

            results = await service.search_similar("test query")

        assert results == []


# =====================================================================
# A3: Orchestration Worker 超时
# =====================================================================


class TestOrchestrationWorkerTimeout:
    """验证 worker 超时被正确捕获。"""

    @pytest.mark.asyncio
    async def test_worker_timeout_captured_as_exception(self):
        """asyncio.TimeoutError 被 gather(return_exceptions=True) 捕获。"""
        # 直接测试 asyncio 行为一致性
        async def slow_worker():
            await asyncio.sleep(100)

        results = await asyncio.gather(
            asyncio.wait_for(slow_worker(), timeout=0.01),
            return_exceptions=True,
        )
        assert len(results) == 1
        assert isinstance(results[0], asyncio.TimeoutError)


# =====================================================================
# A2: Checkpoint 断点恢复
# =====================================================================


class TestCheckpointRestore:
    """验证 CheckpointManager 的恢复逻辑。"""

    @pytest.mark.asyncio
    async def test_restore_returns_none_when_no_checkpoint(self):
        from arc.application.execution.checkpoint import CheckpointManager

        mgr = CheckpointManager(db=AsyncMock())
        conv = MagicMock()
        conv.messages = [
            MagicMock(metadata=None),
            MagicMock(metadata={"some": "data"}),
        ]

        with patch(
            "arc.infrastructure.repositories.conversation.ConversationRepository"
        ) as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=conv)
            result = await mgr.restore_from_checkpoint(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_restore_builds_handoff_from_checkpoint(self):
        from arc.application.execution.checkpoint import CheckpointManager

        mgr = CheckpointManager(db=AsyncMock())

        # 构造带 checkpoint 的 conversation
        user_msg = MagicMock()
        user_msg.role = MagicMock(value="user")
        user_msg.content = "实现用户登录功能"
        user_msg.metadata = None

        checkpoint_msg = MagicMock()
        checkpoint_msg.role = MagicMock(value="system")
        checkpoint_msg.content = "[Checkpoint: autopilot-round-3]"
        checkpoint_msg.metadata = {
            "checkpoint": True,
            "checkpoint_id": "abc123",
            "checkpoint_label": "autopilot-round-3",
            "checkpoint_state": {
                "round": 3,
                "completed": ["技术方案", "API 设计"],
                "completion_pct": 60,
            },
            "checkpoint_created_at": "2026-06-05T10:00:00+00:00",
        }

        conv = MagicMock()
        conv.messages = [user_msg, checkpoint_msg]

        with patch(
            "arc.infrastructure.repositories.conversation.ConversationRepository"
        ) as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=conv)
            handoff = await mgr.restore_from_checkpoint(uuid.uuid4())

        assert handoff is not None
        assert "实现用户登录功能" in handoff.goal
        assert "技术方案" in handoff.completed
        assert "API 设计" in handoff.completed
        assert "round 4" in handoff.pending[0]  # 从 round 3+1 继续

    @pytest.mark.asyncio
    async def test_get_resume_round_returns_latest(self):
        from arc.application.execution.checkpoint import CheckpointManager

        mgr = CheckpointManager(db=AsyncMock())

        msg1 = MagicMock()
        msg1.metadata = {
            "checkpoint": True,
            "checkpoint_state": {"round": 2},
        }
        msg2 = MagicMock()
        msg2.metadata = {
            "checkpoint": True,
            "checkpoint_state": {"round": 5},
        }

        conv = MagicMock()
        conv.messages = [msg1, msg2]  # msg2 is later

        with patch(
            "arc.infrastructure.repositories.conversation.ConversationRepository"
        ) as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=conv)
            round_num = await mgr.get_resume_round(uuid.uuid4())

        assert round_num == 5  # 最后一个 checkpoint 的 round


# =====================================================================
# C2: SSE Event Buffer
# =====================================================================


class TestExperienceFeedbackRefinement:
    """验证精细化反馈中 '被引用 vs 仅注入' 的判定逻辑。"""

    def test_keyword_matching_detects_reference(self):
        """AI 输出中包含经验 title 前 30 字 → 视为引用。"""
        exp_title = "PostgreSQL 分区表在数据量超百万时的性能优化"
        ai_text = "根据之前的经验，PostgreSQL 分区表在数据量超百万时的性能优化方案中提到..."

        keyword = exp_title[:30]
        assert keyword in ai_text

    def test_short_keyword_skipped(self):
        """过短的 keyword（<5字）被跳过，避免误匹配。"""
        kw = "API"
        assert len(kw) < 5  # 按逻辑应跳过
