from __future__ import annotations

from arc.application.context.provider import ProjectContext


class TestProjectContextHasProject:
    def test_empty(self) -> None:
        ctx = ProjectContext()
        assert ctx.has_project is False

    def test_with_name(self) -> None:
        ctx = ProjectContext(project_name="Arc")
        assert ctx.has_project is True


class TestProjectContextToPromptSection:
    def test_empty_returns_blank(self) -> None:
        ctx = ProjectContext()
        assert ctx.to_prompt_section() == ""

    def test_minimal(self) -> None:
        ctx = ProjectContext(project_name="Arc")
        section = ctx.to_prompt_section()
        assert "项目名称: Arc" in section

    def test_with_all_fields(self) -> None:
        ctx = ProjectContext(
            project_name="Arc",
            project_description="工作台",
            tech_stack="Python + React",
            repo_url="https://github.com/test",
            local_path="/home/user/arc",
            version_name="v1.0",
            version_goal="MVP",
            conventions="使用 DDD 架构",
            sibling_requirements=[
                {"title": "用户管理", "status": "active"},
            ],
        )
        section = ctx.to_prompt_section()
        assert "技术栈: Python + React" in section
        assert "版本: v1.0" in section
        assert "版本目标: MVP" in section
        assert "DDD 架构" in section
        assert "用户管理" in section
        assert "active" in section

    def test_without_version(self) -> None:
        ctx = ProjectContext(project_name="Arc", tech_stack="Go")
        section = ctx.to_prompt_section()
        assert "当前版本" not in section


class TestProjectContextToAgentSection:
    def test_empty_returns_blank(self) -> None:
        ctx = ProjectContext()
        assert ctx.to_agent_section() == ""

    def test_with_codebase_summary(self) -> None:
        ctx = ProjectContext(
            project_name="Arc",
            tech_stack="Python",
            codebase_summary="DDD 分层架构",
        )
        section = ctx.to_agent_section()
        assert "项目背景" in section
        assert "代码库概况" in section
        assert "DDD 分层架构" in section

    def test_with_siblings(self) -> None:
        ctx = ProjectContext(
            project_name="Arc",
            sibling_requirements=[{"title": "登录", "status": "done"}],
        )
        section = ctx.to_agent_section()
        assert "登录" in section
