"""Tests for GovernanceArtifactWriter (v6.3.0 T3)。

两层传递第二层: 落盘 charter + CLAUDE.md (charter 操作投影) 到交付项目 local_path。
幂等覆盖, local_path 空/charter 空静默跳过, CLAUDE.md 意图驱动禁硬规则。
"""

from pathlib import Path

from arc.application.project.governance_writer import GovernanceArtifactWriter
from arc.domain.project.charter import ProjectCharter
from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ProjectType


def _project_with_charter(
    tmp_path: Path,
    *,
    project_type: ProjectType = ProjectType.STATIC_SITE,
    conventions: str = "",
    markdown: str | None = None,
) -> Project:
    p = Project(
        name="测试项目",
        project_type=project_type,
        conventions=conventions,
        local_path=str(tmp_path),
    )
    p.charter = ProjectCharter(
        markdown=markdown or "# 宪章\n治理意图内容",
        project_type=project_type,
    )
    return p


class TestGovernanceArtifactWriterWrite:
    def test_write_creates_both_files(self, tmp_path):
        p = _project_with_charter(tmp_path)
        GovernanceArtifactWriter().write(p)

        assert (tmp_path / "CLAUDE.md").exists()
        charter = tmp_path / ".arc" / "governance" / "CHARTER.md"
        assert charter.exists()

    def test_charter_file_contains_charter_markdown(self, tmp_path):
        md = "# 宪章\n独特内容 XYZ"
        p = _project_with_charter(tmp_path, markdown=md)
        GovernanceArtifactWriter().write(p)

        charter = tmp_path / ".arc" / "governance" / "CHARTER.md"
        assert charter.read_text(encoding="utf-8") == md

    def test_context_md_contains_four_mechanism_intents(self, tmp_path):
        p = _project_with_charter(tmp_path)
        GovernanceArtifactWriter().write(p)

        ctx = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "上下文加载意图" in ctx
        assert "版本迭代意图" in ctx
        assert "任务编排意图" in ctx
        assert "质量守护意图" in ctx

    def test_context_md_includes_project_name(self, tmp_path):
        p = _project_with_charter(tmp_path)
        GovernanceArtifactWriter().write(p)

        ctx = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "测试项目" in ctx

    def test_context_md_has_no_hard_rules(self, tmp_path):
        """CLAUDE.md (charter 操作投影) 禁规则执行式硬规则。"""
        p = _project_with_charter(tmp_path)
        GovernanceArtifactWriter().write(p)

        ctx = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        forbidden = [
            "500 行", "500行", "800 行", "单文件行数上限",
            "必须 auth", "必须挂载 auth", "auth 依赖",
            "必修项", "6.1", "6.5",
        ]
        for token in forbidden:
            assert token not in ctx, f"CLAUDE.md 含硬规则措辞: {token!r}"

    def test_context_md_includes_user_conventions_when_nonempty(self, tmp_path):
        p = _project_with_charter(tmp_path, conventions="用户自定义约定 ABC")
        GovernanceArtifactWriter().write(p)

        ctx = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "项目特定治理" in ctx
        assert "用户自定义约定 ABC" in ctx

    def test_context_md_omits_conventions_section_when_empty(self, tmp_path):
        p = _project_with_charter(tmp_path, conventions="")
        GovernanceArtifactWriter().write(p)

        ctx = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "项目特定治理" not in ctx

    def test_write_is_idempotent_overwrites(self, tmp_path):
        """调两次, 文件内容随 charter 更新 (覆盖非追加)。"""
        p = _project_with_charter(tmp_path, markdown="# 第一版")
        writer = GovernanceArtifactWriter()
        writer.write(p)
        first_charter = (tmp_path / ".arc" / "governance" / "CHARTER.md").read_text(
            encoding="utf-8"
        )
        assert first_charter == "# 第一版"

        p.charter = ProjectCharter(
            markdown="# 第二版", project_type=ProjectType.STATIC_SITE
        )
        writer.write(p)
        second_charter = (tmp_path / ".arc" / "governance" / "CHARTER.md").read_text(
            encoding="utf-8"
        )

        assert second_charter == "# 第二版"  # charter 更新
        assert "# 第一版" not in second_charter  # 覆盖非追加

    def test_write_skips_when_no_local_path(self, tmp_path):
        """github clone 前 local_path 为空 → 静默跳过, 不抛。"""
        p = Project(name="t", local_path="")
        p.charter = ProjectCharter(
            markdown="# 宪章", project_type=ProjectType.STATIC_SITE
        )
        # 不应抛异常
        GovernanceArtifactWriter().write(p)
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_write_skips_when_charter_none(self, tmp_path):
        """charter 未初始化 → 跳过。"""
        p = Project(name="t", local_path=str(tmp_path))
        assert p.charter is None
        GovernanceArtifactWriter().write(p)
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_write_skips_when_charter_empty(self, tmp_path):
        """charter markdown 空 → 跳过。"""
        p = Project(name="t", local_path=str(tmp_path))
        p.charter = ProjectCharter(
            markdown="   \n  ", project_type=ProjectType.STATIC_SITE
        )
        GovernanceArtifactWriter().write(p)
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_context_md_has_document_index(self, tmp_path):
        p = _project_with_charter(tmp_path)
        GovernanceArtifactWriter().write(p)

        ctx = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert ".arc/governance/CHARTER.md" in ctx
        assert ".arc/versions/" in ctx
