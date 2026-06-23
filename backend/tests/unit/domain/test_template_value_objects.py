"""Tests for domain/template value objects (v5.7.0 T1)."""

from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateScope,
    TemplateStatus,
)


class TestTemplateCategory:
    def test_values(self):
        assert TemplateCategory.CRUD_APP == "crud_app"
        assert TemplateCategory.WORKFLOW == "workflow"
        assert TemplateCategory.ECOMMERCE == "ecommerce"
        assert TemplateCategory.SOCIAL == "social"
        assert TemplateCategory.SAAS_BACKEND == "saas_backend"
        assert TemplateCategory.CUSTOM == "custom"

    def test_completeness(self):
        expected = {"crud_app", "workflow", "ecommerce", "social", "saas_backend", "custom"}
        assert {c.value for c in TemplateCategory} == expected


class TestTemplateStatus:
    def test_values(self):
        assert TemplateStatus.DRAFT == "draft"
        assert TemplateStatus.CONFIRMED == "confirmed"
        assert TemplateStatus.PUBLISHED == "published"
        assert TemplateStatus.DEPRECATED == "deprecated"


class TestTemplateScope:
    def test_values(self):
        assert TemplateScope.PERSONAL == "personal"
        assert TemplateScope.ORGANIZATION == "organization"
        assert TemplateScope.PUBLIC == "public"
