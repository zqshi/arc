"""上下文提供者注册表。"""

from arc.application.context.providers.code_capability import CodeCapabilityProvider
from arc.application.context.providers.deliverable import DeliverableProvider
from arc.application.context.providers.domain_model import DomainModelProvider
from arc.application.context.providers.experience import ExperienceProvider
from arc.application.context.providers.methodology import MethodologyProvider
from arc.application.context.providers.project import ProjectInfoProvider
from arc.application.context.providers.review_feedback import ReviewFeedbackProvider
from arc.application.context.providers.sufficiency import SufficiencyHintProvider
from arc.application.context.providers.template import TemplateProvider

__all__ = [
    "ProjectInfoProvider",
    "DomainModelProvider",
    "ReviewFeedbackProvider",
    "ExperienceProvider",
    "TemplateProvider",
    "MethodologyProvider",
    "CodeCapabilityProvider",
    "DeliverableProvider",
    "SufficiencyHintProvider",
]
