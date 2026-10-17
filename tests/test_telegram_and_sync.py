import json
from datetime import date

import httpx
import pytest

from review_campaign_agent.models import Campaign, Status
from review_campaign_agent.notion_store import NotionError
from review_campaign_agent.rules import Notification, plan_notifications
from review_campaign_agent.sync import run_sync
from review_campaign_agent.telegram import (
    NotifyError,
    TelegramNotifier,
    find_chat_id,
    format_notification,
    format_summary,
)

TODAY = date(2026, 10, 17)


def camp(**kw):
    base = dict(site="manual", campaign_id="p1", title="가짜식당", status=Status.SELECTED, site_name="가짜사이트",
                ref="p1", notified={"selected"})
    base.update(kw)
    return Campaign(**base)


def tg_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_send_posts_to_bot_endpoint():
    seen = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True})

    TelegramNotifier("123:TOKEN", "999", tg_client(handler)).send("안녕")
    assert seen == [("/bot123:TOKEN/sendMessage", {"chat_id": "999", "text": "안녕", "disable_web_page_preview": True})]


def test_telegram_errors_never_contain_the_token():
    def api_error(request):
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    def conn_error(request):
        raise httpx.ConnectError(f"cannot reach {request.url}")

    for handler in (api_error, conn_error):
        with pytest.raises(NotifyError) as e:
            TelegramNotifier("123:SECRETTOKEN", "9", tg_client(handler)).send("x")
        assert "SECRETTOKEN" not in str(e.value)


def test_find_chat_id_uses_latest_message():
    updates = {"ok": True, "result": [{"message": {"chat": {"id": 111}}}, {"message": {"chat": {"id": 222}}}]}
    assert find_chat_id("t", tg_client(lambda r: httpx.Response(200, json=updates))) == "222"
    assert find_chat_id("t", tg_client(lambda r: httpx.Response(200, json={"ok": True, "result": []}))) is None


def test_message_formats():
    c = camp(review_deadline=date(2026, 10, 20), visit_date=date(2026, 10, 18), url="https://example.kr/c/1")
    assert format_notification(Notification(c, "deadline", ("d-3",), 3)).startswith("⏰ 글 마감 D-3\n가짜식당 (가짜사이트)")
    assert "오늘!" in format_notification(Notification(c, "deadline", ("d-0",), 0))
    assert "방문 D-1" in format_notification(Notification(c, "visit", ("v-1",), 1))
    assert "방문 오늘!" in format_notification(Notification(c, "visit", ("v-0",), 0))
    assert "https://example.kr/c/1" in format_notification(Notification(c, "deadline", ("d-3",), 3))
    sel = format_notification(Notification(c, "new_selection", ("selected",), 3))
    assert "선정" in sel and "10/20 (D-3)" in sel and "방문일 10/18" in sel
    assert "입력해 주세요" in format_notification(Notification(camp(), "new_selection", ("selected",), None))
    assert "지났어요" in format_notification(Notification(c, "overdue", ("overdue",), -2))
    assert "마감일을 입력" in format_notification(Notification(camp(), "deadline_missing", ("deadline_missing",)))
    assert "방문일을 입력" in format_notification(Notification(camp(), "visit_missing", ("visit_missing",)))


def test_summary_sorted_by_deadline_and_skips_done():
    rows = [
        camp(title="나중", review_deadline=date(2026, 11, 1)),
        camp(title="먼저", review_deadline=date(2026, 10, 18)),
        camp(title="미정"),
        camp(title="끝", status=Status.DONE),
    ]
    lines = format_summary(rows, TODAY).splitlines()
    assert lines[0] == "📋 오늘의 체험단 (3건)"
    assert [l.split(" (")[0].lstrip("• ") for l in lines[1:]] == ["먼저", "나중", "미정"]
    assert format_summary([camp(status=Status.DONE)], TODAY) is None


class FakeStore:
    def __init__(self, rows):
        self.rows, self.marked, self.days = rows, [], {}

    def fetch_rows(self):
        return self.rows

    def mark_notified(self, c):
        self.marked.append((c.ref, set(c.notified)))

    def set_days_left(self, c, days):
        self.days[c.ref] = days
        c.shown_days_left = days


class FakeNotifier:
    def __init__(self, fail_on=()):
        self.sent, self.fail_on = [], set(fail_on)

    def send(self, text):
        if any(f in text for f in self.fail_on):
            raise NotifyError("실패")
        self.sent.append(text)


def test_sync_sends_marks_after_success_and_updates_days_left():
    row = camp(review_deadline=date(2026, 10, 18))
    store, notifier = FakeStore([row]), FakeNotifier()
    result = run_sync(store, notifier, TODAY, say=lambda m: None)
    assert (result.planned, result.sent, result.failed) == (1, 1, 0)
    assert store.marked == [("p1", {"selected", "d-3", "d-1"})]
    assert store.days == {"p1": 1}
    # 같은 날 다시 실행해도 중복 알림이 없다
    again = run_sync(store, notifier, TODAY, say=lambda m: None)
    assert again.planned == 0 and len(notifier.sent) == 1


def test_failed_send_is_not_marked_and_retried_next_run():
    row = camp(review_deadline=date(2026, 10, 18))
    store = FakeStore([row])
    failing = FakeNotifier(fail_on=["가짜식당"])
    result = run_sync(store, failing, TODAY, say=lambda m: None)
    assert (result.sent, result.failed) == (0, 1) and store.marked == [] and row.notified == {"selected"}
    ok = FakeNotifier()
    assert run_sync(store, ok, TODAY, say=lambda m: None).sent == 1


def test_mark_failure_after_send_is_reported_not_crashing():
    class BrokenMark(FakeStore):
        def mark_notified(self, c):
            raise NotionError("쓰기 실패")

    msgs = []
    result = run_sync(BrokenMark([camp(review_deadline=date(2026, 10, 18))]), FakeNotifier(), TODAY, say=msgs.append)
    assert result.failed == 1 and any("쓰기 실패" in m for m in msgs)


def test_dry_run_prints_and_changes_nothing():
    row = camp(review_deadline=date(2026, 10, 18))
    store, msgs = FakeStore([row]), []
    result = run_sync(store, None, TODAY, summary=True, dry_run=True, say=msgs.append)
    assert result.planned == 1 and result.sent == 0
    assert store.marked == [] and store.days == {} and row.notified == {"selected"}
    assert any("[미리보기]" in m and "가짜식당" in m for m in msgs) and any("오늘의 체험단" in m for m in msgs)


def test_summary_is_sent_only_when_requested():
    rows = [camp(review_deadline=date(2026, 11, 30))]
    quiet, loud = FakeNotifier(), FakeNotifier()
    run_sync(FakeStore(rows), quiet, TODAY, say=lambda m: None)
    result = run_sync(FakeStore(rows), loud, TODAY, summary=True, say=lambda m: None)
    assert quiet.sent == [] and result.summary_sent and "오늘의 체험단" in loud.sent[0]


def test_manual_row_flow_end_to_end_with_rules():
    # Notion 에 사람이 직접 적은 행(선정상태·고유키 없음) → 알림 계산까지 이어지는지
    row = camp(site="manual", notified=set(), review_deadline=date(2026, 10, 19), visit_date=date(2026, 10, 18))
    kinds = [n.kind for n in plan_notifications([row], TODAY)]
    assert kinds == ["new_selection", "visit"]
