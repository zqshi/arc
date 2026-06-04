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
                {"title": "用户管理", "status": "active", "from_analysis": False},
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

    def test_version_analysis_summary_injected(self) -> None:
        """v5.1.0: 版本分析缓存注入到 prompt section。"""
        ctx = ProjectContext(
            project_name="Arc",
            version_name="v2.0",
            version_analysis_summary="**行动建议**:\n- [P0] 优化性能",
        )
        section = ctx.to_prompt_section()
        assert "版本分析洞察" in section
        assert "优化性能" in section

    def test_version_analysis_empty_not_shown(self) -> None:
        """无分析缓存时不输出版本分析段。"""
        ctx = ProjectContext(
            project_name="Arc",
            version_name="v2.0",
            version_analysis_summary="",
        )
        section = ctx.to_prompt_section()
        assert "版本分析洞察" not in section

    def test_sibling_from_analysis_tag(self) -> None:
        """v5.1.0: sibling 来源标记 AI建议 vs 手动。"""
        ctx = ProjectContext(
            project_name="Arc",
            sibling_requirements=[
                {"title": "AI推荐需求", "status": "pending", "from_analysis": True},
                {"title": "手动创建需求", "status": "active", "from_analysis": False},
            ],
        )
        section = ctx.to_prompt_section()
        assert "AI建议" in section
        assert "手动" in section


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
            sibling_requirements=[{"title": "登录", "status": "done", "from_analysis": False}],
        )
        section = ctx.to_agent_section()
        assert "登录" in section

    def test_analysis_in_agent_section(self) -> None:
        """v5.1.0: agent section 也包含版本分析。"""
        ctx = ProjectContext(
            project_name="Arc",
            version_analysis_summary="当前版本进度正常",
        )
        section = ctx.to_agent_section()
        assert "版本分析洞察" in section
        assert "进度正常" in section
