"""AI API Error Investigator — core package.
Exposes public API symbols for investigating and diagnosing errors.
"""

from investigator.error_parser import ParsedError
from investigator.investigation import Investigation
from investigator.investigation_result import InvestigationResult
from investigator.investigator import investigate
from investigator.knowledge_loader import KnowledgeEntry

__all__ = [
    "investigate",
    "InvestigationResult",
    "Investigation",
    "ParsedError",
    "KnowledgeEntry",
]