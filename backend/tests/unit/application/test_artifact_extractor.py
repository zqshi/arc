from __future__ import annotations

import re

from arc.application.execution.artifact_extractor import DELIVERABLE_PATTERN


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
