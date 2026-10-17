from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Status(str, Enum):
    APPLIED = "applied"
    SELECTED = "selected"
    REJECTED = "rejected"
    DONE = "done"


@dataclass
class Campaign:
    site: str
    campaign_id: str
    title: str
    status: Status
    selected_at: date | None = None
    visit_date: date | None = None
    review_deadline: date | None = None
    url: str = ""
    notified: set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        return f"{self.site}:{self.campaign_id}"
