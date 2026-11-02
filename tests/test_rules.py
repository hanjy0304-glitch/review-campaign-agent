from datetime import date, datetime, timezone

from review_campaign_agent.models import Campaign, Status
from review_campaign_agent.rules import plan_notifications, today_kst

TODAY = date(2026, 10, 17)


def campaign(deadline=None, visit=None, notified=("selected",), status=Status.SELECTED, kind=None, title="title"):
    return Campaign("s", "1", title, status, kind=kind, visit_date=visit, review_deadline=deadline,
                    notified=set(notified))


def kinds(campaigns, today=TODAY):
    return [n.kind for n in plan_notifications(campaigns, today)]


def test_today_is_korean_date():
    # UTC 17일 20:00 = 한국 18일 05:00
    assert today_kst(datetime(2026, 10, 17, 20, 0, tzinfo=timezone.utc)) == date(2026, 10, 18)
    assert today_kst(datetime(2026, 10, 17, 14, 59, tzinfo=timezone.utc)) == date(2026, 10, 17)


def test_new_selection_notified_once():
    c = campaign(date(2026, 11, 30), notified=())
    assert kinds([c]) == ["new_selection"]
    c.notified.add("selected")
    assert kinds([c]) == []


def test_new_selection_absorbs_deadline_info_into_one_message():
    c = campaign(date(2026, 10, 18), notified=())
    (n,) = plan_notifications([c], TODAY)
    assert n.kind == "new_selection" and n.days_left == 1
    assert {"selected", "d-3", "d-1"} <= set(n.keys)
    c.notified.update(n.keys)
    assert kinds([c]) == []


def test_new_selection_without_deadline_is_one_message():
    c = campaign(None, notified=())
    (n,) = plan_notifications([c], TODAY)
    assert n.kind == "new_selection" and set(n.keys) == {"selected", "deadline_missing"}


def test_only_selected_or_visited_campaigns_are_considered():
    for status in (Status.APPLIED, Status.REJECTED, Status.DONE):
        assert kinds([campaign(date(2026, 10, 18), status=status)]) == []


def test_deadline_reminder_at_each_threshold():
    for days, key in ((3, "d-3"), (1, "d-1"), (0, "d-0")):
        (n,) = plan_notifications([campaign(date(2026, 10, 17 + days))], TODAY)
        assert n.kind == "deadline" and n.days_left == days and key in n.keys


def test_no_reminder_before_first_threshold():
    assert kinds([campaign(date(2026, 10, 25))]) == []


def test_reminder_not_repeated_after_marking_keys():
    c = campaign(date(2026, 10, 18))
    (n,) = plan_notifications([c], TODAY)
    c.notified.update(n.keys)
    assert kinds([c]) == []


def test_missed_threshold_sends_one_notification():
    c = campaign(date(2026, 10, 19))  # D-2: d-3 이 아직 안 나간 상태
    (n,) = plan_notifications([c], TODAY)
    assert n.keys == ("d-3",)
    c.notified.update(n.keys)
    assert kinds([c]) == []


def test_overdue_and_missing_deadline_notified_once():
    c = campaign(date(2026, 10, 10))
    assert kinds([c]) == ["overdue"]
    c.notified.add("overdue")
    assert kinds([c]) == []
    m = campaign(None)
    assert kinds([m]) == ["deadline_missing"]
    m.notified.add("deadline_missing")
    assert kinds([m]) == []


def test_visit_reminders_d1_and_dday():
    for days in (1, 0):
        (n,) = plan_notifications([campaign(date(2026, 12, 1), visit=date(2026, 10, 17 + days))], TODAY)
        assert n.kind == "visit" and n.days_left == days and f"v-{days}" in n.keys


def test_visit_reminder_not_before_threshold_or_repeated():
    far = campaign(date(2026, 12, 1), visit=date(2026, 10, 20))
    assert kinds([far]) == []
    near = campaign(date(2026, 12, 1), visit=date(2026, 10, 18))
    (n,) = plan_notifications([near], TODAY)
    near.notified.update(n.keys)
    assert kinds([near]) == []


def test_no_visit_reminder_after_visit_but_deadline_still_applies():
    c = campaign(date(2026, 10, 18), visit=date(2026, 10, 17), status=Status.VISITED)
    assert kinds([c]) == ["deadline"]


def test_visit_kind_without_date_is_flagged_once():
    c = campaign(date(2026, 12, 1), kind="방문형")
    assert kinds([c]) == ["visit_missing"]
    c.notified.add("visit_missing")
    assert kinds([c]) == []
    assert kinds([campaign(date(2026, 12, 1), kind="배송형")]) == []


def test_test_campaigns_are_skipped():
    test_c = campaign(date(2026, 10, 18), title="테스트")
    test_eng = campaign(date(2026, 10, 18), title="test")
    test_bracket = campaign(date(2026, 10, 18), title="[테스트] 식당체험단")
    assert kinds([test_c, test_eng, test_bracket]) == []
