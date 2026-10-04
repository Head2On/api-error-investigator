from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from investigator.error_parser import ParsedError
from investigator.investigation import Investigation
from investigator.knowledge_loader import KnowledgeEntry


Status = Literal["known", "unknown"]


@dataclass
class InvestigationResult:
    status: Status
    parsed_error: ParsedError
    knowledge: KnowledgeEntry | None
    investigation: Investigation | None

    def __post_init__(self) -> None:
        if self.status not in ("known", "unknown"):
            raise ValueError(
                f"status must be 'known' or 'unknown', got {self.status!r}"
            )

        if self.status == "known":
            if self.knowledge is None:
                raise ValueError(
                    "status='known' requires a knowledge entry, got None"
                )
            if self.investigation is None:
                raise ValueError(
                    "status='known' requires an investigation, got None"
                )
        if self.status == "unknown":
            if self.knowledge is not None:
                raise ValueError(
                    "status='unknown' requires knowledge=None, "
                    f"got {type(self.knowledge).__name__}"
                )
            if self.investigation is not None:
                raise ValueError(
                    "status='unknown' requires investigation=None, "
                    f"got {type(self.investigation).__name__}"
                )
            
    @classmethod
    def known(
        cls, 
        parsed_error: ParsedError,
        knowledge: KnowledgeEntry,
        investigation: Investigation,
    ) -> "InvestigationResult":
        return cls(
            status="known",
            parsed_error=parsed_error,
            knowledge=knowledge,
            investigation=investigation,
        )

    @classmethod
    def unknown(cls, parsed_error: ParsedError) -> "InvestigationResult":
        return cls(
            status="unknown",
            parsed_error=parsed_error,
            knowledge=None,
            investigation=None,
        )