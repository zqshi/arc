"""聚合引用提取器单元测试。"""

from arc.application.review.aggregate_extractor import extract_aggregate_references


class TestExtractAggregateReferences:
    def test_from_data_model_entities(self):
        artifacts = [
            {
                "content": {
                    "data_model": {
                        "entities": [
                            {"name": "Order", "fields": []},
                            {"name": "Payment", "fields": []},
                        ]
                    }
                }
            }
        ]
        result = extract_aggregate_references(artifacts)
        assert "Order" in result
        assert "Payment" in result

    def test_from_event_storming(self):
        artifacts = [
            {
                "content": {
                    "event_storming": {
                        "events": [
                            {"name": "OrderCreated", "aggregate": "Order"},
                            {"name": "PaymentReceived", "aggregate": "Payment"},
                        ],
                        "commands": [
                            {"name": "CreateOrder", "target_aggregate": "Order"},
                        ],
                    }
                }
            }
        ]
        result = extract_aggregate_references(artifacts)
        assert "Order" in result
        assert "Payment" in result

    def test_from_domain_design_contexts(self):
        artifacts = [
            {
                "content": {
                    "domain_design": {
                        "bounded_contexts": [
                            {"name": "OrderContext", "aggregates": ["Order", "OrderItem"]},
                        ]
                    }
                }
            }
        ]
        result = extract_aggregate_references(artifacts)
        assert "Order" in result
        assert "OrderItem" in result

    def test_empty_artifacts(self):
        assert extract_aggregate_references([]) == set()

    def test_invalid_input(self):
        assert extract_aggregate_references([None, "not_a_dict", 42]) == set()

    def test_no_matching_patterns(self):
        artifacts = [{"content": {"some_field": "some_value"}}]
        result = extract_aggregate_references(artifacts)
        assert len(result) == 0

    def test_mixed_sources(self):
        artifacts = [
            {"content": {"data_model": {"entities": [{"name": "User"}]}}},
            {"content": {"event_storming": {"events": [{"name": "e", "aggregate": "Account"}], "commands": []}}},
        ]
        result = extract_aggregate_references(artifacts)
        assert "User" in result
        assert "Account" in result
