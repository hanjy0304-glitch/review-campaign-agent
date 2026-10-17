from dataclasses import dataclass
from datetime import date

from .models import Campaign, Status

DEFAULT_REMINDER_DAYS = (3, 1, 0)


@dataclass(frozen=True)
class Notification:
    campaign: Campaign
    kind: str  # new_selection | deadline | overdue | deadline_missing
    keys: tuple[str, ...]  # 발송 후 campaign.notified 에 기록할 키
    days_left: int | None = None


def plan_notifications(
    campaigns: list[Campaign],
    today: date,
    reminder_days: tuple[int, ...] = DEFAULT_REMINDER_DAYS,
) -> list[Notification]:
    out: list[Notification] = []
    for c in campaigns:
        if c.status != Status.SELECTED:
            continue
        if "selected" not in c.notified:
            out.append(Notification(c, "new_selection", ("selected",)))
        if c.review_deadline is None:
            if "deadline_missing" not in c.notified:
                out.append(Notification(c, "deadline_missing", ("deadline_missing",)))
            continue
        days_left = (c.review_deadline - today).days
        if days_left < 0:
            if "overdue" not in c.notified:
                out.append(Notification(c, "overdue", ("overdue",), days_left))
            continue
        due = [n for n in sorted(reminder_days) if days_left <= n]
        keys = tuple(f"d-{n}" for n in due)
        if any(k not in c.notified for k in keys):
            out.append(Notification(c, "deadline", keys, days_left))
    return out
