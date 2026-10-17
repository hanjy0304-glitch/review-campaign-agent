from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from .notion_store import NotionError, NotionStore
from .rules import DEFAULT_REMINDER_DAYS, DEFAULT_VISIT_REMINDER_DAYS, plan_notifications
from .telegram import NotifyError, TelegramNotifier, format_notification, format_summary


@dataclass
class SyncResult:
    planned: int = 0
    sent: int = 0
    failed: int = 0
    summary_sent: bool = False


def run_sync(
    store: NotionStore,
    notifier: TelegramNotifier | None,
    today: date,
    reminder_days: tuple[int, ...] = DEFAULT_REMINDER_DAYS,
    visit_reminder_days: tuple[int, ...] = DEFAULT_VISIT_REMINDER_DAYS,
    summary: bool = False,
    dry_run: bool = False,
    say: Callable[[str], None] = print,
) -> SyncResult:
    """Notion 행을 읽어 보낼 알림을 계산하고 발송한다.

    알림 이력은 발송에 성공한 뒤에만 기록한다. 실패한 알림은 다음 실행에서 다시 시도된다.
    dry_run 이면 아무것도 보내거나 쓰지 않고 내용만 출력한다.
    """
    rows = store.fetch_rows()
    result = SyncResult()
    for n in plan_notifications(rows, today, reminder_days, visit_reminder_days):
        result.planned += 1
        text = format_notification(n)
        if dry_run or notifier is None:
            say(f"[미리보기] {text}\n")
            continue
        try:
            notifier.send(text)
            n.campaign.notified.update(n.keys)
            store.mark_notified(n.campaign)
            result.sent += 1
        except (NotifyError, NotionError) as e:
            # 발송은 됐는데 기록이 실패하면 다음 실행에서 한 번 더 갈 수 있다. 알림 누락보다 낫다.
            result.failed += 1
            say(f"알림 실패 ({n.kind}): {e}")

    if not dry_run:
        for c in rows:
            if c.review_deadline is None or c.ref == "":
                continue
            left = (c.review_deadline - today).days
            if left != c.shown_days_left:
                try:
                    store.set_days_left(c, left)
                except NotionError as e:
                    say(f"남은일수 갱신 실패: {e}")

    if summary and (text := format_summary(rows, today)):
        if dry_run or notifier is None:
            say(f"[미리보기] {text}\n")
        else:
            try:
                notifier.send(text)
                result.summary_sent = True
            except NotifyError as e:
                say(f"요약 발송 실패: {e}")
    return result
