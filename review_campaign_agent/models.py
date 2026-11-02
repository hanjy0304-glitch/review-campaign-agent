from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Status(str, Enum):
    APPLIED = "applied"
    REJECTED = "rejected"
    SELECTED = "selected"  # 선정됨, 아직 체험 전
    VISITED = "visited"  # 체험 완료, 글 작성 전
    DONE = "done"  # 글 작성 완료


@dataclass
class Campaign:
    site: str  # 카탈로그 key. Notion 에 직접 입력한 건은 "manual"
    campaign_id: str
    title: str
    status: Status
    kind: str | None = None  # 방문형 | 배송형 | 구매평 | 기자단 ...
    selected_at: date | None = None
    visit_date: date | None = None
    review_deadline: date | None = None
    url: str = ""
    notified: set[str] = field(default_factory=set)
    site_name: str = ""  # 화면에 보여줄 사이트 이름
    ref: str = ""  # 저장소(Notion) 행 id
    shown_days_left: int | None = None  # Notion 에 현재 표시된 남은 일수

    @property
    def key(self) -> str:
        return f"{self.site}:{self.campaign_id}"

    @property
    def is_test(self) -> bool:
        t = self.title.strip().lower()
        return t in ("테스트", "test") or t.startswith(("[테스트]", "[test]"))
