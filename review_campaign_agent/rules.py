from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .models import Campaign, Status

KST = ZoneInfo("Asia/Seoul")
DEFAULT_REMINDER_DAYS = (3, 1, 0)
DEFAULT_VISIT_REMINDER_DAYS = (1, 0)
VISIT_KIND = "방문형"


def today_kst(now: datetime | None = None) -> date:
    """모든 날짜 계산은 한국시간 기준. GitHub Actions 는 UTC 로 돌기 때문에 반드시 이 함수를 쓴다."""
    return (now or datetime.now(KST)).astimezone(KST).date()


@dataclass(frozen=True)
class Notification:
    campaign: Campaign
    # new_selection | deadline | check_done | deadline_missing | visit | visit_missing
    kind: str
    keys: tuple[str, ...]  # 발송에 성공한 뒤 campaign.notified 에 기록할 키
    days_left: int | None = None  # deadline/visit: 남은 일수


def _threshold_keys(days_left: int, thresholds: tuple[int, ...], prefix: str) -> tuple[str, ...]:
    return tuple(f"{prefix}-{n}" for n in sorted(thresholds) if days_left <= n)


def _deadline_notification(c: Campaign, today: date, reminder_days: tuple[int, ...]) -> Notification | None:
    if c.review_deadline is None:
        if "deadline_missing" in c.notified:
            return None
        return Notification(c, "deadline_missing", ("deadline_missing",))
    days_left = (c.review_deadline - today).days
    if days_left < 0:
        # 기간이 지났다고 봇이 스스로 종료 처리하지 않는다. 완료 여부는 사람에게 물어보고,
        # 진행단계가 '작성완료'로 바뀌어야(사람이 직접) 알림 대상에서 빠진다.
        return None if "check_done" in c.notified else Notification(c, "check_done", ("check_done",), days_left)
    keys = _threshold_keys(days_left, reminder_days, "d")
    if any(k not in c.notified for k in keys):
        return Notification(c, "deadline", keys, days_left)
    return None


def _visit_notification(c: Campaign, today: date, visit_days: tuple[int, ...]) -> Notification | None:
    if c.visit_date is None:
        if c.kind == VISIT_KIND and "visit_missing" not in c.notified:
            return Notification(c, "visit_missing", ("visit_missing",))
        return None
    days_left = (c.visit_date - today).days
    if days_left < 0:
        return None
    keys = _threshold_keys(days_left, visit_days, "v")
    if any(k not in c.notified for k in keys):
        return Notification(c, "visit", keys, days_left)
    return None


def plan_notifications(
    campaigns: list[Campaign],
    today: date,
    reminder_days: tuple[int, ...] = DEFAULT_REMINDER_DAYS,
    visit_reminder_days: tuple[int, ...] = DEFAULT_VISIT_REMINDER_DAYS,
) -> list[Notification]:
    """오늘 보내야 할 알림 목록. 발송 성공 후 호출 측이 notification.keys 를 notified 에 기록해야 한다."""
    out: list[Notification] = []
    for c in campaigns:
        if c.is_test or c.status not in (Status.SELECTED, Status.VISITED):
            continue
        deadline_n = _deadline_notification(c, today, reminder_days)
        if "selected" not in c.notified:
            # 신규 선정 알림에 마감 정보를 합쳐서 한 번에 보낸다.
            # 완료 확인 요청(check_done)은 질문이므로 선정 알림에 섞지 않고 따로 보낸다.
            merge = deadline_n if deadline_n and deadline_n.kind != "check_done" else None
            keys = ("selected",) + (merge.keys if merge else ())
            out.append(Notification(c, "new_selection", keys, deadline_n.days_left if deadline_n else None))
        elif deadline_n:
            out.append(deadline_n)
        if c.status == Status.SELECTED and (visit_n := _visit_notification(c, today, visit_reminder_days)):
            out.append(visit_n)
    return out
