"""DomainModelExtractor 静态方法单元测试。"""

from arc.application.execution.domain_model_extractor import DomainModelExtractor


class TestBuildEntityContextMap:
    def test_basic(self):
        entities = [
            {"name": "Order", "bounded_context": "OrderContext"},
            {"name": "Payment", "bounded_context": "PaymentContext"},
        ]
        result = DomainModelExtractor._build_entity_context_map(entities)
        assert result == {"Order": "OrderContext", "Payment": "PaymentContext"}

    def test_empty(self):
        assert DomainModelExtractor._build_entity_context_map([]) == {}

    def test_missing_fields(self):
        entities = [{"name": "Order"}, {"bounded_context": "X"}, {}]
        result = DomainModelExtractor._build_entity_context_map(entities)
        assert result == {}

    def test_non_dict_skipped(self):
        entities = ["not_a_dict", None, 42]
        result = DomainModelExtractor._build_entity_context_map(entities)
        assert result == {}


class TestEntitiesToAggregates:
    def test_basic(self):
        entities = [{"name": "Order", "fields": [{"name": "id"}, {"name": "total"}], "relations": "has items"}]
        result = DomainModelExtractor._entities_to_aggregates(entities, "test-source")
        assert len(result) == 1
        assert result[0]["name"] == "Order"
        assert result[0]["fields"] == ["id", "total"]
        assert result[0]["source"] == "test-source"

    def test_empty(self):
        assert DomainModelExtractor._entities_to_aggregates([], "s") == []

    def test_with_context_map(self):
        entities = [{"name": "Order", "fields": []}]
        ctx = {"Order": "OrderContext"}
        result = DomainModelExtractor._entities_to_aggregates(entities, "s", ctx)
        assert result[0]["context"] == "OrderContext"


class TestMergeAggregates:
    def test_new_aggregate(self):
        existing = [{"name": "Order", "fields": ["id"]}]
        new = [{"name": "Payment", "fields": ["id", "amount"]}]
        result = DomainModelExtractor._merge_aggregates(existing, new)
        names = {a["name"] for a in result}
        assert names == {"Order", "Payment"}

    def test_update_existing(self):
        existing = [{"name": "Order", "fields": ["id"], "source": "old"}]
        new = [{"name": "Order", "fields": ["id", "total"], "source": "new"}]
        result = DomainModelExtractor._merge_aggregates(existing, new)
        assert len(result) == 1
        assert result[0]["fields"] == ["id", "total"]
        assert result[0]["source"] == "new"

    def test_empty_merge(self):
        assert DomainModelExtractor._merge_aggregates([], []) == []


class TestMergeStrategicDesign:
    def test_merge_subdomains(self):
        dm: dict = {"subdomains": []}
        design = {"subdomains": [{"name": "Core", "type": "核心域", "description": "核心业务"}]}
        DomainModelExtractor._merge_strategic_design(dm, design)
        assert len(dm["subdomains"]) == 1
        assert dm["subdomains"][0]["name"] == "Core"

    def test_merge_contexts(self):
        dm: dict = {"contexts": []}
        design = {"bounded_contexts": [{"name": "OrderCtx", "subdomain": "Core"}]}
        DomainModelExtractor._merge_strategic_design(dm, design)
        assert len(dm["contexts"]) == 1


class TestMergeEventStorming:
    def test_merge_events(self):
        dm = {"aggregates": [{"name": "Order", "events": []}]}
        es = {"events": [{"name": "OrderCreated", "aggregate": "Order"}]}
        DomainModelExtractor._merge_event_storming(dm, es)
        assert "OrderCreated" in dm["aggregates"][0]["events"]

    def test_merge_commands(self):
        dm = {"aggregates": [{"name": "Order", "methods": []}]}
        es = {"commands": [{"name": "CreateOrder", "target_aggregate": "Order"}]}
        DomainModelExtractor._merge_event_storming(dm, es)
        assert "CreateOrder" in dm["aggregates"][0]["methods"]

    def test_no_duplicate(self):
        dm = {"aggregates": [{"name": "Order", "events": ["OrderCreated"]}]}
        es = {"events": [{"name": "OrderCreated", "aggregate": "Order"}]}
        DomainModelExtractor._merge_event_storming(dm, es)
        assert dm["aggregates"][0]["events"].count("OrderCreated") == 1


class TestModelsEqual:
    def test_equal(self):
        m = {"subdomains": [], "contexts": [], "aggregates": [], "relations": [], "aggregate_relations": []}
        assert DomainModelExtractor._models_equal(m, m) is True

    def test_different(self):
        m1 = {"aggregates": [{"name": "A"}]}
        m2 = {"aggregates": [{"name": "B"}]}
        assert DomainModelExtractor._models_equal(m1, m2) is False
