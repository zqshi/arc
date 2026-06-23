from __future__ import annotations

import re

from arc.application.execution.artifact_extractor import DELIVERABLE_PATTERN
from arc.domain.artifact.value_objects import ArtifactType


class TestDeliverablePattern:
    def test_matches_standard_marker(self) -> None:
        text = """Some discussion here.

[DELIVERABLE:requirement_spec]
```json
{"background": "test", "goals": ["g1"]}
```

More text."""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0][0] == "requirement_spec"
        assert '"background"' in matches[0][1]

    def test_matches_without_json_lang(self) -> None:
        text = """[DELIVERABLE:test_report]
```
{"summary": "all passed"}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0][0] == "test_report"

    def test_matches_multiple_markers(self) -> None:
        text = """[DELIVERABLE:requirement_spec]
```json
{"a": 1}
```

Some text between.

[DELIVERABLE:tech_architecture]
```json
{"b": 2}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 2
        assert matches[0][0] == "requirement_spec"
        assert matches[1][0] == "tech_architecture"

    def test_no_match_without_marker(self) -> None:
        text = "Just a normal response without any deliverables."
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 0


class TestAppCodeServiceSpecExtraction:
    """v5.5.0: 验证 ArtifactExtractor 能识别 app_code / service_spec 标记。

    这两个新 artifact 类型走与既有类型相同的 DELIVERABLE 提取链路，
    只要 ArtifactType 枚举包含它们 (T1/T2 已加)，提取即可成功。
    """

    def test_app_code_marker_recognized_as_valid_type(self) -> None:
        """[DELIVERABLE:app_code] 的 type 字符串能转为 ArtifactType。"""
        text = """[DELIVERABLE:app_code]
```json
{"project_dir": "generated/app", "tech_stack": ["react"], "build_command": "npm run build", "run_command": "npm run dev", "entry_points": ["src/main.tsx"]}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        type_str = matches[0][0]
        # 提取链路的关键: ArtifactType(type_str) 不抛 ValueError
        assert ArtifactType(type_str) == ArtifactType.APP_CODE

    def test_service_spec_marker_recognized_as_valid_type(self) -> None:
        """[DELIVERABLE:service_spec] 的 type 字符串能转为 ArtifactType。"""
        text = """[DELIVERABLE:service_spec]
```json
{"data_model_ref": "v1", "data_persistence": "none", "endpoints": [], "auth_strategy": "none"}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        assert ArtifactType(matches[0][0]) == ArtifactType.SERVICE_SPEC

    def test_dev_report_and_app_code_coexist_in_one_message(self) -> None:
        """DEVELOPMENT 阶段一条消息同时产出 DEV_REPORT + APP_CODE。"""
        text = """[DELIVERABLE:dev_report]
```json
{"test_design": {}, "implementation": {}, "validation": {}}
```

[DELIVERABLE:app_code]
```json
{"project_dir": "gen/app", "tech_stack": ["vue"], "build_command": "npm run build", "run_command": "npm run dev", "entry_points": ["src/main.ts"]}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 2
        types = [m[0] for m in matches]
        assert "dev_report" in types
        assert "app_code" in types

